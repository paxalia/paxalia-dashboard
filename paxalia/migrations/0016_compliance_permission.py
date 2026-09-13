from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('paxalia', '0015_ops_monitoring'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='dashboardaccess',
            options={
                'default_permissions': (),
                'managed': False,
                'permissions': [
                    ('view_billing', 'Can view Billing section'),
                    ('view_security', 'Can view Security Center'),
                    ('view_backups', 'Can view Backups section'),
                    ('view_sites', 'Can view Sites section'),
                    ('view_server', 'Can view Server monitoring'),
                    ('view_compliance', 'Can view Compliance tools'),
                ],
            },
        ),
    ]
