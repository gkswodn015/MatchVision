from django.urls import path
from . import views

urlpatterns = [
    path('', views.main, name='main'),
    path('signup/', views.signup, name='signup'),
    path('upload/', views.upload_match, name='upload_match'),
    path('matches/', views.match_list, name='match_list'),

    path(
        'matches/<int:match_id>/request-analysis/',
        views.request_analysis,
        name='request_analysis'
    ),
    path(
        'matches/<int:match_id>/analysis-status/',
        views.analysis_status,
        name='analysis_status'
    ),
]