from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Match


class SignUpForm(UserCreationForm):
    username = forms.CharField(
        label='아이디',
        widget=forms.TextInput(attrs={'placeholder': '아이디를 입력하세요'})
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
        fields = ['username', 'password1', 'password2']


class MatchUploadForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ['title', 'video']
        labels = {
            'title': '경기명',
            'video': '경기 영상 파일',
        }
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': '예: 단국대 vs OO대 경기'
            }),
        }


class MatchEditForm(forms.ModelForm):
    class Meta:
        model = Match
        fields = ['title']
        labels = {
            'title': '경기명',
        }
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': '수정할 경기명을 입력하세요'
            }),
        }