"""Paxalia Admin registry, compatibility, and configuration diagnostics."""

from __future__ import annotations

import traceback

from django.contrib import admin
from django.core.management.base import BaseCommand
from django.urls import NoReverseMatch, reverse

from paxalia.admin_center import registry
from paxalia.settings import get_config


class Command(BaseCommand):
    help = "Validate Paxalia Admin model discovery, configuration, Django compatibility, and security policy."

    def add_arguments(self, parser):
        parser.add_argument("--quiet-pass", action="store_true", help="Suppress successful checks.")

    def handle(self, *args, **options):
        quiet = bool(options["quiet_pass"])
        failures = 0
        warnings = 0
        self._configuration_failures = 0
        self._configuration_warnings = 0

        def check(name, func, *, warn=False):
            nonlocal failures, warnings
            try:
                detail = func()
                if warn:
                    warnings += 1
                    prefix = "WARN"
                else:
                    prefix = "PASS"
                if not quiet or warn:
                    suffix = f": {detail}" if detail else ""
                    self.stdout.write(f"[{prefix}] {name}{suffix}")
                return detail
            except Exception as exc:  # noqa: BLE001
                failures += 1
                self.stderr.write(self.style.ERROR(f"[FAIL] {name}: {exc.__class__.__name__}: {exc}"))
                self.stderr.write(traceback.format_exc())
                return None

        check("Django Admin site registry", lambda: f"{len(admin.site._registry)} registered model(s)")
        check("Paxalia Admin enabled", lambda: "enabled" if get_config().get("ADMIN_ENABLED", True) else "disabled")
        check("Registered model discovery", self._check_discovery)
        self._check_configuration_report(quiet=quiet)
        check("ModelAdmin compatibility hooks", self._check_model_admin_hooks)
        check("Changelist editor compatibility", self._check_changelist_editor)
        check("Deletion preview compatibility", self._check_deletion_preview)
        check("Relationship and inline discovery", self._check_relationship_hooks)
        check("History route", self._check_history_route)
        check("Sensitive-field policy", self._check_sensitive_policy)
        check("Admin hardening settings", self._check_hardening_settings)

        failures += self._configuration_failures
        warnings += self._configuration_warnings

        self.stdout.write(
            f"Paxalia Admin diagnostics completed: {failures} failures, {warnings} warnings."
        )
        if failures:
            raise SystemExit(1)

    def _check_discovery(self):
        definitions = registry.definitions()
        for definition in definitions:
            if definition.model_admin is not admin.site._registry.get(definition.model):
                raise AssertionError(f"Registry adapter mismatch for {definition.label}")
        return f"{len(definitions)} accessible model(s)"

    def _check_configuration_report(self, *, quiet=False):
        """Report configuration findings using their actual severity.

        A clean configuration is a PASS, not a warning. Registry-level
        errors are failures; advisory findings are warnings.
        """
        issues = registry.validate_configuration()
        if not issues:
            if not quiet:
                self.stdout.write("[PASS] Model configuration: no configuration issues")
            return

        errors = [issue for issue in issues if str(issue.get("level", "warning")).lower() == "error"]
        warnings_found = [issue for issue in issues if issue not in errors]

        preview_errors = "; ".join(issue["message"] for issue in errors[:4])
        preview_warnings = "; ".join(issue["message"] for issue in warnings_found[:4])

        if errors:
            self._configuration_failures += 1
            detail = preview_errors or f"{len(errors)} configuration error(s)"
            self.stderr.write(self.style.ERROR(f"[FAIL] Model configuration: {detail}"))

        if warnings_found:
            self._configuration_warnings += 1
            detail = preview_warnings or f"{len(warnings_found)} configuration warning(s)"
            self.stdout.write(f"[WARN] Model configuration: {detail}")

    def _check_configuration(self):
        """Compatibility helper retained for callers/tests using the method directly."""
        issues = registry.validate_configuration()
        if not issues:
            return "no configuration issues"
        return "; ".join(issue["message"] for issue in issues[:4])

    def _check_model_admin_hooks(self):
        definitions = registry.definitions()
        required = (
            "get_queryset",
            "get_form",
            "get_list_display",
            "get_list_display_links",
            "get_list_filter",
            "get_search_fields",
            "get_ordering",
            "get_actions",
            "get_fieldsets",
            "get_readonly_fields",
            "get_inline_instances",
            "get_changelist_form",
            "get_changelist_formset",
            "has_view_permission",
            "has_add_permission",
            "has_change_permission",
            "has_delete_permission",
            "delete_model",
            "delete_queryset",
            "save_form",
            "save_model",
            "save_related",
            "log_addition",
            "log_change",
            "log_deletion",
        )
        missing = []
        for definition in definitions:
            for method_name in required:
                if not callable(getattr(definition.model_admin, method_name, None)):
                    missing.append(f"{definition.label}:{method_name}")
        if missing:
            raise AssertionError("Missing ModelAdmin hooks: " + ", ".join(missing[:12]))
        return f"checked {len(definitions)} ModelAdmin definition(s)"

    def _check_changelist_editor(self):
        definitions = registry.definitions()
        editable_models = []
        invalid = []
        for definition in definitions:
            try:
                editable = definition.list_editable(None)
            except Exception as exc:
                invalid.append(f"{definition.label}: {exc.__class__.__name__}: {exc}")
                continue
            if not editable:
                continue
            editable_models.append(definition.label)
            value = getattr(definition.model_admin, "list_editable", ())
            if value is None:
                value = ()
            if isinstance(value, str) or not hasattr(value, "__iter__"):
                invalid.append(f"{definition.label}: list_editable must be an iterable of field names")
        if invalid:
            raise AssertionError("Invalid list_editable configuration: " + "; ".join(invalid[:12]))
        return f"{len(editable_models)} model(s) expose Django list-editable support"

    def _check_deletion_preview(self):
        definitions = registry.definitions()
        missing = [
            definition.label
            for definition in definitions
            if not callable(getattr(definition.model_admin, "get_deleted_objects", None))
        ]
        if missing:
            # The service has a Collector fallback, so this is a compatibility
            # warning rather than a hard failure.
            return f"{len(missing)} model(s) use Paxalia Collector fallback"
        return "all registered ModelAdmins expose get_deleted_objects"

    def _check_relationship_hooks(self):
        definitions = registry.definitions()
        unsupported = []
        inline_count = 0
        relation_count = 0
        for definition in definitions:
            relation_count += sum(1 for field in definition.model._meta.get_fields() if getattr(field, "is_relation", False))
            try:
                inline_count += len(definition.model_admin.get_inline_instances(None, None) or ())
            except Exception:
                # Dynamic inline methods may require request/object context.
                continue
            try:
                definition.model._meta.get_fields()
            except Exception:
                unsupported.append(definition.label)
        if unsupported:
            raise AssertionError("Could not inspect relations for: " + ", ".join(unsupported[:8]))
        return f"{relation_count} relationship fields and {inline_count} inline definition(s) discovered"

    def _check_history_route(self):
        definitions = registry.definitions()
        if not definitions:
            return "no registered models to probe"
        definition = definitions[0]
        try:
            url = reverse(
                "paxalia:admin_object_history",
                kwargs={
                    "app_label": definition.app_label,
                    "model_name": definition.model_name,
                    "object_id": "diagnostic",
                },
            )
        except NoReverseMatch as exc:
            raise AssertionError("admin_object_history route is not installed") from exc
        return url

    def _check_sensitive_policy(self):
        configured = get_config().get("ADMIN_SENSITIVE_FIELDS") or []
        if not configured:
            raise AssertionError("ADMIN_SENSITIVE_FIELDS must not be empty")
        normalized = {str(value).lower().replace("_", "") for value in configured}
        required = {"password", "token", "secret", "apikey", "authorization", "cookie"}
        missing = required - normalized
        if missing:
            raise AssertionError("Sensitive policy missing: " + ", ".join(sorted(missing)))
        return f"{len(normalized)} configured protected field name(s)"

    def _check_hardening_settings(self):
        config = get_config()
        numeric_settings = {
            "ADMIN_LIST_PER_PAGE": (1, 1000),
            "ADMIN_MAX_RELATION_ITEMS": (1, 100),
            "ADMIN_MAX_BULK_OPERATIONS": (1, 5000),
            "ADMIN_MAX_DELETE_PREVIEW": (1, 500),
            "ADMIN_OBJECT_HISTORY_PER_PAGE": (1, 200),
        }
        invalid = []
        for name, (minimum, maximum) in numeric_settings.items():
            try:
                value = int(config.get(name))
            except (TypeError, ValueError):
                invalid.append(name)
                continue
            if not minimum <= value <= maximum:
                invalid.append(name)
        if not isinstance(config.get("ADMIN_LIST_EDITABLE_ENABLED"), bool):
            invalid.append("ADMIN_LIST_EDITABLE_ENABLED")
        if not isinstance(config.get("ADMIN_PROTECTED_NO_STORE"), bool):
            invalid.append("ADMIN_PROTECTED_NO_STORE")
        if invalid:
            raise AssertionError("Invalid Admin hardening settings: " + ", ".join(invalid))
        return "hardening settings are valid"

