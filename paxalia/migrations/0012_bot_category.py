from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('paxalia', '0011_notifications'),
    ]

    operations = [
        migrations.AddField(
            model_name='pageview',
            name='bot_category',
            field=models.CharField(
                blank=True, default='', db_index=True, max_length=20,
                choices=[
                    ('search_engine', 'Search engine'),
                    ('ai_crawler', 'AI crawler'),
                    ('social_preview', 'Social preview'),
                    ('seo_tool', 'SEO tool'),
                    ('unknown', 'Unknown bot'),
                    ('malicious', 'Malicious / scanner'),
                ],
                help_text=(
                    "Set once by the middleware at write time (see "
                    "bot_classification.py::classify_bot) — empty string means "
                    "not a bot. Existing rows from before this field was added "
                    "can be backfilled with `manage.py backfill_pageview_bot_category`."
                ),
            ),
        ),
        migrations.AlterField(
            model_name='pageview',
            name='is_bot',
            field=models.BooleanField(
                default=False, db_index=True,
                help_text=(
                    "True if the request path matched a known scanner/attack-probe "
                    "path (AnalyticsSettings.bot_paths), OR the User-Agent matched a "
                    "known crawler/bot pattern (see bot_classification.py) — this "
                    "field's meaning was widened in the phase that added "
                    "bot_category; see that module's BREAKING CHANGE note."
                ),
            ),
        ),
    ]
