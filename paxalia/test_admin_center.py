import io
import types
import zipfile

from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import include, path, reverse
from django.utils import timezone

from .admin_center import PaxaliaModelAdapter, registry
from .models import Funnel, PageView, ShareLink, Site


urlpatterns = [
    path("", include("paxalia.urls")),
    path("django-admin/", admin.site.urls),
]


def paxalia_test_activate_sites(modeladmin, request, queryset):
    queryset.update(is_active=True)


paxalia_test_activate_sites.short_description = "Activate selected sites"


def _rewrite_package_member(raw, member_name, transform):
    source = io.BytesIO(raw)
    output = io.BytesIO()
    transformed = False
    with zipfile.ZipFile(source, "r") as source_zip, zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as target_zip:
        for info in source_zip.infolist():
            data = source_zip.read(info.filename)
            if info.filename == member_name and not transformed:
                data = transform(data)
                transformed = True
            target_zip.writestr(info.filename, data)
    if not transformed:
        raise AssertionError(f"Package member not found: {member_name}")
    return output.getvalue()


def _append_duplicate_package_member(raw, member_name):
    source = io.BytesIO(raw)
    output = io.BytesIO()
    with zipfile.ZipFile(source, "r") as source_zip, zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as target_zip:
        infos = source_zip.infolist()
        for info in infos:
            target_zip.writestr(info.filename, source_zip.read(info.filename))
        target_zip.writestr(member_name, source_zip.read(member_name))
    return output.getvalue()


def _flip_first_byte(data):
    value = bytearray(data)
    if not value:
        raise AssertionError("Cannot tamper with an empty package member")
    value[0] ^= 1
    return bytes(value)


