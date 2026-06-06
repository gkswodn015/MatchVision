from django.db import models
from django.contrib.auth.models import User


class Team(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    league = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Player(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField(max_length=100)
    jersey_number = models.PositiveIntegerField(null=True, blank=True)
    position = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.name


class Match(models.Model):
    STATUS_CHOICES = [
        ('uploaded', '업로드 완료'),
        ('analyzing', '분석 중'),
        ('completed', '분석 완료'),
        ('failed', '분석 실패'),
    ]

    title = models.CharField(max_length=100)
    video_name = models.CharField(max_length=100, default='전반전')
    video = models.FileField(upload_to='videos/')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)

    home_team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='home_matches'
    )
    away_team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='away_matches'
    )

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
    highest_speed = models.FloatField(default=0)

    match_info_url = models.URLField(blank=True)
    score_info = models.CharField(max_length=100, blank=True)
    goal_records = models.TextField(blank=True)
    lineup_info = models.TextField(blank=True)
    team_stats = models.TextField(blank=True)

    detected_video = models.FileField(upload_to='analysis_results/', blank=True)
    topview_video = models.FileField(upload_to='analysis_results/', blank=True)
    analysis_error = models.TextField(blank=True)
    analysis_log = models.TextField(blank=True)
    analyzer_team_ids = models.TextField(blank=True)

    report_text = models.TextField(blank=True)
    is_saved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.match.title} 분석 리포트'


class PlayerResult(models.Model):
    analysis = models.ForeignKey(
        AnalysisResult,
        on_delete=models.CASCADE,
        related_name='players'
    )
    player = models.ForeignKey(Player, on_delete=models.SET_NULL, null=True, blank=True)
    track_id = models.PositiveIntegerField(null=True, blank=True)
    track_group = models.CharField(max_length=20, blank=True)
    player_name = models.CharField(max_length=50)
    team_name = models.CharField(max_length=50)
    distance = models.FloatField(default=0)
    speed = models.FloatField(default=0)
    max_speed = models.FloatField(default=0)

    def __str__(self):
        return f'{self.team_name} - {self.player_name}'
