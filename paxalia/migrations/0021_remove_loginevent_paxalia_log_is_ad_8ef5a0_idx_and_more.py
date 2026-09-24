# Consolidated development migration: replaces the earlier 0021 + 0022 index
# reconciliation chain with one final schema-state migration.
#
# IMPORTANT: this is intended for the unreleased v4 development branch while
# the local PostgreSQL test database is recreated from scratch. Do not rewrite
# an already-released/applied migration in production; publish a new migration
# instead.

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        (
            "paxalia",
            "0020_paxalia_observability",
        ),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # LoginEvent: remove the pre-v4 ascending composite indexes and replace
        # them with the actual dashboard query order (-created_at).
        migrations.RemoveIndex(
            model_name="loginevent",
            name="paxalia_log_is_ad_8ef5a0_idx",
        ),
        migrations.RemoveIndex(
            model_name="loginevent",
            name="paxalia_log_event_t_c37d22_idx",
        ),
        migrations.RemoveIndex(
            model_name="loginevent",
            name="paxalia_log_failur_429dee_idx",
        ),
        migrations.RemoveIndex(
            model_name="paxalialoggroup",
            name="paxalia_plg_source_9f07a3_idx",
        ),
        migrations.RemoveIndex(
            model_name="paxalialoggroup",
            name="paxalia_plg_severit_1e7f8a_idx",
        ),
        migrations.RemoveIndex(
            model_name="paxalialoggroup",
            name="paxalia_plg_category_79dc5c_idx",
        ),

        # Preserve the useful existing LoginEvent indexes, but give them the
        # stable Paxalia names used by the v4 model state.
        migrations.RenameIndex(
            model_name="loginevent",
            new_name="paxalia_log_user_id_a63a3f_idx",
            old_name="analytics_l_user_id_9d1a5e_idx",
        ),
        migrations.RenameIndex(
            model_name="loginevent",
            new_name="paxalia_log_result_9e90aa_idx",
            old_name="analytics_l_result_5f3c2a_idx",
        ),

        # PaxaliaLogEvent composite indexes: consolidate the generated names
        # from the original observability migration into the final stable names.
        migrations.RenameIndex(
            model_name="paxalialogevent",
            new_name="paxalia_pax_timesta_037ce2_idx",
            old_name="paxalia_plo_timest_1e6d6f_idx",
        ),
        migrations.RenameIndex(
            model_name="paxalialogevent",
            new_name="paxalia_pax_source_a542fb_idx",
            old_name="paxalia_plo_source_3e4ce5_idx",
        ),
        migrations.RenameIndex(
            model_name="paxalialogevent",
            new_name="paxalia_pax_traffic_c4b81c_idx",
            old_name="paxalia_plo_traffic_4a5f48_idx",
        ),
        migrations.RenameIndex(
            model_name="paxalialogevent",
            new_name="paxalia_pax_request_c74a7d_idx",
            old_name="paxalia_plo_request_5e75ae_idx",
        ),
        migrations.RenameIndex(
            model_name="paxalialogevent",
            new_name="paxalia_pax_correla_924d68_idx",
            old_name="paxalia_plo_correlat_4f57d6_idx",
        ),
        migrations.RenameIndex(
            model_name="paxalialogevent",
            new_name="paxalia_pax_excepti_933c37_idx",
            old_name="paxalia_plo_exceptio_6c9d5d_idx",
        ),
        migrations.RenameIndex(
            model_name="paxalialogevent",
            new_name="paxalia_pax_fingerp_3a10aa_idx",
            old_name="paxalia_plo_fingerp_09d9df_idx",
        ),

        # Final LoginEvent composite indexes.
        # UptimeCheck: preserve the existing v3 database index while
        # aligning its physical name with the stable v4 model state.
        migrations.RenameIndex(
            model_name="uptimecheck",
            old_name="analytics_u_monitor_1a2b3c_idx",
            new_name="paxalia_upt_monitor_d38f8e_idx",
        ),

        migrations.AddIndex(
            model_name="loginevent",
            index=models.Index(
                fields=["is_admin", "-created_at"],
                name="paxalia_log_is_admi_119e3b_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="loginevent",
            index=models.Index(
                fields=["event_type", "-created_at"],
                name="paxalia_log_event_t_7d5a3e_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="loginevent",
            index=models.Index(
                fields=["failure_category", "-created_at"],
                name="paxalia_log_failure_8314a0_idx",
            ),
        ),

        # Final PaxaliaLogGroup composite indexes.
        migrations.AddIndex(
            model_name="paxalialoggroup",
            index=models.Index(
                fields=["source", "-last_seen"],
                name="paxalia_pax_source_b2919b_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="paxalialoggroup",
            index=models.Index(
                fields=["severity", "-last_seen"],
                name="paxalia_pax_severit_8f2790_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="paxalialoggroup",
            index=models.Index(
                fields=["category", "-last_seen"],
                name="paxalia_pax_categor_457dd8_idx",
            ),
        ),

        # These IDs changed from AutoField-style state to BigAutoField-style
        # state under the package's current default_auto_field configuration.
        migrations.AlterField(
            model_name="deployment",
            name="id",
            field=models.BigAutoField(
                auto_created=True,
                primary_key=True,
                serialize=False,
                verbose_name="ID",
            ),
        ),
        migrations.AlterField(
            model_name="servermetricsnapshot",
            name="id",
            field=models.BigAutoField(
                auto_created=True,
                primary_key=True,
                serialize=False,
                verbose_name="ID",
            ),
        ),
        migrations.AlterField(
            model_name="slowquery",
            name="id",
            field=models.BigAutoField(
                auto_created=True,
                primary_key=True,
                serialize=False,
                verbose_name="ID",
            ),
        ),
        migrations.AlterField(
            model_name="uptimecheck",
            name="id",
            field=models.BigAutoField(
                auto_created=True,
                primary_key=True,
                serialize=False,
                verbose_name="ID",
            ),
        ),
        migrations.AlterField(
            model_name="uptimeincident",
            name="id",
            field=models.BigAutoField(
                auto_created=True,
                primary_key=True,
                serialize=False,
                verbose_name="ID",
            ),
        ),
        migrations.AlterField(
            model_name="uptimemonitor",
            name="id",
            field=models.BigAutoField(
                auto_created=True,
                primary_key=True,
                serialize=False,
                verbose_name="ID",
            ),
        ),

        migrations.AlterModelOptions(
            name="dashboardaccess",
            options={
                "default_permissions": (),
                "managed": False,
                "permissions": [
                    ("view_billing", "Can view Billing section"),
                    ("view_security", "Can view Security Center"),
                    ("view_backups", "Can view Backups section"),
                    ("view_sites", "Can view Sites section"),
                    ("view_server", "Can view Server monitoring"),
                    ("view_compliance", "Can view Compliance tools"),
                    ("view_logs", "Can view Paxalia Logs"),
                ],
            },
        ),
    ]
