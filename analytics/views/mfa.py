# analytics/views/mfa.py
"""
TOTP enrollment for the current staff user. Builds on top of the
best-effort MFA *status* tab already in the Security Center (v2.2.0),
which only ever reads whether a device exists. This adds the actual
enrollment flow.

django-otp is an OPTIONAL dependency (not in install_requires), same
as the status tab's existing guarded import — so the import happens
inside the view function, never at module level, since urls.py
imports every view module unconditionally and a top-level import
would crash the whole app for anyone who hasn't installed it.

No QR code image here on purpose: rendering one would mean adding a
new dependency (the `qrcode` package, or a bundled JS QR library)
purely for this feature. Instead this shows the manual-entry secret
and the otpauth:// URI as text/link — every authenticator app supports
manual key entry, and opening the otpauth:// link directly on the same
device (common on mobile) works too. QR support can be layered on
later without changing this flow if that trade-off changes.
"""
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from ..security_audit import log_action


def _totp_device_model():
    try:
        from django_otp.plugins.otp_totp.models import TOTPDevice
        return TOTPDevice
    except ImportError:
        return None


@staff_member_required
def mfa_enroll(request):
    TOTPDevice = _totp_device_model()
    if TOTPDevice is None:
        raise Http404(
            "django-otp is not installed. Install django-otp and add "
            "django_otp / django_otp.plugins.otp_totp to INSTALLED_APPS "
            "to enable two-factor enrollment."
        )

    confirmed = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
    if confirmed and request.GET.get('reset') != '1':
        return render(request, 'analytics/mfa_enroll.html', {
            'active_page': 'security',
            'page_title': _('Two-Factor Authentication'),
            'already_enrolled': True,
            'show_search': False,
        })

    # Reuse the same unconfirmed device across GET/POST of one enrollment
    # attempt, rather than creating a fresh one (and a fresh secret) on
    # every page load.
    device = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()
    if device is None:
        device = TOTPDevice.objects.create(user=request.user, confirmed=False, name='default')

    if request.method == 'POST':
        token = request.POST.get('token', '').strip()
        if token and device.verify_token(token):
            device.confirmed = True
            device.save(update_fields=['confirmed'])
            log_action(request, 'security.mfa_enrolled')
            messages.success(request, _('Two-factor authentication is now enabled on your account.'))
            return redirect('analytics:security')
        messages.error(request, _('That code didn\'t match — check your authenticator app and try again.'))

    context = {
        'active_page': 'security',
        'page_title': _('Two-Factor Authentication'),
        'already_enrolled': False,
        'otpauth_url': device.config_url,
        'show_search': False,
    }
    return render(request, 'analytics/mfa_enroll.html', context)


@staff_member_required
@require_POST
def mfa_disable(request):
    TOTPDevice = _totp_device_model()
    if TOTPDevice is None:
        raise Http404("django-otp is not installed.")

    TOTPDevice.objects.filter(user=request.user).delete()
    log_action(request, 'security.mfa_disabled')
    messages.success(request, _('Two-factor authentication has been disabled on your account.'))
    return redirect('analytics:security')
