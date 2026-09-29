from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from events.models import EventMembership
from django.conf import settings
from django.conf.urls.static import static

from fairpanel_core import views

@login_required
def redirect_legacy_team(request, event_id):
    if not EventMembership.objects.filter(user=request.user, event_id=event_id, role='participant').exists():
        return HttpResponseForbidden('Participant access required.')
    return redirect(f'/participant/events/{event_id}/team/')

@login_required
def redirect_legacy_submission(request, event_id):
    if not EventMembership.objects.filter(user=request.user, event_id=event_id, role='participant').exists():
        return HttpResponseForbidden('Participant access required.')
    return redirect(f'/participant/events/{event_id}/submission/')

urlpatterns = [
    # Platform Administration
    path('admin/', admin.site.urls),

    # Shared API Contract
    path('api/v1/', include('api.urls')),

    # Public Routes
    path('', views.landing_page, name='landing'),
    path('how-it-works/', views.how_it_works_page, name='how_it_works'),
    path('events/', views.public_events_list, name='public_events'),
    path('events/<str:event_id>/', views.public_event_detail, name='public_event_detail'),
    path('events/<str:event_id>/results/', views.public_event_results, name='public_event_results'),
    path('projects/', views.public_gallery, name='public_gallery'),
    path('projects/<str:project_id>/', views.public_project_detail, name='public_project_detail'),

    # Legacy Route Redirects
    path('events/<str:event_id>/team/', redirect_legacy_team),
    path('events/<str:event_id>/submission/', redirect_legacy_submission),

    # Authentication & Access
    path('login/', views.login_chooser, name='login'),
    path('login/<str:workspace_role>/', views.login_workspace, name='login_workspace'),
    path('register/', views.register_view, name='register'),
    path('dashboard/', views.dashboard_resolver, name='dashboard_resolver'),
    path('workspaces/', views.workspaces_chooser, name='workspaces_chooser'),
    path('account/security/', views.account_security, name='account_security'),
    path('invites/team/<str:token>/', views.team_invite_accept_page, name='team_invite_accept_page'),
    path('invites/judge/<str:token>/', views.judge_invite_accept_page, name='judge_invite_accept_page'),

    # Participant Workspace
    path('participant/', views.participant_dashboard, name='participant_dashboard'),
    path('participant/settings/', views.participant_settings, name='participant_settings'),
    path('participant/events/<str:event_id>/team/', views.participant_team, name='participant_team'),
    path('participant/events/<str:event_id>/submission/', views.participant_submission, name='participant_submission'),

    # Judge Workspace
    path('judge/', views.judge_dashboard, name='judge_dashboard'),
    path('judge/settings/', views.judge_settings, name='judge_settings'),
    path('judge/projects/<str:project_id>/', views.judge_review_project, name='judge_review_project'),

    # Organizer Workspace
    path('organizer/', views.organizer_dashboard, name='organizer_dashboard'),
    path('organizer/settings/', views.organizer_settings, name='organizer_settings'),
    path('organizer/events/new/', views.organizer_event_create, name='organizer_event_create'),
    path('organizer/events/<str:event_id>/', views.organizer_event_detail, name='organizer_event_detail'),
    path('organizer/events/<str:event_id>/settings/', views.organizer_event_settings, name='organizer_event_settings'),
    path('organizer/events/<str:event_id>/submissions/', views.organizer_event_submissions, name='organizer_event_submissions'),
    path('organizer/events/<str:event_id>/judges/', views.organizer_event_judges, name='organizer_event_judges'),
    path('organizer/events/<str:event_id>/results/', views.organizer_event_results, name='organizer_event_results'),
    path('organizer/events/<str:event_id>/audit/', views.organizer_event_audit, name='organizer_event_audit'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
