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