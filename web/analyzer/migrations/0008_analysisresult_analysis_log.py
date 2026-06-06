from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analyzer', '0007_analysisresult_videos_and_error'),
    ]

    operations = [
        migrations.AddField(
            model_name='analysisresult',
            name='analysis_log',
            field=models.TextField(blank=True),
        ),
    ]
