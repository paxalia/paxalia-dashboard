from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0007_goals_funnels_segments_annotations'),
    ]

    operations = [
        migrations.CreateModel(
            name='DashboardAccess',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ],
            options={
                'permissions': [
                    ('view_billing', 'Can view Billing section'),
                    ('view_security', 'Can view Security Center'),
                    ('view_backups', 'Can view Backups section'),
                    ('view_sites', 'Can view Sites section'),
                    ('view_server', 'Can view Server monitoring'),
                ],
                'managed': False,
                'default_permissions': (),
            },
        ),
    ]
