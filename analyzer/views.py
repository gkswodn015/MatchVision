from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from .forms import SignUpForm, MatchUploadForm


def main(request):
    return render(request, 'analyzer/main.html')


def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)

        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('main')
    else:
        form = SignUpForm()

    return render(request, 'registration/signup.html', {'form': form})


@login_required
def upload_match(request):
    if request.method == 'POST':
        form = MatchUploadForm(request.POST, request.FILES)

        if form.is_valid():
            match = form.save(commit=False)
            match.uploaded_by = request.user
            match.status = 'uploaded'
            match.save()
            return redirect('main')
    else:
        form = MatchUploadForm()

    return render(request, 'analyzer/upload.html', {'form': form})