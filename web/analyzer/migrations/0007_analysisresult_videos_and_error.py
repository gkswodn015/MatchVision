from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('analyzer', '0006_analysisresult_goal_records_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='match',
            name='status',
            field=models.CharField(
                choices=[
                    ('uploaded', '업로드 완료'),
                    ('analyzing', '분석 중'),
                    ('completed', '분석 완료'),
                    ('failed', '분석 실패'),
                ],
                default='uploaded',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='analysisresult',
            name='analysis_error',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='analysisresult',
            name='detected_video',
            field=models.FileField(blank=True, upload_to='analysis_results/'),
        ),
        migrations.AddField(
            model_name='analysisresult',
            name='topview_video',
            field=models.FileField(blank=True, upload_to='analysis_results/'),
        ),
    ]
