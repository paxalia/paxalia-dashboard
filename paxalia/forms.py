"""Generic Django-native forms used by Paxalia authentication pages."""
from __future__ import annotations

from django import forms
from django.utils.translation import gettext as _
from django.contrib.auth import get_user_model, load_backend, password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.conf import settings
from django.core.exceptions import ValidationError

from .settings import get_config


User = get_user_model()


class PaxaliaAuthenticationForm(forms.Form):
    """Accept the host user's configured username field and email when available."""

    username = forms.CharField(label=_("Username or email"), max_length=254)
    password = forms.CharField(label=_("Password"), strip=False, widget=forms.PasswordInput)

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.fields["username"].widget.attrs.setdefault("autocomplete", "username")
        self.fields["password"].widget.attrs.setdefault("autocomplete", "current-password")
        try:
            username_field = User._meta.get_field(User.USERNAME_FIELD)
            self.fields["username"].label = _("Username or email") if User.USERNAME_FIELD != "email" and getattr(User, "email", None) else str(username_field.verbose_name).title()
        except Exception:
            pass

    def clean(self):
        cleaned = super().clean()
        identifier = (cleaned.get("username") or "").strip()
        password = cleaned.get("password") or ""
        if not identifier or not password:
            raise ValidationError(_("Please enter your username/email and password."))

        user = self._authenticate_isolated(identifier, password)
        if user is None and "@" in identifier:
            user = self._authenticate_by_email(identifier, password)
        if user is None:
            raise ValidationError(_("Please enter a correct username/email and password."))
        self.confirm_login_allowed(user)

        self.user_cache = user
        return cleaned

    @staticmethod
    def _isolated_backend_paths():
        configured = get_config().get("AUTH_ISOLATED_AUTHENTICATION_BACKENDS")
        if configured:
            paths = configured
        else:
            # Isolation means the host project's authentication stack does not
            # implicitly participate in Paxalia administrator login. Use
            # Django's password-checking backend by default; projects that
            # genuinely require LDAP/SSO/custom credential validation can opt
            # in explicitly with AUTH_ISOLATED_AUTHENTICATION_BACKENDS.
            paths = ["django.contrib.auth.backends.ModelBackend"]
        if not paths:
            paths = ["django.contrib.auth.backends.ModelBackend"]
        return tuple(str(path) for path in paths if str(path).strip())

    def _authenticate_isolated(self, identifier: str, password: str):
        """Authenticate without invoking host-level Axes/2FA session state."""
        for path in self._isolated_backend_paths():
            try:
                backend = load_backend(path)
            except Exception:
                continue
            authenticate_method = getattr(backend, "authenticate", None)
            if not callable(authenticate_method):
                continue
            try:
                user = authenticate_method(
                    self.request, username=identifier, password=password
                )
            except TypeError:
                try:
                    user = authenticate_method(
                        self.request, identifier, password=password
                    )
                except Exception:
                    continue
            except Exception:
                continue
            if user is not None:
                user.backend = path
                return user
        return None

    def _authenticate_by_email(self, email: str, password: str):
        try:
            email_field = User._meta.get_field("email")
        except Exception:
            return None
        if not email_field:
            return None
        try:
            matches = User._default_manager.filter(email__iexact=email)
            if matches.count() != 1:
                return None
            user = matches.first()
            if not user:
                return None
            return self._authenticate_isolated(
                getattr(user, User.USERNAME_FIELD), password
            )
        except Exception:
            return None

    def confirm_login_allowed(self, user):
        """Honor the host authentication policy for the authenticated user."""
        checker = getattr(AuthenticationForm, "confirm_login_allowed", None)
        if checker is not None:
            checker(self, user)
            return
        if not getattr(user, "is_active", True):
            raise ValidationError(_("This account is inactive."))

    def get_user(self):
        return getattr(self, "user_cache", None)


class PaxaliaUserCreationForm(forms.ModelForm):
    """Generic account-creation form that respects AUTH_USER_MODEL."""

    password1 = forms.CharField(label=_("Password"), strip=False, widget=forms.PasswordInput)
    password2 = forms.CharField(label=_("Confirm password"), strip=False, widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        identity_fields = [User.USERNAME_FIELD, *getattr(User, "REQUIRED_FIELDS", [])]
        available = []
        for name in identity_fields:
            if name in self.base_fields:
                continue
            try:
                field = User._meta.get_field(name)
            except Exception:
                continue
            if not field.editable or name == "password":
                continue
            form_field = self._field_from_model_field(field)
            self.fields[name] = form_field
            available.append(name)
        self._identity_field_names = available

    @staticmethod
    def _field_from_model_field(field):
        form_field = field.formfield()
        if form_field is None:
            return forms.CharField(label=field.verbose_name.title(), required=not field.blank, max_length=getattr(field, "max_length", None))
        return form_field

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 != password2:
            raise ValidationError(_("The two password fields did not match."))
        if password1:
            try:
                password_validation.validate_password(password1, self.instance)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        for name in getattr(self, "_identity_field_names", []):
            setattr(user, name, self.cleaned_data.get(name))
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user

