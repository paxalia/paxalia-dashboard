from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Flips AnalyticsSettings.anonymize_ip's default from True to False.

    Deliberately does NOT touch existing AnalyticsSettings rows: a default
    only affects new rows created without the field set. Sites that already
    have a settings row keep whatever value they already had (True, unless
    someone had already turned it off) — this migration only changes what
    a *fresh* install gets. If you want an existing deployment to switch to
    raw (non-hashed) IP storage too, flip the "Anonymize IP addresses"
    toggle in the dashboard's Settings page after upgrading.
    """

    dependencies = [
        ('analytics', '0004_pageview_is_api'),
    ]

    operations = [
        migrations.AlterField(
            model_name='analyticssettings',
            name='anonymize_ip',
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Hash IP addresses with SHA256 before storing. Off by "
                    "default — turn on if you want visitor IPs anonymized."
                ),
            ),
        ),
    ]