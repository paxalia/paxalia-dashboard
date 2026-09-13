from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('paxalia', '0016_compliance_permission'),
    ]

    operations = [
        migrations.AddField(
            model_name='dailysitestats',
            name='imported_from',
            field=models.CharField(
                blank=True, default='', max_length=20,
                choices=[('ga', 'Google Analytics'), ('plausible', 'Plausible'), ('csv', 'Generic CSV')],
                help_text="Set by manage.py / the Data Import page when this row came from a historical CSV import "
                          "rather than this package's own live tracking. Empty for every normally-tracked day.",
            ),
        ),
    ]