@override_settings(ROOT_URLCONF="paxalia.test_admin_center")
class PaxaliaAdminCenterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin_user = User.objects.create_superuser(
            username="paxalia-admin-test",
            email="admin@example.com",
            password="test-password",
        )
        cls.site = Site.objects.create(name="Example", domain="example.test", is_active=True)

    def setUp(self):
        self.client.force_login(self.admin_user)
        # Admin Center tests exercise Django ModelAdmin/registry behavior.
        # The dedicated security test suite covers the mandatory three-layer
        # authentication contract separately. Keep these tests isolated from
        # that policy so they continue to verify the generic Admin subsystem.
        self.admin_gate_patch = patch("paxalia.admin_security.admin_session_is_valid", return_value=True)
        self.admin_gate_patch.start()
        self.addCleanup(self.admin_gate_patch.stop)
        self.request = RequestFactory().get("/")
        self.request.user = self.admin_user

    def patch_model_admin(self, model, attribute, value):
        model_admin = admin.site._registry[model]
        original = getattr(model_admin, attribute)
        setattr(model_admin, attribute, value)
        self.addCleanup(setattr, model_admin, attribute, original)
        return model_admin

    @staticmethod
    def admin_datetime_payload(field_name, value):
        value = timezone.localtime(value) if timezone.is_aware(value) else value
        return {
            f"{field_name}_0": value.strftime("%Y-%m-%d"),
            f"{field_name}_1": value.strftime("%H:%M:%S"),
        }

    def test_registry_discovers_registered_model_and_adapter(self):
        definition = registry.get("paxalia", "site", request=self.request)
        self.assertIs(definition.model, Site)
        self.assertIs(definition.model_admin, admin.site._registry[Site])
        adapter = PaxaliaModelAdapter(definition)
        self.assertIs(adapter.model, Site)
        self.assertTrue(adapter.permissions(self.request)["view"])
        self.assertEqual(adapter.metadata(self.request)["label"], "paxalia.site")
        self.assertEqual(definition.identity_fields, ("domain",))

    def test_package_identity_prefers_natural_unique_field_over_primary_key(self):
        from .packages.engine import identity_fields

        self.assertEqual(identity_fields(Site), ["domain"])

    def test_registry_model_policy_metadata_is_generic(self):
        with override_settings(PAXALIA_DASHBOARD={
            "ADMIN_MODELS": {
                "paxalia.site": {
                    "hidden_fields": ["domain"],
                    "display_fields": ["name"],
                    "identity_fields": ["name"],
                    "max_relation_items": 2,
                    "protected": True,
                    "allow_duplicate": True,
                },
            },
        }):
            definition = registry.get("paxalia", "site", request=self.request)
            self.assertEqual(definition.identity_fields, ("name",))
            self.assertEqual(definition.hidden_fields, {"domain"})
            self.assertEqual(definition.display_fields, {"name"})
            self.assertEqual(definition.max_relation_items, 2)
            self.assertTrue(definition.protected)

    def test_admin_navigation_and_model_pages_render(self):
        urls = [
            reverse("paxalia:admin_home"),
            reverse("paxalia:admin_models"),
            reverse("paxalia:admin_audit"),
            reverse("paxalia:admin_model_overview", kwargs={"app_label": "paxalia", "model_name": "site"}),
            reverse("paxalia:admin_model_list", kwargs={"app_label": "paxalia", "model_name": "site"}),
            reverse("paxalia:admin_model_stats", kwargs={"app_label": "paxalia", "model_name": "site"}),
            reverse("paxalia:admin_object_detail", kwargs={"app_label": "paxalia", "model_name": "site", "object_id": self.site.pk}),
            reverse("paxalia:admin_object_history", kwargs={"app_label": "paxalia", "model_name": "site", "object_id": self.site.pk}),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_model_list_uses_search_and_filters(self):
        Site.objects.create(name="Inactive", domain="inactive.test", is_active=False)
        url = reverse("paxalia:admin_model_list", kwargs={"app_label": "paxalia", "model_name": "site"})
        response = self.client.get(url, {"q": "inactive.test", "is_active__exact": "0"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "inactive.test")
        self.assertNotContains(response, "example.test")

    def test_protected_model_statistics_json_is_no_store(self):
        with override_settings(PAXALIA_DASHBOARD={"ADMIN_MODELS": {"paxalia.site": {"protected": True}}}):
            url = reverse("paxalia:admin_model_stats", kwargs={"app_label": "paxalia", "model_name": "site"})
            response = self.client.get(url, {"format": "json"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Cache-Control"], "no-store, no-cache, must-revalidate, max-age=0")

    def test_model_statistics_json_is_bounded_and_available(self):
        url = reverse("paxalia:admin_model_stats", kwargs={"app_label": "paxalia", "model_name": "site"})
        response = self.client.get(url, {"format": "json"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("total", response.json())
        self.assertIn("related_fields", response.json())

    def test_site_crud_uses_django_model_validation_and_permissions(self):
        add_url = reverse("paxalia:admin_model_add", kwargs={"app_label": "paxalia", "model_name": "site"})

        # Django ModelForm keeps editable, non-blank fields required even when
        # the model field has a default. The Paxalia surface must preserve that
        # native validation contract rather than silently inventing missing data.
        invalid_response = self.client.post(add_url, {
            "name": "Created",
            "domain": "created.test",
            "is_active": "on",
        })
        self.assertEqual(invalid_response.status_code, 200)
        self.assertTrue(invalid_response.context["form"].errors)
        self.assertFalse(Site.objects.filter(domain="created.test").exists())

        created_at = timezone.now().replace(microsecond=0)
        add_data = {
            "name": "Created",
            "domain": "created.test",
            "is_active": "on",
        }
        add_data.update(self.admin_datetime_payload("created_at", created_at))
        response = self.client.post(add_url, add_data)
        self.assertEqual(response.status_code, 302)
        created = Site.objects.get(domain="created.test")

        change_url = reverse("paxalia:admin_object_change", kwargs={"app_label": "paxalia", "model_name": "site", "object_id": created.pk})
        change_data = {
            "name": "Changed",
            "domain": "changed.test",
            "is_active": "on",
        }
        change_data.update(self.admin_datetime_payload("created_at", created.created_at))
        response = self.client.post(change_url, change_data)
        self.assertEqual(response.status_code, 302)
        created.refresh_from_db()
        self.assertEqual(created.name, "Changed")
        self.assertEqual(created.domain, "changed.test")

        history_url = reverse("paxalia:admin_object_history", kwargs={"app_label": "paxalia", "model_name": "site", "object_id": created.pk})
        history_response = self.client.get(history_url)
        self.assertEqual(history_response.status_code, 200)
        self.assertContains(history_response, "Change")

        delete_url = reverse("paxalia:admin_object_delete", kwargs={"app_label": "paxalia", "model_name": "site", "object_id": created.pk})
        self.assertEqual(self.client.get(delete_url).status_code, 200)
        self.assertEqual(self.client.post(delete_url).status_code, 302)
        self.assertFalse(Site.objects.filter(pk=created.pk).exists())

    def test_site_crud_rejects_model_validation_conflicts_without_write(self):
        add_url = reverse("paxalia:admin_model_add", kwargs={"app_label": "paxalia", "model_name": "site"})
        duplicate_data = {
            "name": "Conflicting",
            "domain": self.site.domain,
            "is_active": "on",
        }
        duplicate_data.update(self.admin_datetime_payload("created_at", timezone.now().replace(microsecond=0)))
        response = self.client.post(add_url, duplicate_data)
        self.assertEqual(response.status_code, 200)
        self.assertIn("domain", response.context["form"].errors)
        self.assertEqual(Site.objects.filter(domain=self.site.domain).count(), 1)

    def test_registered_user_records_page_renders_without_translation_local_collision(self):
        url = reverse("paxalia:admin_model_list", kwargs={"app_label": "auth", "model_name": "user"})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Users")

    def test_list_editable_uses_native_modeladmin_attribute(self):
        model_admin = self.patch_model_admin(Site, "list_editable", ("is_active",))
        definition = registry.get("paxalia", "site", request=self.request)
        self.assertEqual(definition.list_editable(self.request), ("is_active",))
        self.assertIs(model_admin, admin.site._registry[Site])

    def test_list_editable_uses_django_changelist_formset(self):
        model_admin = self.patch_model_admin(Site, "list_editable", ("is_active",))
        url = reverse("paxalia:admin_model_list", kwargs={"app_label": "paxalia", "model_name": "site"})
        response = self.client.get(url, {"q": "example.test"})
        self.assertEqual(response.status_code, 200)
        formset = response.context["list_editable_formset"]
        self.assertIsNotNone(formset)
        self.assertEqual(len(formset.forms), 1)
        self.assertEqual(set(formset.forms[0].fields), {"is_active", "id"})
        self.assertContains(response, f'name="{formset.prefix}-TOTAL_FORMS"')
        self.assertContains(response, f'name="{formset.prefix}-INITIAL_FORMS"')
        self.assertContains(response, f'name="{formset.prefix}-0-is_active"')

        management = formset.management_form
        data = {
            management.add_prefix("TOTAL_FORMS"): str(formset.total_form_count()),
            management.add_prefix("INITIAL_FORMS"): str(formset.initial_form_count()),
            management.add_prefix("MIN_NUM_FORMS"): str(formset.management_form.fields["MIN_NUM_FORMS"].initial or 0),
            management.add_prefix("MAX_NUM_FORMS"): str(formset.management_form.fields["MAX_NUM_FORMS"].initial or 1000),
            f"{formset.prefix}-0-id": str(self.site.pk),
            f"{formset.prefix}-0-is_active": "",
            "_save": "1",
        }
        post_response = self.client.post(f"{url}?q=example.test", data)
        if post_response.status_code != 302:
            bound_formset = post_response.context.get("list_editable_formset")
            self.fail(
                "List-editable POST did not redirect: "
                f"errors={getattr(bound_formset, 'errors', None)!r}; "
                f"non_form_errors={getattr(bound_formset, 'non_form_errors', lambda: [])()!r}"
            )
        self.site.refresh_from_db()
        self.assertFalse(self.site.is_active)

        # The same native formset must also accept a checked BooleanField.
        second_response = self.client.get(url, {"q": "example.test"})
        second_formset = second_response.context["list_editable_formset"]
        second_data = {
            second_formset.management_form.add_prefix("TOTAL_FORMS"): str(second_formset.total_form_count()),
            second_formset.management_form.add_prefix("INITIAL_FORMS"): str(second_formset.initial_form_count()),
            second_formset.management_form.add_prefix("MIN_NUM_FORMS"): str(second_formset.management_form.fields["MIN_NUM_FORMS"].initial or 0),
            second_formset.management_form.add_prefix("MAX_NUM_FORMS"): str(second_formset.management_form.fields["MAX_NUM_FORMS"].initial or 1000),
            f"{second_formset.prefix}-0-id": str(self.site.pk),
            f"{second_formset.prefix}-0-is_active": "on",
            "_save": "1",
        }
        self.assertEqual(self.client.post(f"{url}?q=example.test", second_data).status_code, 302)
        self.site.refresh_from_db()
        self.assertTrue(self.site.is_active)

    def test_custom_model_admin_action_executes_through_registered_action(self):
        model_admin = self.patch_model_admin(Site, "actions", (paxalia_test_activate_sites,))
        self.site.is_active = False
        self.site.save(update_fields=["is_active"])
        url = reverse("paxalia:admin_model_action", kwargs={"app_label": "paxalia", "model_name": "site"})
        response = self.client.post(url, {"action": paxalia_test_activate_sites.__name__, "selected": [str(self.site.pk)]})
        self.assertEqual(response.status_code, 302)
        self.site.refresh_from_db()
        self.assertTrue(self.site.is_active)
        self.assertIsNotNone(model_admin)

    def test_custom_model_admin_action_rejects_object_level_permission_denial(self):
        model_admin = self.patch_model_admin(Site, "actions", (paxalia_test_activate_sites,))
        original = model_admin.has_change_permission

        def deny_one(self, request, obj=None):
            if obj is not None and str(obj.pk) == str(PaxaliaAdminCenterTests.site.pk):
                return False
            return original(request, obj)

        model_admin.has_change_permission = types.MethodType(deny_one, model_admin)
        self.addCleanup(setattr, model_admin, "has_change_permission", original)
        url = reverse("paxalia:admin_model_action", kwargs={"app_label": "paxalia", "model_name": "site"})
        response = self.client.post(url, {"action": paxalia_test_activate_sites.__name__, "selected": [str(self.site.pk)]})
        self.assertEqual(response.status_code, 403)

    def test_bulk_delete_rejects_object_level_permission_denial(self):
        model_admin = admin.site._registry[Site]
        original = model_admin.has_delete_permission

        def deny_one(self, request, obj=None):
            if obj is not None and str(obj.pk) == str(PaxaliaAdminCenterTests.site.pk):
                return False
            return original(request, obj)

        model_admin.has_delete_permission = types.MethodType(deny_one, model_admin)
        self.addCleanup(setattr, model_admin, "has_delete_permission", original)
        url = reverse("paxalia:admin_model_action", kwargs={"app_label": "paxalia", "model_name": "site"})
        response = self.client.post(url, {"action": "delete_selected", "selected": [str(self.site.pk)]})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Site.objects.filter(pk=self.site.pk).exists())
        self.assertNotIn("paxalia_admin_delete_ids", self.client.session)

    def test_delete_confirmation_uses_model_admin_impact_contract(self):
        url = reverse("paxalia:admin_object_delete", kwargs={"app_label": "paxalia", "model_name": "site", "object_id": self.site.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn(Site._meta.label, response.context["impact"]["counts"])
        self.assertContains(response, "Objects affected")

    def test_protected_model_detail_is_no_store(self):
        with override_settings(PAXALIA_DASHBOARD={
            "ADMIN_MODELS": {"paxalia.site": {"protected": True}},
        }):
            url = reverse("paxalia:admin_object_detail", kwargs={"app_label": "paxalia", "model_name": "site", "object_id": self.site.pk})
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Cache-Control"], "no-store, no-cache, must-revalidate, max-age=0")
            self.assertEqual(response["Pragma"], "no-cache")

    def test_sensitive_model_value_is_masked_on_detail(self):
        secret = "pbkdf2_sha256$720000$unusual-secret-value"
        obj = ShareLink.objects.create(name="Protected", password_hash=secret, created_by=self.admin_user)
        url = reverse("paxalia:admin_object_detail", kwargs={"app_label": "paxalia", "model_name": "sharelink", "object_id": obj.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, secret)
        self.assertContains(response, "••••••••")

    def test_staff_without_model_permission_is_denied(self):
        User = get_user_model()
        user = User.objects.create_user(username="limited-staff", password="pw", is_staff=True)
        self.client.force_login(user)
        url = reverse("paxalia:admin_model_list", kwargs={"app_label": "paxalia", "model_name": "site"})
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_funnel_change_page_discovers_inline_admin(self):
        funnel = Funnel.objects.create(name="Checkout funnel", site=self.site)
        url = reverse("paxalia:admin_object_change", kwargs={"app_label": "paxalia", "model_name": "funnel", "object_id": funnel.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Funnel Steps")

    def test_bulk_selection_limit_is_rejected_without_truncation(self):
        url = reverse("paxalia:admin_model_action", kwargs={"app_label": "paxalia", "model_name": "site"})
        selected = [f"missing-{index}" for index in range(501)]
        response = self.client.post(url, {"action": "delete_selected", "selected": selected})
        self.assertEqual(response.status_code, 302)
        self.assertNotIn("paxalia_admin_delete_ids", self.client.session)

    def test_bulk_delete_uses_confirmation_and_django_delete_semantics(self):
        a = Site.objects.create(name="Bulk A", domain="bulk-a.test")
        b = Site.objects.create(name="Bulk B", domain="bulk-b.test")
        action_url = reverse("paxalia:admin_model_action", kwargs={"app_label": "paxalia", "model_name": "site"})
        response = self.client.post(action_url, {"action": "delete_selected", "selected": [str(a.pk), str(b.pk)]})
        self.assertEqual(response.status_code, 302)
        confirmation_url = reverse("paxalia:admin_bulk_delete", kwargs={"app_label": "paxalia", "model_name": "site"})
        response = self.client.get(confirmation_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2")
        self.assertTrue(response.context["impact"]["counts"])
        response = self.client.post(confirmation_url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Site.objects.filter(pk__in=[a.pk, b.pk]).exists())

    def test_admin_diagnostics_clean_configuration_is_not_a_warning(self):
        from io import StringIO
        from django.core.management import call_command

        stdout = StringIO()
        stderr = StringIO()
        call_command("paxalia_admin_test", stdout=stdout, stderr=stderr)
        output = stdout.getvalue() + stderr.getvalue()
        self.assertIn("[PASS] Model configuration: no configuration issues", output)
        self.assertIn("Paxalia Admin diagnostics completed: 0 failures, 0 warnings.", output)
        self.assertNotIn("[WARN] Model configuration", output)

    def test_allowlist_and_configuration_diagnostics_are_safe(self):
        with override_settings(PAXALIA_DASHBOARD={"ADMIN_MODEL_ALLOWLIST": ["paxalia.site"]}):
            definitions = registry.definitions()
            self.assertEqual([item.label for item in definitions], ["paxalia.site"])

        with override_settings(PAXALIA_DASHBOARD={
            "ADMIN_MODELS": {"paxalia.site": {"identity_fields": ["missing_field"]}},
        }):
            issues = registry.validate_configuration()
            self.assertTrue(any(issue["code"] == "missing_field" for issue in issues))

    def test_django_admin_fallback_remains_available(self):
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)

    def test_paxalia_package_round_trip_creates_new_identity(self):
        from .packages.engine import export_model, import_package, preview_package

        raw = export_model(Site, self.request, selected_ids=[self.site.pk])
        self.assertTrue(raw.startswith(b"PK"))
        preview = preview_package(raw, conflict="update")
        self.assertEqual(preview["record_count"], 1)
        self.assertEqual(preview["created"], 0)
        Site.objects.filter(pk=self.site.pk).delete()
        result = import_package(raw, self.request, conflict="update", atomic=True)
        self.assertEqual(result["created"], 1)
        self.assertTrue(Site.objects.filter(domain="example.test").exists())

    def test_paxalia_package_integrity_rejects_content_tampering(self):
        from .packages.engine import export_model, preview_package

        raw = export_model(Site, self.request, selected_ids=[self.site.pk])
        tampered = _rewrite_package_member(raw, "data.json", _flip_first_byte)
        with self.assertRaises(ValueError):
            preview_package(tampered, conflict="update")

    def test_paxalia_package_integrity_rejects_manifest_tampering(self):
        from .packages.engine import export_model, preview_package

        raw = export_model(Site, self.request, selected_ids=[self.site.pk])
        tampered = _rewrite_package_member(raw, "manifest.json", _flip_first_byte)
        with self.assertRaises(ValueError):
            preview_package(tampered, conflict="update")

    def test_paxalia_package_rejects_duplicate_archive_members(self):
        from .packages.engine import export_model, preview_package

        raw = export_model(Site, self.request, selected_ids=[self.site.pk])
        tampered = _append_duplicate_package_member(raw, "data.json")
        with self.assertRaises(ValueError):
            preview_package(tampered, conflict="update")

    def test_paxalia_package_rejects_path_traversal_members(self):
        from .packages.engine import export_model, preview_package

        raw = export_model(Site, self.request, selected_ids=[self.site.pk])
        source = io.BytesIO(raw)
        output = io.BytesIO()
        with zipfile.ZipFile(source, "r") as source_zip, zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as target_zip:
            for info in source_zip.infolist():
                target_zip.writestr(info.filename, source_zip.read(info.filename))
            target_zip.writestr("../evil.txt", b"blocked")
        with self.assertRaises(ValueError):
            preview_package(output.getvalue(), conflict="update")

    def test_package_manifest_preserves_translation_only_mode(self):
        from .packages.engine import build_package, inspect_package

        payload = {
            "schema": 1,
            "translations_only": True,
            "models": [],
            "records": [],
            "record_count": 0,
            "relationship_count": 0,
            "translation_count": 0,
        }

        manifest, normalized, models = inspect_package(build_package(payload))
        self.assertTrue(manifest["translations_only"])
        self.assertTrue(normalized["translations_only"])
        self.assertEqual(models, {})

    def test_paxalia_package_rejects_malformed_record_shape(self):
        from .packages.engine import build_package, PackageError, inspect_package

        payload = {
            "schema": 1,
            "models": [],
            "records": ["not-an-object"],
            "record_count": 1,
            "relationship_count": 0,
            "translation_count": 0,
        }
        with self.assertRaises(PackageError):
            inspect_package(build_package(payload))

    def test_paxalia_package_rejects_malformed_relationship_payload(self):
        from .packages.engine import build_package, export_model, inspect_package, PackageError

        raw = export_model(Site, self.request, selected_ids=[self.site.pk])
        _, payload, _ = inspect_package(raw)
        payload["records"][0]["relationships"] = {"missing_relation": None}
        with self.assertRaises(PackageError):
            inspect_package(build_package(payload))

    def test_paxalia_package_rejects_sensitive_identity_fields(self):
        from .packages.engine import build_package, export_model, inspect_package, PackageError

        raw = export_model(Site, self.request, selected_ids=[self.site.pk])
        _, payload, _ = inspect_package(raw)
        payload["records"][0]["identity"]["secret"] = "should-never-be-accepted"
        with self.assertRaises(PackageError):
            inspect_package(build_package(payload))

    def test_paxalia_package_dry_run_does_not_write(self):
        from .packages.engine import build_package, export_model, import_package, inspect_package

        raw = export_model(Site, self.request, selected_ids=[self.site.pk])
        _, payload, _ = inspect_package(raw)
        payload["records"][0]["fields"]["domain"] = "dry-run.test"
        payload["records"][0]["identity"]["domain"] = "dry-run.test"
        package = build_package(payload)
        result = import_package(package, self.request, conflict="update", atomic=True, dry_run=True)
        self.assertEqual(result["created"], 1)
        self.assertFalse(Site.objects.filter(domain="dry-run.test").exists())

    def test_paxalia_package_atomic_import_rolls_back_prior_records_on_failure(self):
        from .packages.engine import build_package, export_model, import_package, inspect_package, PackageError

        raw = export_model(Site, self.request, selected_ids=[self.site.pk])
        _, payload, _ = inspect_package(raw)
        first = dict(payload["records"][0])
        second = dict(payload["records"][0])
        first["identity"] = dict(first["identity"], domain="atomic-one.test")
        first["fields"] = dict(first["fields"], domain="atomic-one.test")
        second["identity"] = dict(second["identity"], domain="atomic-two.test")
        second["fields"] = dict(second["fields"], domain="atomic-two.test", created_at="not-a-date")
        payload["records"] = [first, second]
        payload["record_count"] = 2
        package = build_package(payload)
        with self.assertRaises(PackageError):
            import_package(package, self.request, conflict="update", atomic=True)
        self.assertFalse(Site.objects.filter(domain="atomic-one.test").exists())
        self.assertFalse(Site.objects.filter(domain="atomic-two.test").exists())

    def test_paxalia_package_partial_import_preserves_successful_records(self):
        from .packages.engine import build_package, export_model, import_package, inspect_package

        raw = export_model(Site, self.request, selected_ids=[self.site.pk])
        _, payload, _ = inspect_package(raw)
        first = dict(payload["records"][0])
        second = dict(payload["records"][0])
        first["identity"] = dict(first["identity"], domain="partial-one.test")
        first["fields"] = dict(first["fields"], domain="partial-one.test")
        second["identity"] = dict(second["identity"], domain="partial-two.test")
        second["fields"] = dict(second["fields"], domain="partial-two.test", created_at="not-a-date")
        payload["records"] = [first, second]
        payload["record_count"] = 2
        payload["models"] = [dict(item) for item in payload["models"]]
        payload["models"][0]["record_count"] = 2
        result = import_package(build_package(payload), self.request, conflict="update", atomic=False)
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertTrue(Site.objects.filter(domain="partial-one.test").exists())
        self.assertFalse(Site.objects.filter(domain="partial-two.test").exists())

    def test_paxalia_protected_model_requires_encryption(self):
        from .packages.engine import export_model, PackageError

        with override_settings(PAXALIA_DASHBOARD={
            "ADMIN_MODELS": {"paxalia.site": {"protected": True}},
            "PACKAGE_REQUIRE_ENCRYPTION_FOR_PROTECTED": True,
        }):
            with self.assertRaises(PackageError):
                export_model(Site, self.request, selected_ids=[self.site.pk])

    def test_paxalia_encrypted_package_rejects_wrong_password(self):
        from .packages.engine import export_model, preview_package, PackageError

        raw = export_model(Site, self.request, selected_ids=[self.site.pk], password="correct-password")
        self.assertEqual(preview_package(raw, password="correct-password", conflict="update")["record_count"], 1)
        with self.assertRaises(PackageError):
            preview_package(raw, password="wrong-password", conflict="update")

    def test_paxalia_allowed_conflict_policy_is_enforced(self):
        from .packages.engine import export_model, preview_package, PackageError

        raw = export_model(Site, self.request, selected_ids=[self.site.pk])
        with override_settings(PAXALIA_DASHBOARD={"PACKAGE_ALLOWED_CONFLICTS": ["skip"]}):
            with self.assertRaises(PackageError):
                preview_package(raw, conflict="update")
            result = preview_package(raw, conflict="skip")
            self.assertEqual(result["skipped"], 1)

    def test_package_export_center_post_returns_a_download(self):
        url = reverse("paxalia:admin_package_export")
        response = self.client.post(url, {"models": ["paxalia.site"]})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"PK"))
        self.assertIn("attachment; filename=", response["Content-Disposition"])
        self.assertIn("paxalia-package-", response["Content-Disposition"])

    def test_package_export_center_supports_multiple_registered_models(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="package-user",
            email="package-user@example.com",
            password="not-exported",
        )
        url = reverse("paxalia:admin_package_export")
        response = self.client.post(url, {
            "models": ["paxalia.site", user_model._meta.label_lower],
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"PK"))
        self.assertIn("attachment; filename=", response["Content-Disposition"])
        self.assertGreater(len(response.content), 100)
        self.assertIsNotNone(user.pk)

    def test_package_export_accepts_selected_model_with_zero_records(self):
        from .packages.engine import export_models, preview_package

        raw = export_models([Site, Funnel], self.request)
        preview = preview_package(raw, conflict="update")
        self.assertEqual(preview["model_count"], 2)
        self.assertEqual(preview["record_count"], 1)

    def test_package_retry_rebuilds_model_metadata_for_failed_subset(self):
        from .packages.engine import build_retry_package, export_models, preview_package

        user_model = get_user_model()
        user_model.objects.create_user(username="retry-user", email="retry@example.com", password="password")
        raw = export_models([Site, user_model], self.request)
        retry = build_retry_package(raw, {"errors": [{"index": 0, "reason": "test failure"}]})
        self.assertIsNotNone(retry)
        preview = preview_package(retry, conflict="update")
        self.assertEqual(preview["record_count"], 1)
        self.assertEqual(preview["model_count"], 1)
        self.assertEqual(preview["created"], 0)

    def test_package_duplicate_record_identity_is_rejected(self):
        from .packages.engine import PackageError, build_package, export_model, inspect_package

        raw = export_model(Site, self.request, selected_ids=[self.site.pk])
        _, payload, _ = inspect_package(raw)
        record = payload["records"][0]
        payload["records"] = [record, dict(record)]
        payload["record_count"] = 2
        payload["models"][0]["record_count"] = 2
        with self.assertRaises(PackageError):
            inspect_package(build_package(payload))

    def test_package_export_handles_nullable_relationships(self):
        from paxalia.models import PageView
        from paxalia.packages.engine import export_models, inspect_package

        page_view = PageView.objects.create(
            site=None,
            url="https://example.com/nullable",
            path="/nullable",
            method="GET",
            status_code=200,
        )
        definition = registry.get("paxalia", "pageview", request=self.request)
        package_bytes = export_models(
            [definition],
            self.request,
            selected_ids_by_model={definition.label: [page_view.pk]},
        )
        manifest, payload, models = inspect_package(package_bytes)
        self.assertEqual(models[definition.label], PageView)
        record = next(record for record in payload["records"] if record["identity"]["id"] == str(page_view.pk))
        self.assertNotIn("site", record["fields"])
        self.assertIsNone(record["relationships"]["site"])

    def test_jsonable_rejects_mapping_key_collisions_after_normalization(self):
        from paxalia.packages.engine import PackageError, _jsonable

        with self.assertRaises(PackageError):
            _jsonable({1: "first", "1": "second"})

    def test_model_export_rejects_unknown_scope(self):
        url = reverse("paxalia:admin_model_export", kwargs={"app_label": "paxalia", "model_name": "site"})
        response = self.client.post(url, {"scope": "unexpected"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "export scope is invalid")

    def test_relation_counts_do_not_disclose_restricted_objects(self):
        page_view = PageView.objects.create(
            site=self.site, url="https://example.test/private", path="/private", method="GET", status_code=200
        )
        model_admin = self.patch_model_admin(PageView, "has_view_permission", lambda request, obj=None: obj is None)
        url = reverse("paxalia:admin_object_detail", kwargs={"app_label": "paxalia", "model_name": "site", "object_id": self.site.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        relation = next(item for item in response.context["relations"] if item["name"] == "page_views")
        self.assertEqual(relation["count"], 0)
        self.assertTrue(relation["has_restricted"])
        self.assertTrue(relation["more"])
        self.assertContains(response, "Some related records are restricted.")
        self.assertNotContains(response, page_view.path)
        self.assertIsNotNone(model_admin)

    def test_jsonable_handles_nested_special_values(self):
        from datetime import datetime
        from uuid import UUID, uuid4
        from .packages.engine import _jsonable

        original_uuid = uuid4()
        value = {"nested": [original_uuid, {"when": datetime.now(), "bytes": b"secret"}]}
        encoded = _jsonable(value)
        self.assertEqual(encoded["nested"][0], str(original_uuid))
        self.assertEqual(encoded["nested"][1]["bytes"]["__paxalia_type__"], "bytes")
        self.assertEqual(encoded["nested"][1]["bytes"]["encoding"], "base64")
        self.assertIsInstance(UUID(encoded["nested"][0]), UUID)

    def test_jsonable_handles_lazy_translation_and_field_file(self):
        from django.utils.translation import gettext_lazy
        from django.core.files.storage import default_storage
        from django.db.models.fields.files import FieldFile
        from .packages.engine import _jsonable

        self.assertEqual(_jsonable(gettext_lazy("Lazy label")), "Lazy label")

        class DummyField:
            storage = default_storage

        field_file = FieldFile(object(), DummyField(), "uploads/example.txt")
        self.assertEqual(_jsonable(field_file), "uploads/example.txt")

    def test_redacted_json_marker_collision_is_not_treated_as_a_sentinel(self):
        from .packages.engine import _restore_redacted

        value = {"__paxalia_type__": "redacted", "extra": "data"}
        restored = _restore_redacted(value)
        self.assertEqual(restored, value)

    def test_kdf_parameters_reject_cpu_amplification_values(self):
        import json
        from .packages.security import PackageSecurityError, decrypt, encrypt

        envelope = json.loads(encrypt(b"payload", "test-password").decode("utf-8"))
        envelope["iterations"] = 2_000_000
        with self.assertRaises(PackageSecurityError):
            decrypt(json.dumps(envelope).encode("utf-8"), "test-password")

    def test_package_validation_blocks_hidden_field_import(self):
        from .packages.engine import PackageError, build_package, export_model, inspect_package

        raw = export_model(Site, self.request, selected_ids=[self.site.pk])
        _, payload, _ = inspect_package(raw)
        record = dict(payload["records"][0])
        record["fields"] = dict(record["fields"], domain="injected.example")
        payload["records"] = [record]
        with override_settings(PAXALIA_DASHBOARD={"ADMIN_MODELS": {"paxalia.site": {"hidden_fields": ["domain"]}}}):
            with self.assertRaises(PackageError):
                inspect_package(build_package(payload))

    def test_model_list_template_respects_object_view_and_selection_flags(self):
        from pathlib import Path

        template = Path(__file__).resolve().parent.joinpath("templates", "paxalia", "admin", "model_list.html").read_text()
        self.assertIn("{% if row.can_view %}", template)
        self.assertIn("{% if row.selectable %}", template)
        self.assertIn("{% trans \"Restricted\" %}", template)
        self.assertNotIn('value="{{ row.object_id }}" data-paxalia-select-item></td>\n                        {% for cell in row.cells %}', template)

    def test_inline_save_submit_is_not_blocked_by_action_guard(self):
        from pathlib import Path

        script = Path(__file__).resolve().parent.joinpath("static", "paxalia", "scripts", "admin-center.js").read_text()
        self.assertIn("submitter?.name === '_save' && submitter?.value === '1'", script)

    def test_paxalia_admin_package_routes_render(self):
        urls = [
            reverse("paxalia:admin_packages"),
            reverse("paxalia:admin_package_export"),
            reverse("paxalia:admin_package_import"),
            reverse("paxalia:admin_package_history"),
            reverse("paxalia:admin_model_export", kwargs={"app_label": "paxalia", "model_name": "site"}),
            reverse("paxalia:admin_model_import", kwargs={"app_label": "paxalia", "model_name": "site"}),
            reverse("paxalia:admin_model_localization", kwargs={"app_label": "paxalia", "model_name": "site"}),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)


    def test_package_nested_secret_keys_are_redacted(self):
        from .packages.engine import _jsonable

        encoded = _jsonable(
            {"api_key": "secret", "nested": {"password": "hidden", "safe": "visible"}},
            sensitive_names={"api_key", "password"},
        )
        self.assertEqual(encoded["api_key"], {"__paxalia_type__": "redacted"})
        self.assertEqual(encoded["nested"]["password"], {"__paxalia_type__": "redacted"})
        self.assertEqual(encoded["nested"]["safe"], "visible")

    def test_sensitive_column_rendering_cannot_fall_back_to_raw_value(self):
        from .admin_center.query import render_column_value

        model_admin = admin.site._registry[Site]
        with override_settings(PAXALIA_DASHBOARD={"ADMIN_SENSITIVE_FIELDS": ["domain"]}):
            with patch("paxalia.admin_center.query.lookup_field", side_effect=AttributeError("lookup failed")):
                self.assertEqual(
                    render_column_value(self.site, "domain", model_admin),
                    "••••••••",
                )


    def test_package_json_bytes_use_round_trip_safe_marker(self):
        from .packages.engine import _jsonable

        encoded = _jsonable(b"secret-bytes")
        self.assertEqual(encoded["__paxalia_type__"], "bytes")
        self.assertEqual(encoded["encoding"], "base64")
        self.assertEqual(encoded["value"], "c2VjcmV0LWJ5dGVz")

    def test_build_package_recomputes_derived_counts_from_records(self):
        from .packages.engine import build_package, inspect_package

        payload = {
            "schema": 1,
            "project": {"django_version": "6.0"},
            "translations_only": False,
            "models": [{
                "label": "paxalia.site",
                "identity_fields": ["domain"],
                "record_count": 0,
            }],
            "records": [{
                "model": "paxalia.site",
                "identity": {"domain": "example.test"},
                "fields": {"name": "Example"},
                "relationships": {},
                "many_to_many": {},
                "translations": {},
            }],
            "record_count": 0,
            "relationship_count": 99,
            "translation_count": 42,
        }

        _, normalized, _ = inspect_package(build_package(payload))
        self.assertEqual(normalized["models"][0]["identity_fields"], ["domain"])
        self.assertEqual(normalized["record_count"], 1)
        self.assertEqual(normalized["relationship_count"], 0)
        self.assertEqual(normalized["translation_count"], 0)
        self.assertEqual(normalized["models"][0]["record_count"], 1)


    def test_partial_package_import_rolls_back_record_when_relationship_fails(self):
        from uuid import uuid4
        from .packages.engine import build_package, export_model, import_package, inspect_package

        page_view = PageView.objects.create(
            site=self.site,
            url="https://example.test/",
            path="/",
            method="GET",
            status_code=200,
        )
        raw = export_model(PageView, self.request, selected_ids=[page_view.pk])
        _, payload, _ = inspect_package(raw)
        record = dict(payload["records"][0])
        new_id = uuid4()
        record["identity"] = {"id": str(new_id)}
        record["fields"] = dict(record["fields"], id=str(new_id))
        original_site_identity = record["relationships"]["site"]["identity"]
        missing_site_identity = {}
        for name, value in original_site_identity.items():
            missing_site_identity[name] = (
                str(uuid4()) if name == "id"
                else "missing-relationship-%s.test" % uuid4().hex
            )
        record["relationships"] = {
            "site": {
                "model": "paxalia.site",
                "identity": missing_site_identity,
            }
        }
        payload["records"] = [record]
        payload["record_count"] = 1
        result = import_package(build_package(payload), self.request, conflict="update", atomic=False)
        self.assertEqual(result["failed"], 1)
        self.assertFalse(PageView.objects.filter(pk=new_id).exists())

    def test_package_import_preserves_required_foreign_keys(self):
        from .models import UptimeCheck, UptimeMonitor
        from .packages.engine import build_package, export_models, import_package, inspect_package

        monitor = UptimeMonitor.objects.create(
            name="Package import monitor",
            url="https://example.test/health",
            is_active=True,
        )
        check = UptimeCheck.objects.create(
            monitor=monitor,
            status="up",
            status_code=200,
        )
        raw = export_models([UptimeMonitor, UptimeCheck], self.request)
        _, payload, _ = inspect_package(raw)

        new_monitor_identity = max(UptimeMonitor.objects.values_list("pk", flat=True)) + 1000
        new_check_identity = max(UptimeCheck.objects.values_list("pk", flat=True)) + 1000
        monitor_record = dict(next(record for record in payload["records"] if record["model"] == "paxalia.uptimemonitor"))
        check_record = dict(next(record for record in payload["records"] if record["model"] == "paxalia.uptimecheck"))
        monitor_record["identity"] = {"id": new_monitor_identity}
        check_record["identity"] = {"id": new_check_identity}
        check_record["relationships"] = {
            "monitor": {"model": "paxalia.uptimemonitor", "identity": {"id": new_monitor_identity}}
        }
        payload["records"] = [monitor_record, check_record]
        payload["record_count"] = 2

        result = import_package(build_package(payload), self.request, conflict="update", atomic=False)
        self.assertEqual(result["created"], 2)
        self.assertEqual(result["failed"], 0)
        imported_monitor = UptimeMonitor.objects.exclude(pk=monitor.pk).get(name=monitor.name)
        imported_check = UptimeCheck.objects.filter(monitor=imported_monitor).exclude(pk=check.pk).first()
        self.assertIsNotNone(imported_check)
        self.assertEqual(imported_check.monitor_id, imported_monitor.pk)


    def test_partial_import_blocks_dependents_of_failed_package_records(self):
        from uuid import uuid4
        from .packages.engine import build_package, export_models, import_package, inspect_package

        page_view = PageView.objects.create(
            site=self.site,
            url="https://example.test/dependency/",
            path="/dependency/",
            method="GET",
            status_code=200,
        )
        raw = export_models([Site, PageView], self.request)
        _, payload, _ = inspect_package(raw)
        site_record = next(record for record in payload["records"] if record["model"] == "paxalia.site")
        page_record = next(record for record in payload["records"] if record["model"] == "paxalia.pageview")

        site_record = dict(site_record)
        site_record["fields"] = dict(site_record["fields"], created_at="not-a-date")
        new_page_id = uuid4()
        page_record = dict(page_record)
        page_record["identity"] = {"id": str(new_page_id)}
        page_record["fields"] = dict(page_record["fields"], id=str(new_page_id))
        payload["records"] = [site_record, page_record]
        payload["record_count"] = 2

        result = import_package(build_package(payload), self.request, conflict="update", atomic=False)
        self.assertEqual(result["failed"], 2)
        self.assertFalse(PageView.objects.filter(pk=new_page_id).exists())
        self.assertEqual({error["index"] for error in result["errors"]}, {0, 1})
        dependent_errors = [
            error for error in result["errors"]
            if error["index"] == 1
        ]
        self.assertEqual(len(dependent_errors), 1)
        self.assertIn("dependency", str(dependent_errors[0]["reason"]).lower())


    def test_logs_csv_formula_like_values_are_neutralized(self):
        from .views.logs import _csv_safe

        self.assertEqual(_csv_safe("=SUM(A1:A2)"), "'=SUM(A1:A2)")
        self.assertEqual(_csv_safe("normal text"), "normal text")


    def test_analytics_export_redacts_credential_like_urls_and_is_not_cached(self):
        PageView.objects.create(
            site=self.site,
            url="https://example.test/search?token=top-secret",
            path="/search?token=top-secret",
            method="GET",
            status_code=200,
        )
        response = self.client.get(
            reverse("paxalia:export", kwargs={"export_type": "pages"}),
            {"format": "json"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertNotIn("top-secret", response.content.decode("utf-8"))
        self.assertIn("[REDACTED]", response.content.decode("utf-8"))


    def test_single_model_export_frontend_contract_does_not_use_multimodel_state(self):
        from pathlib import Path

        root = Path(__file__).resolve().parent
        admin_js = (root / "static" / "paxalia" / "scripts" / "admin-center.js").read_text()
        single = admin_js.split("document.querySelectorAll('[data-paxalia-single-export]')", 1)[1]
        single = single.split("document.querySelectorAll('[data-paxalia-package-export]')", 1)[0]
        self.assertIn("singleExportProtected", single)
        self.assertIn("singleExportRequireEncryption", single)
        self.assertNotIn("selected.some", single)
        export_template = (root / "templates" / "paxalia" / "admin" / "package_export.html").read_text()
        self.assertIn("data-single-export-protected", export_template)
        self.assertIn("data-single-export-require-encryption", export_template)



class PaxaliaAdminFrontendContractTests(TestCase):
    def test_frontend_preferences_use_current_dashboard_contracts(self):
        from pathlib import Path
        root = Path(__file__).resolve().parent
        theme_js = (root / "static" / "paxalia" / "scripts" / "theme-manager.js").read_text()
        language_js = (root / "static" / "paxalia" / "scripts" / "language-manager.js").read_text()
        base_html = (root / "templates" / "paxalia" / "base.html").read_text()
        settings_html = (root / "templates" / "paxalia" / "settings.html").read_text()
        self.assertIn("data-analytics-theme", theme_js)
        self.assertNotIn("data-paxalia-theme", theme_js)
        self.assertIn("localStorage.setItem(STORAGE, next)", theme_js)
        self.assertIn("/i18n/setlang/", language_js)
        self.assertIn("name = 'language'", language_js)
        self.assertIn("admin_packages", base_html)
        self.assertIn("data-theme=", settings_html)
        self.assertIn("data-lang=", settings_html)
        admin_js = (root / "static" / "paxalia" / "scripts" / "admin-center.js").read_text()
        export_template = (root / "templates" / "paxalia" / "admin" / "package_export_center.html").read_text()
        localization_template = (root / "templates" / "paxalia" / "admin" / "model_localization.html").read_text()
        models_template = (root / "templates" / "paxalia" / "admin" / "models.html").read_text()
        self.assertIn("data-pa-app-toggle", admin_js)
        self.assertIn("data-pa-language-tab", admin_js)
        self.assertIn("submitExportAsDownload", admin_js)
        self.assertIn("Content-Disposition", admin_js)
        self.assertIn("submitter?.name === '_save' && submitter?.value === '1'", admin_js)
        self.assertIn("singleExportProtected", admin_js)
        self.assertIn("singleExportRequireEncryption", admin_js)
        single_export_template = (root / "templates" / "paxalia" / "admin" / "package_export.html").read_text()
        self.assertIn("data-single-export-protected", single_export_template)
        self.assertIn("data-single-export-require-encryption", single_export_template)
        self.assertIn("data-protected-required", single_export_template)
        self.assertIn("data-package-protected", export_template)
        self.assertIn("selected.some((box) => box.dataset.packageProtected === 'true')", admin_js)
        self.assertNotIn("root.dataset.singleExportProtected === 'true'", admin_js.split("document.querySelectorAll('[data-paxalia-package-export]')", 1)[1])
        self.assertIn("data-package-model-search", export_template)
        self.assertIn("data-package-protected", export_template)
        self.assertIn("data-generic-error", export_template)
        self.assertIn("translation_save", localization_template)
        self.assertIn("data-pa-model-search", models_template)
