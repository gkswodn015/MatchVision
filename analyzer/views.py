from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from .forms import SignUpForm, MatchUploadForm, MatchEditForm
from .models import Match, AnalysisResult, PlayerResult


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
def match_detail(request, match_id):
    match = get_object_or_404(Match, id=match_id, uploaded_by=request.user)
    return render(request, 'analyzer/match_detail.html', {'match': match})


def create_dummy_analysis_result(match):
    analysis, created = AnalysisResult.objects.get_or_create(
        match=match,
        defaults={
            'possession_team_a': 55.0,
            'possession_team_b': 45.0,
            'report_text': (
                'YOLO와 OpenCV 분석 결과를 기반으로 생성된 경기 분석 리포트입니다. '
                '현재는 실제 분석 알고리즘 연결 전 단계이므로 웹 기능 확인을 위한 더미 데이터입니다.'
            ),
        }
    )

    if created:
        PlayerResult.objects.create(
            analysis=analysis,
            player_name='player_1',
            team_name='Team A',
            distance=5.2,
            speed=12.3
        )
        PlayerResult.objects.create(
            analysis=analysis,
            player_name='player_2',
            team_name='Team A',
            distance=4.8,
            speed=10.7
        )
        PlayerResult.objects.create(
            analysis=analysis,
            player_name='player_3',
            team_name='Team B',
            distance=5.6,
            speed=13.1
        )
        PlayerResult.objects.create(
            analysis=analysis,
            player_name='player_4',
            team_name='Team B',
            distance=4.5,
            speed=9.8
        )

    match.status = 'completed'
    match.save()

    return analysis


@login_required
def request_analysis(request, match_id):
    match = get_object_or_404(Match, id=match_id, uploaded_by=request.user)

    if request.method == 'POST':
        create_dummy_analysis_result(match)
        return redirect('analysis_report', match_id=match.id)

    return render(request, 'analyzer/analysis_request.html', {'match': match})


@login_required
def analysis_status(request, match_id):
    match = get_object_or_404(Match, id=match_id, uploaded_by=request.user)
    return render(request, 'analyzer/analysis_status.html', {'match': match})


@login_required
def generate_report(request, match_id):
    match = get_object_or_404(Match, id=match_id, uploaded_by=request.user)

    if request.method == 'POST':
        create_dummy_analysis_result(match)
        return redirect('analysis_report', match_id=match.id)

    return redirect('analysis_status', match_id=match.id)


@login_required
def analysis_report(request, match_id):
    match = get_object_or_404(Match, id=match_id, uploaded_by=request.user)
    analysis = get_object_or_404(AnalysisResult, match=match)
    players = analysis.players.all()

    report_settings = request.session.get('report_settings', {
        'show_tracking': True,
        'show_path': True,
        'show_topview': True,
        'show_speed': True,
        'show_summary': True,
    })

    return render(request, 'analyzer/analysis_report.html', {
        'match': match,
        'analysis': analysis,
        'players': players,
        'report_settings': report_settings,
    })


@login_required
def match_manage(request):
    matches = Match.objects.filter(uploaded_by=request.user).order_by('-created_at')
    return render(request, 'analyzer/match_manage.html', {'matches': matches})


@login_required
def edit_match(request, match_id):
    match = get_object_or_404(Match, id=match_id, uploaded_by=request.user)

    if request.method == 'POST':
        form = MatchEditForm(request.POST, instance=match)

        if form.is_valid():
            form.save()
            return redirect('match_manage')
    else:
        form = MatchEditForm(instance=match)

    return render(request, 'analyzer/match_edit.html', {
        'form': form,
        'match': match,
    })


@login_required
def delete_match(request, match_id):
    match = get_object_or_404(Match, id=match_id, uploaded_by=request.user)

    if request.method == 'POST':
        match.video.delete(save=False)
        match.delete()
        return redirect('match_manage')

    return render(request, 'analyzer/match_delete.html', {'match': match})


@login_required
def team_player_manage(request):
    analyses = AnalysisResult.objects.filter(
        match__uploaded_by=request.user
    ).order_by('-created_at')

    return render(request, 'analyzer/team_player_manage.html', {
        'analyses': analyses,
    })


@login_required
def edit_team_players(request, match_id):
    match = get_object_or_404(Match, id=match_id, uploaded_by=request.user)
    analysis = get_object_or_404(AnalysisResult, match=match)
    players = analysis.players.all()

    if request.method == 'POST':
        for player in players:
            player.player_name = request.POST.get(
                f'player_name_{player.id}',
                player.player_name
            )
            player.team_name = request.POST.get(
                f'team_name_{player.id}',
                player.team_name
            )
            player.save()

        return redirect('analysis_report', match_id=match.id)

    return render(request, 'analyzer/team_player_edit.html', {
        'match': match,
        'analysis': analysis,
        'players': players,
    })


@login_required
def settings_page(request):
    current_settings = request.session.get('report_settings', {
        'show_tracking': True,
        'show_path': True,
        'show_topview': True,
        'show_speed': True,
        'show_summary': True,
    })

    if request.method == 'POST':
        current_settings = {
            'show_tracking': 'show_tracking' in request.POST,
            'show_path': 'show_path' in request.POST,
            'show_topview': 'show_topview' in request.POST,
            'show_speed': 'show_speed' in request.POST,
            'show_summary': 'show_summary' in request.POST,
        }

        request.session['report_settings'] = current_settings
        return redirect('settings_page')

    return render(request, 'analyzer/settings.html', {
        'settings': current_settings,
    })