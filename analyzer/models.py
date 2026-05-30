from django.db import models
from django.contrib.auth.models import User


class Match(models.Model):
    STATUS_CHOICES = [
        ('uploaded', '업로드 완료'),
        ('analyzing', '분석 중'),
        ('completed', '분석 완료'),
    ]

    title = models.CharField(max_length=100)
    video = models.FileField(upload_to='videos/')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='uploaded'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class AnalysisResult(models.Model):
    match = models.OneToOneField(
        Match,
        on_delete=models.CASCADE,
        related_name='analysis_result'
    )
    possession_team_a = models.FloatField(default=0)
    possession_team_b = models.FloatField(default=0)
    report_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.match.title} 분석 리포트'


class PlayerResult(models.Model):
    analysis = models.ForeignKey(
        AnalysisResult,
        on_delete=models.CASCADE,
        related_name='players'
    )
    player_name = models.CharField(max_length=50)
    team_name = models.CharField(max_length=50)
    distance = models.FloatField(default=0)
    speed = models.FloatField(default=0)

    def __str__(self):
        return f'{self.team_name} - {self.player_name}'