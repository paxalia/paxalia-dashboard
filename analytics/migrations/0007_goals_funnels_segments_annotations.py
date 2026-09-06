import uuid

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('analytics', '0006_multisite'),
    ]

    operations = [
        migrations.AddField(
            model_name='pageview', name='utm_source',
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
        migrations.AddField(
            model_name='pageview', name='utm_medium',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='pageview', name='utm_campaign',
            field=models.CharField(blank=True, db_index=True, max_length=255),
        ),
        migrations.AddField(
            model_name='pageview', name='utm_term',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='pageview', name='utm_content',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.CreateModel(
            name='Goal',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('goal_type', models.CharField(choices=[('page', 'Page visited'), ('event', 'Event fired')], max_length=10)),
                ('match_value', models.CharField(
                    help_text="Path for a page goal (e.g. '/thank-you/'), or 'category:action' for an event goal (e.g. 'signup:completed').",
                    max_length=255)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('site', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='goals', to='analytics.site')),
            ],
            options={'verbose_name': 'Goal', 'verbose_name_plural': 'Goals', 'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='Funnel',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('site', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='funnels', to='analytics.site')),
            ],
            options={'verbose_name': 'Funnel', 'verbose_name_plural': 'Funnels', 'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='FunnelStep',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('order', models.PositiveIntegerField()),
                ('name', models.CharField(max_length=255)),
                ('step_type', models.CharField(choices=[('page', 'Page visited'), ('event', 'Event fired')], max_length=10)),
                ('match_value', models.CharField(help_text='Same format as Goal.match_value.', max_length=255)),
                ('funnel', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='steps', to='analytics.funnel')),
            ],
            options={'verbose_name': 'Funnel Step', 'verbose_name_plural': 'Funnel Steps', 'ordering': ['funnel', 'order']},
        ),
        migrations.AlterUniqueTogether(
            name='funnelstep',
            unique_together={('funnel', 'order')},
        ),
        migrations.CreateModel(
            name='Segment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=255)),
                ('filters', models.JSONField(blank=True, default=dict)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('site', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='segments', to='analytics.site')),
            ],
            options={'verbose_name': 'Segment', 'verbose_name_plural': 'Segments', 'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='ChartAnnotation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('date', models.DateField(db_index=True)),
                ('label', models.CharField(max_length=255)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
                ('site', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='annotations', to='analytics.site')),
            ],
            options={'verbose_name': 'Chart Annotation', 'verbose_name_plural': 'Chart Annotations', 'ordering': ['-date']},
        ),
    ]
