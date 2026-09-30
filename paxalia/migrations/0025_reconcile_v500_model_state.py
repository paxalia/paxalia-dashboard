# Generated for Paxalia Dashboard v5.0.0 model-state reconciliation.
from django.db import migrations, models


LEGACY_PERMISSION_CODENAME = "view_server_files"
LEGACY_PERMISSION_NAME = "Can view Paxalia Server Files"


def remove_legacy_server_files_view_permission(apps, schema_editor):
    """Consolidate the historical duplicate into DashboardAccess.

    Some already-migrated development databases may contain
    ``view_server_files`` on both ContentTypes because an unreleased 0023
    state previously defined the section permission on ServerFileOperation.
    Preserve all existing user/group assignments while moving them to the
    canonical DashboardAccess permission, then delete only the duplicate.
    """
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")
    dashboard_ct = ContentType.objects.filter(
        app_label="paxalia",
        model="dashboardaccess",
    ).first()
    operation_ct = ContentType.objects.filter(
        app_label="paxalia",
        model="serverfileoperation",
    ).first()
    if dashboard_ct is None or operation_ct is None:
        return

    canonical, _ = Permission.objects.get_or_create(
        content_type=dashboard_ct,
        codename=LEGACY_PERMISSION_CODENAME,
        defaults={"name": LEGACY_PERMISSION_NAME},
    )
    legacy = Permission.objects.filter(
        content_type=operation_ct,
        codename=LEGACY_PERMISSION_CODENAME,
    ).first()
    if legacy is None or legacy.pk == canonical.pk:
        return

    for user in legacy.user_set.all().iterator():
        canonical.user_set.add(user)
    for group in legacy.group_set.all().iterator():
        canonical.group_set.add(group)
    legacy.delete()


def preserve_current_permission_state_on_reverse(apps, schema_editor):
    """0025 reversal must not recreate an intentionally removed duplicate."""
    return


class Migration(migrations.Migration):
    dependencies = [
        ("paxalia", "0024_operations"),
    ]

    operations = [
        # Clean the stale duplicate first. This is intentionally retained as a
        # data migration instead of rewriting 0023, because 0023 may already
        # be recorded as applied in development or staging databases.
        migrations.RunPython(
            remove_legacy_server_files_view_permission,
            preserve_current_permission_state_on_reverse,
        ),
        migrations.AlterField(
            model_name="uptimeincident",
            name="cause",
            field=models.CharField(blank=True, max_length=500),
        ),
        migrations.AlterField(
            model_name="uptimemonitor",
            name="check_interval_minutes",
            field=models.PositiveIntegerField(default=5),
        ),
        migrations.AlterField(
            model_name="uptimemonitor",
            name="is_active",
            field=models.BooleanField(db_index=True, default=True),
        ),
    ]
