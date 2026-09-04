from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0003_csp_violations'),
    ]

    operations = [
        migrations.AddField(
            model_name='pageview',
            name='is_api',
            field=models.BooleanField(
                db_index=True, default=False,
                help_text=(
                    "True if the request path matched API_PATH_PREFIX. Set once by "
                    "the middleware at write time so every view can filter page "
                    "views and API calls apart with a plain field lookup instead of "
                    "re-matching the path prefix in every query. Existing rows from "
                    "before this field was added can be backfilled with "
                    "`manage.py backfill_pageview_is_api`."
                ),
            ),
        ),
    ]
