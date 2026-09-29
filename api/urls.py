from django.urls import path
from api import views

urlpatterns = [
    # Auth
    path('auth/csrf', views.auth_csrf, name='api_auth_csrf'),
    path('auth/register', views.auth_register, name='api_auth_register'),
    path('auth/login', views.auth_login, name='api_auth_login'),
    path('auth/logout', views.auth_logout, name='api_auth_logout'),
    path('auth/me', views.auth_me, name='api_auth_me'),
    path('auth/workspaces', views.auth_workspaces, name='api_auth_workspaces'),
    path('auth/password/change', views.auth_password_change, name='api_auth_password_change'),
    path('auth/sessions', views.auth_sessions_list, name='api_auth_sessions_list'),
    path('auth/sessions/revoke-others', views.auth_sessions_revoke_others, name='api_auth_sessions_revoke_others'),

    # Workspace Settings
    path('settings/organizer', views.settings_organizer, name='api_settings_organizer'),
    path('settings/judge', views.settings_judge, name='api_settings_judge'),
    path('settings/participant', views.settings_participant, name='api_settings_participant'),

    # Public Stats & Events
    path('public/stats', views.public_stats, name='api_public_stats'),
    path('events', views.events_list_create, name='api_events_list_create'),
    path('events/<str:event_id>', views.event_detail_update, name='api_event_detail_update'),
    path('events/<str:event_id>/join', views.event_join, name='api_event_join'),

    # Teams
    path('events/<str:event_id>/teams', views.event_teams_list_create, name='api_event_teams'),
    path('teams/<str:team_id>/invites', views.team_invites_create, name='api_team_invites_create'),
    path('team-invites/<str:invite_id>', views.team_invite_revoke, name='api_team_invite_revoke'),
    path('team-invites/accept', views.team_invites_accept, name='api_team_invites_accept'),

    # Projects
    path('events/<str:event_id>/projects', views.event_projects_list_create, name='api_event_projects'),
    path('projects/<str:project_id>', views.project_detail_update, name='api_project_detail_update'),
    path('projects/<str:project_id>/submit', views.project_submit, name='api_project_submit'),
    path('uploads', views.upload_media, name='api_uploads'),

    # Rubric & Scoring
    path('events/<str:event_id>/rubric', views.event_rubric_detail_update, name='api_event_rubric'),
    path('events/<str:event_id>/judge-invites', views.event_judge_invites, name='api_event_judge_invites'),
    path('judge-invites/accept', views.judge_invites_accept, name='api_judge_invites_accept'),
    path('events/<str:event_id>/assignments', views.event_assignments_list_create, name='api_event_assignments'),
    path('assignments/<str:assignment_id>/conflict', views.assignment_conflict, name='api_assignment_conflict'),

    # Judge Endpoints
    path('judge/assignments', views.judge_assignments, name='api_judge_assignments'),
    path('judge/scores', views.judge_scores, name='api_judge_scores'),
    path('judges/<str:judge_id>/scores', views.judge_peer_scores, name='api_judges_peer_scores'),
    path('projects/<str:project_id>/review', views.project_review_save, name='api_project_review_save'),
    path('projects/<str:project_id>/review/submit', views.project_review_submit, name='api_project_review_submit'),

    # Organizer Operations
    path('events/<str:event_id>/progress', views.event_progress, name='api_event_progress'),
    path('projects/<str:project_id>/eligibility', views.project_eligibility, name='api_project_eligibility'),
    path('events/<str:event_id>/results/preview', views.event_results_preview, name='api_event_results_preview'),
    path('events/<str:event_id>/results/publish', views.event_results_publish, name='api_event_results_publish'),
    path('events/<str:event_id>/results', views.event_results_public, name='api_event_results_public'),
    path('events/<str:event_id>/audit', views.event_audit_log, name='api_event_audit_log'),
    path('events/<str:event_id>/exports/<str:kind>.csv', views.event_csv_export, name='api_event_csv_export'),
]
