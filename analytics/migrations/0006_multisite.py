import uuid

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0005_flip_anonymize_ip_default'),
    ]

    operations = [
        migrations.CreateModel(
            name='Site',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('domain', models.CharField(
                    db_index=True, max_length=255, unique=True,
                    help_text="Hostname only, no scheme/port, e.g. 'example.com'.")),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                'verbose_name': 'Site',
                'verbose_name_plural': 'Sites',
                'ordering': ['name'],
            },
        ),
        migrations.AddField(
            model_name='analyticssettings',
            name='search_query_params',
            field=models.TextField(
                blank=True, default='q\nsearch\nquery',
                help_text=(
                    "One query-string parameter name per line. A request whose "
                    "URL includes any of these params is logged as a site-search "
                    "event (see AnalyticsEvent, category='site_search')."
                ),
            ),
        ),
        migrations.AddField(
            model_name='pageview',
            name='site',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='page_views', to='analytics.site',
                help_text="Resolved from the request's hostname. Null if the host didn't match any registered Site."
            ),
        ),
        migrations.AddField(
            model_name='analyticsevent',
            name='site',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='events', to='analytics.site',
            ),
        ),
        migrations.AddField(
            model_name='cspviolation',
            name='site',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name='csp_violations', to='analytics.site',
            ),
        ),
        migrations.AddField(
            model_name='dailysitestats',
            name='site',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.CASCADE,
                related_name='daily_stats', to='analytics.site',
            ),
        ),
        migrations.AlterField(
            model_name='dailysitestats',
            name='date',
            field=models.DateField(db_index=True),
        ),
        migrations.AlterUniqueTogether(
            name='dailysitestats',
            unique_together={('site', 'date')},
        ),
    ]
