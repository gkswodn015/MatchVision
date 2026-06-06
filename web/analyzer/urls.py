from django.urls import path
from . import views

urlpatterns = [
    path('', views.main, name='main'),
    path('signup/', views.signup, name='signup'),

    path('upload/', views.upload_match, name='upload_match'),
    path('matches/', views.match_list, name='match_list'),

    path('matches/<int:match_id>/', views.match_detail, name='match_detail'),
    path('matches/<int:match_id>/analysis/', views.video_analysis, name='video_analysis'),
    path('matches/<int:match_id>/request-analysis/', views.request_analysis, name='request_analysis'),
    path('matches/<int:match_id>/analysis-status/', views.analysis_status, name='analysis_status'),
    path('matches/<int:match_id>/generate-report/', views.generate_report, name='generate_report'),
    path('matches/<int:match_id>/report/', views.analysis_report, name='analysis_report'),
    path('matches/<int:match_id>/report/update-info/', views.update_report_info, name='update_report_info'),
    path('matches/<int:match_id>/report/update-track-players/', views.update_track_players, name='update_track_players'),
    path('matches/<int:match_id>/report/save/', views.save_report, name='save_report'),

    path('manage/', views.match_manage, name='match_manage'),
    path('manage/<int:match_id>/edit/', views.edit_match, name='edit_match'),
    path('manage/<int:match_id>/delete/', views.delete_match, name='delete_match'),

    path('settings/', views.settings_page, name='settings_page'),
]
