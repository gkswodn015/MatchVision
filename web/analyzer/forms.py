from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Match, Team, Player


class SignUpForm(UserCreationForm):
    first_name = forms.CharField(
        label='이름',
        widget=forms.TextInput(attrs={'placeholder': '이름을 입력하세요'})
    )
    username = forms.CharField(
        label='아이디',
        widget=forms.TextInput(attrs={'placeholder': '아이디를 입력하세요'})
    )
    email = forms.EmailField(
        label='이메일',
        widget=forms.EmailInput(attrs={'placeholder': '이메일을 입력하세요'})
    )
    password1 = forms.CharField(
        label='비밀번호',
        widget=forms.PasswordInput(attrs={'placeholder': '비밀번호를 입력하세요'})
    )
    password2 = forms.CharField(
        label='비밀번호 확인',
        widget=forms.PasswordInput(attrs={'placeholder': '비밀번호를 다시 입력하세요'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'username', 'email', 'password1', 'password2']


class MatchUploadForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ['title', 'video_name', 'video']
        labels = {
            'title': '경기 이름',
            'video_name': '영상 이름',
            'video': '경기 영상 파일',
        }
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': '예: 2026-04-01_홈팀 vs 원정팀'
            }),
            'video_name': forms.TextInput(attrs={
                'placeholder': '예: 전반전, 후반전, 01번 클립'
            }),
        }


class MatchEditForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ['title', 'video_name']
        labels = {
            'title': '경기 이름',
            'video_name': '영상 이름',
        }
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': '수정할 경기 이름을 입력하세요'
            }),
            'video_name': forms.TextInput(attrs={
                'placeholder': '수정할 영상 이름을 입력하세요'
            }),
        }

class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ['name', 'league']
        labels = {
            'name': '팀 이름',
            'league': '소속 리그',
        }
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': '예: XX FC'}),
            'league': forms.TextInput(attrs={'placeholder': '예: X 리그'}),
        }


class PlayerForm(forms.ModelForm):
    class Meta:
        model = Player
        fields = ['team', 'jersey_number', 'position', 'name']
        labels = {
            'team': '소속 팀',
            'jersey_number': '등번호',
            'position': '포지션',
            'name': '선수 이름',
        }
        widgets = {
            'position': forms.TextInput(attrs={'placeholder': '예: FW, MF, DF, GK'}),
            'name': forms.TextInput(attrs={'placeholder': '선수 이름'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            self.fields['team'].queryset = Team.objects.filter(user=user)