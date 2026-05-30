from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from .forms import SignUpForm, MatchUploadForm
from .models import Match


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
            return redirect('match_list')
    else:
        form = MatchUploadForm()

    return render(request, 'analyzer/upload.html', {'form': form})


@login_required
def match_list(request):
    matches = Match.objects.filter(uploaded_by=request.user).order_by('-created_at')
    return render(request, 'analyzer/match_list.html', {'matches': matches})


@login_required
def request_analysis(request, match_id):
    match = get_object_or_404(Match, id=match_id, uploaded_by=request.user)

    if request.method == 'POST':
        match.status = 'analyzing'
        match.save()
        return redirect('analysis_status', match_id=match.id)

    return render(request, 'analyzer/analysis_request.html', {'match': match})


@login_required
def analysis_status(request, match_id):
    match = get_object_or_404(Match, id=match_id, uploaded_by=request.user)
    return render(request, 'analyzer/analysis_status.html', {'match': match})