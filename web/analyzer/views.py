import threading

from django.db import close_old_connections
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .forms import (
    SignUpForm,
    MatchUploadForm,
    MatchEditForm,
    TeamForm,
    PlayerForm,
)
from .models import Match, AnalysisResult, PlayerResult, Team, Player
from .services.analyzer_runner import AnalyzerRunError, import_analyzer_result_videos, run_analyzer_for_match


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


@login_required
def video_analysis(request, match_id):
    match = get_object_or_404(Match, id=match_id, uploaded_by=request.user)
    teams = Team.objects.filter(user=request.user).order_by('name')

    return render(request, 'analyzer/video_analysis.html', {
        'match': match,
        'teams': teams,
    })


def create_dummy_analysis_result(match):
    home_name = match.home_team.name if match.home_team else 'Home Team'
    away_name = match.away_team.name if match.away_team else 'Away Team'

    analysis, created = AnalysisResult.objects.get_or_create(
        match=match,
        defaults={
            'possession_team_a': 55.0,
            'possession_team_b': 45.0,
            'highest_speed': 34.1,
            'score_info': f'{home_name} 2 : 1 {away_name}',
            'goal_records': (
                f'{home_name}: 전반 23분 득점, 후반 12분 득점\n'
                f'{away_name}: 후반 31분 득점'
            ),
            'lineup_info': (
                f'{home_name}: player_1, player_2\n'
                f'{away_name}: player_3, player_4'
            ),
            'team_stats': (
                f'{home_name} 점유율 55%, 슈팅 8회, 패스 성공률 82%\n'
                f'{away_name} 점유율 45%, 슈팅 6회, 패스 성공률 78%'
            ),
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
            team_name=home_name,
            distance=11.2,
            speed=8.4,
            max_speed=34.1
        )
        PlayerResult.objects.create(
            analysis=analysis,
            player_name='player_2',
            team_name=home_name,
            distance=9.8,
            speed=7.9,
            max_speed=30.5
        )
        PlayerResult.objects.create(
            analysis=analysis,
            player_name='player_3',
            team_name=away_name,
            distance=10.5,
            speed=8.1,
            max_speed=32.2
        )
        PlayerResult.objects.create(
            analysis=analysis,
            player_name='player_4',
            team_name=away_name,
            distance=8.7,
            speed=7.4,
            max_speed=28.9
        )

    match.status = 'completed'
    match.save()

    return analysis


def create_analyzer_analysis_result(match):
    home_name = match.home_team.name if match.home_team else 'Home Team'
    away_name = match.away_team.name if match.away_team else 'Away Team'

    analysis, _ = AnalysisResult.objects.get_or_create(match=match)
    analysis.analysis_error = ''
    analysis.analysis_log = ''
    analysis.report_text = (
        'Analyzer/main.py를 실행해 객체 탐지 영상과 탑뷰 변환 영상을 생성했습니다. '
        '분석 과정은 기존 Analyzer의 OpenCV 창과 로그를 그대로 사용합니다.'
    )
    analysis.score_info = f'{home_name} vs {away_name}'

    def append_log(message: str) -> None:
        AnalysisResult.objects.filter(id=analysis.id).update(
            analysis_log=analysis.analysis_log + message + '\n'
        )
        analysis.analysis_log += message + '\n'

    result = run_analyzer_for_match(match, log_callback=append_log)
    analysis.detected_video.name = result.detected_video_name
    analysis.topview_video.name = result.topview_video_name
    analysis.save()

    match.status = 'completed'
    match.save()

    return analysis


def start_analysis_job(match_id: int) -> None:
    thread = threading.Thread(
        target=_run_analysis_job,
        args=(match_id,),
        daemon=True,
    )
    thread.start()


def _run_analysis_job(match_id: int) -> None:
    close_old_connections()
    try:
        match = Match.objects.select_related('home_team', 'away_team').get(id=match_id)
        create_analyzer_analysis_result(match)
    except Exception as exc:
        try:
            match = Match.objects.get(id=match_id)
            analysis, _ = AnalysisResult.objects.get_or_create(match=match)
            analysis.analysis_error = str(exc)
            analysis.report_text = 'Analyzer 실행 중 오류가 발생했습니다.'
            analysis.save()

            match.status = 'failed'
            match.save(update_fields=['status'])
        finally:
            close_old_connections()


@login_required
def request_analysis(request, match_id):
    match = get_object_or_404(Match, id=match_id, uploaded_by=request.user)

    if request.method == 'POST':
        home_team_id = request.POST.get('home_team')
        away_team_id = request.POST.get('away_team')

        if home_team_id:
            match.home_team = Team.objects.filter(
                id=home_team_id,
                user=request.user
            ).first()

        if away_team_id:
            match.away_team = Team.objects.filter(
                id=away_team_id,
                user=request.user
            ).first()

        match.status = 'analyzing'
        match.save()

        start_analysis_job(match.id)
        messages.info(request, '분석 요청이 접수되었습니다. 완료되면 리포트에서 결과 영상을 확인할 수 있습니다.')
        return redirect('analysis_status', match_id=match.id)

    return render(request, 'analyzer/analysis_request.html', {'match': match})


@login_required
def analysis_status(request, match_id):
    match = get_object_or_404(Match, id=match_id, uploaded_by=request.user)
    analysis = AnalysisResult.objects.filter(match=match).first()
    return render(request, 'analyzer/analysis_status.html', {
        'match': match,
        'analysis': analysis,
    })


@login_required
def generate_report(request, match_id):
    match = get_object_or_404(Match, id=match_id, uploaded_by=request.user)

    if request.method == 'POST':
        match.status = 'analyzing'
        match.save()

        start_analysis_job(match.id)
        messages.info(request, '분석 요청이 접수되었습니다.')
        return redirect('analysis_status', match_id=match.id)

    return redirect('analysis_status', match_id=match.id)


@login_required
def analysis_report(request, match_id):
    match = get_object_or_404(Match, id=match_id, uploaded_by=request.user)
    analysis = get_object_or_404(AnalysisResult, match=match)
    _sync_analysis_videos(match, analysis)
    players = analysis.players.all()

    report_settings = request.session.get('report_settings', {
        'show_tracking': True,
        'show_path': True,
        'show_topview': True,
        'show_speed': True,
        'show_summary': True,
        'heatmap_opacity': 60,
    })

    return render(request, 'analyzer/analysis_report.html', {
        'match': match,
        'analysis': analysis,
        'players': players,
        'report_settings': report_settings,
    })


def _sync_analysis_videos(match, analysis) -> None:
    needs_sync = not analysis.detected_video or not analysis.topview_video
    if analysis.detected_video and not analysis.detected_video.storage.exists(analysis.detected_video.name):
        needs_sync = True
    if analysis.topview_video and not analysis.topview_video.storage.exists(analysis.topview_video.name):
        needs_sync = True

    if not needs_sync:
        return

    try:
        result = import_analyzer_result_videos(match)
    except AnalyzerRunError:
        return

    analysis.detected_video.name = result.detected_video_name
    analysis.topview_video.name = result.topview_video_name
    analysis.save(update_fields=['detected_video', 'topview_video'])


@login_required
def update_report_info(request, match_id):
    match = get_object_or_404(Match, id=match_id, uploaded_by=request.user)
    analysis = get_object_or_404(AnalysisResult, match=match)

    if request.method == 'POST':
        url = request.POST.get('match_info_url', '')
        analysis.match_info_url = url

        if url:
            home_name = match.home_team.name if match.home_team else '홈팀'
            away_name = match.away_team.name if match.away_team else '원정팀'

            analysis.score_info = f'{home_name} 2 : 1 {away_name}'
            analysis.goal_records = (
                f'전반 23분 {home_name} 득점\n'
                f'후반 12분 {home_name} 득점\n'
                f'후반 31분 {away_name} 득점'
            )
            analysis.lineup_info = (
                f'{home_name} 라인업: GK, DF, MF, FW\n'
                f'{away_name} 라인업: GK, DF, MF, FW'
            )
            analysis.team_stats = (
                f'{home_name} 점유율 55%, 슈팅 8회, 패스 성공률 82%\n'
                f'{away_name} 점유율 45%, 슈팅 6회, 패스 성공률 78%'
            )
        else:
            analysis.score_info = ''
            analysis.goal_records = ''
            analysis.lineup_info = ''
            analysis.team_stats = ''

        analysis.save()

    return redirect('analysis_report', match_id=match.id)


@login_required
def save_report(request, match_id):
    match = get_object_or_404(Match, id=match_id, uploaded_by=request.user)
    analysis = get_object_or_404(AnalysisResult, match=match)

    if request.method == 'POST':
        analysis.is_saved = True
        analysis.save()

    return redirect('analysis_report', match_id=match.id)


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
    teams = Team.objects.filter(user=request.user).order_by('-created_at')
    players = Player.objects.filter(user=request.user).select_related('team').order_by(
        'team__name',
        'jersey_number'
    )
    analyses = AnalysisResult.objects.filter(
        match__uploaded_by=request.user
    ).order_by('-created_at')

    team_form = TeamForm()
    player_form = PlayerForm(user=request.user)

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'team':
            team_form = TeamForm(request.POST)

            if team_form.is_valid():
                team = team_form.save(commit=False)
                team.user = request.user
                team.save()
                return redirect('team_player_manage')

        elif form_type == 'player':
            player_form = PlayerForm(request.POST, user=request.user)

            if player_form.is_valid():
                player = player_form.save(commit=False)
                player.user = request.user
                player.save()
                return redirect('team_player_manage')

    return render(request, 'analyzer/team_player_manage.html', {
        'teams': teams,
        'players': players,
        'analyses': analyses,
        'team_form': team_form,
        'player_form': player_form,
    })


@login_required
def edit_team(request, team_id):
    team = get_object_or_404(Team, id=team_id, user=request.user)

    if request.method == 'POST':
        form = TeamForm(request.POST, instance=team)

        if form.is_valid():
            form.save()
            return redirect('team_player_manage')
    else:
        form = TeamForm(instance=team)

    return render(request, 'analyzer/team_edit.html', {
        'form': form,
        'team': team,
    })


@login_required
def delete_team(request, team_id):
    team = get_object_or_404(Team, id=team_id, user=request.user)

    if request.method == 'POST':
        team.delete()
        return redirect('team_player_manage')

    return render(request, 'analyzer/team_delete.html', {'team': team})


@login_required
def edit_player(request, player_id):
    player = get_object_or_404(Player, id=player_id, user=request.user)

    if request.method == 'POST':
        form = PlayerForm(request.POST, instance=player, user=request.user)

        if form.is_valid():
            form.save()
            return redirect('team_player_manage')
    else:
        form = PlayerForm(instance=player, user=request.user)

    return render(request, 'analyzer/player_edit.html', {
        'form': form,
        'player': player,
    })


@login_required
def delete_player(request, player_id):
    player = get_object_or_404(Player, id=player_id, user=request.user)

    if request.method == 'POST':
        player.delete()
        return redirect('team_player_manage')

    return render(request, 'analyzer/player_delete.html', {'player': player})


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
        'heatmap_opacity': 60,
        'theme_color': 'green',
        'tracking_overlay': True,
    })

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'profile':
            request.user.first_name = request.POST.get(
                'first_name',
                request.user.first_name
            )
            request.user.email = request.POST.get(
                'email',
                request.user.email
            )
            request.user.save()

            messages.success(request, '개인정보가 수정되었습니다.')
            return redirect('settings_page')

        if form_type == 'password':
            current_password = request.POST.get('current_password')
            new_password = request.POST.get('new_password')
            confirm_password = request.POST.get('confirm_password')

            if not request.user.check_password(current_password):
                messages.error(request, '현재 비밀번호가 일치하지 않습니다.')
            elif not new_password:
                messages.error(request, '새 비밀번호를 입력하세요.')
            elif new_password != confirm_password:
                messages.error(request, '새 비밀번호와 비밀번호 확인이 일치하지 않습니다.')
            else:
                request.user.set_password(new_password)
                request.user.save()
                update_session_auth_hash(request, request.user)
                messages.success(request, '비밀번호가 변경되었습니다.')

            return redirect('settings_page')

        if form_type == 'display':
            current_settings = {
                'show_tracking': 'show_tracking' in request.POST,
                'show_path': 'show_path' in request.POST,
                'show_topview': 'show_topview' in request.POST,
                'show_speed': 'show_speed' in request.POST,
                'show_summary': 'show_summary' in request.POST,
                'heatmap_opacity': int(request.POST.get('heatmap_opacity', 60)),
                'theme_color': request.POST.get('theme_color', 'green'),
                'tracking_overlay': 'tracking_overlay' in request.POST,
            }

            request.session['report_settings'] = current_settings
            messages.success(request, '화면 및 리포트 설정이 저장되었습니다.')
            return redirect('settings_page')

        if form_type == 'delete_account':
            user = request.user
            logout(request)
            user.delete()
            return redirect('main')

    return render(request, 'analyzer/settings.html', {
        'settings': current_settings,
    })
