from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('analytics', '0018_fix_dailysitestats_duplicates'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sharelink',
            name='password_hash',
            field=models.CharField(
                blank=True,
                help_text='Django password hash. Blank means no password required.',
                max_length=128,
            ),
        ),
    ]
