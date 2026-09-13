import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('paxalia', '0014_uptime_monitoring'),
    ]

    operations = [
        migrations.CreateModel(
            name='ServerMetricSnapshot',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('recorded_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('cpu_percent', models.FloatField()),
                ('memory_percent', models.FloatField()),
                ('disk_io_read_bytes', models.BigIntegerField(default=0)),
                ('disk_io_write_bytes', models.BigIntegerField(default=0)),
                ('network_in_bytes', models.BigIntegerField(default=0)),
                ('network_out_bytes', models.BigIntegerField(default=0)),
            ],
            options={
                'ordering': ['-recorded_at'],
            },
        ),
        migrations.CreateModel(
            name='SlowQuery',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sql', models.TextField()),
                ('duration_ms', models.FloatField(db_index=True)),
                ('path', models.CharField(blank=True, max_length=255)),
                ('created_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
            ],
            options={
                'verbose_name': 'Slow Query',
                'verbose_name_plural': 'Slow Queries',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Deployment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version', models.CharField(blank=True, help_text='Git SHA, tag, or version string — whatever CI passes.', max_length=100)),
                ('notes', models.TextField(blank=True)),
                ('deployed_at', models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ('annotation', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='deployment', to='paxalia.chartannotation')),
                ('site', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='deployments', to='paxalia.site')),
            ],
            options={
                'ordering': ['-deployed_at'],
            },
        ),
    ]
