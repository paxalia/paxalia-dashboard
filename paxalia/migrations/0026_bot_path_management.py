from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("paxalia", "0025_reconcile_v500_model_state"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="dashboardaccess",
            options={
                "managed": False,
                "default_permissions": (),
                "permissions": [
                    ("view_billing", "Can view Billing section"),
                    ("view_security", "Can view Security Center"),
                    ("view_backups", "Can view Backups section"),
                    ("view_sites", "Can view Sites section"),
                    ("view_server", "Can view Server monitoring"),
                    ("view_compliance", "Can view Compliance tools"),
                    ("view_logs", "Can view Paxalia Logs"),
                    ("view_server_files", "Can view Paxalia Server Files"),
                    ("view_availability", "Can view Paxalia Availability"),
                    ("view_transfers", "Can view Paxalia Transfer Center"),
                    ("create_transfers", "Can create Paxalia transfers"),
                    ("manage_availability", "Can manage Paxalia Availability"),
                    ("view_incidents", "Can view Paxalia Availability incidents"),
                    ("manage_resource_policies", "Can manage Paxalia resource policies"),
                    ("manage_bot_paths", "Can manage Bot/Scanner path rules and cleanup"),
                ],
            },
        ),
    ]
