import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import Http404, HttpResponseForbidden
from django.utils import timezone
from django.db.models import Q, Count
from django.core.paginator import Paginator

from events.models import Event, EventMembership, Track, Prize, CustomQuestion, Rubric, Criterion
from teams.models import Team, TeamMembership, TeamInvite
from projects.models import Project, ProjectMedia
from judging.models import JudgeTrackScope, JudgeInvite, Assignment, Review, ResultSnapshot, ResultRow
from judging.scoring import compute_pool_results
from accounts.models import WorkspaceSettings
from audit.models import AuditEvent

User = get_user_model()


# -------------------------------------------------------------
# Public Views
# -------------------------------------------------------------

def landing_page(request):
    """
    Cinematic landing page (document title 'FairPanel — Every Project Deserves a Fair Review')
    """
    events_count = Event.objects.filter(status__in=['active', 'judging', 'published']).count()
    teams_count = Team.objects.count()
    projects_count = Project.objects.filter(status='submitted', eligibility='eligible').count()
    tracks_count = Track.objects.count()

    context = {
        'events_count': events_count,
        'teams_count': teams_count,
        'projects_count': projects_count,
        'tracks_count': tracks_count,
    }
    return render(request, 'fairpanel/landing.html', context)


def how_it_works_page(request):
    return render(request, 'fairpanel/how_it_works.html')


def public_events_list(request):
    events = Event.objects.all().order_by('-created_at')
    return render(request, 'fairpanel/events/list.html', {'events': events})


def public_event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    tracks = event.tracks.all()
    prizes = event.prizes.all()
    questions = event.custom_questions.all()

    user_membership = None
    user_team = None
    if request.user.is_authenticated:
        user_membership = event.memberships.filter(user=request.user).first()
        user_team_mem = TeamMembership.objects.filter(team__event=event, user=request.user).first()
        if user_team_mem:
            user_team = user_team_mem.team

    has_results = event.result_snapshots.exists()

    context = {
        'event': event,
        'tracks': tracks,
        'prizes': prizes,
        'custom_questions': questions,
        'user_membership': user_membership,
        'user_team': user_team,
        'has_results': has_results,
    }
    return render(request, 'fairpanel/events/detail.html', context)


def public_gallery(request):
    """
    Public Project Gallery
    CRITICAL: MUST SERVER-RENDER PROJECT TITLES FROM FIXTURES IN INITIAL HTML!
    """
    event_id = request.GET.get('event')
    search_q = request.GET.get('q', '').strip()
    track_filter = request.GET.get('track', '').strip()

    qs = Project.objects.filter(status='submitted', eligibility='eligible').select_related('team', 'track', 'event')

    if event_id:
        qs = qs.filter(event_id=event_id)

    if track_filter:
        qs = qs.filter(track_id=track_filter)

    if search_q:
        qs = qs.filter(
            Q(title__icontains=search_q) |
            Q(tagline__icontains=search_q) |
            Q(description__icontains=search_q) |
            Q(tech_tags__icontains=search_q)
        )

    # Order stably
    qs = qs.order_by('id')

    paginator = Paginator(qs, 24)
    page_number = request.GET.get('page', 1)
    projects_page = paginator.get_page(page_number)

    all_tracks = Track.objects.all()
    events = Event.objects.all()

    context = {
        'projects': projects_page,
        'selected_event_id': event_id,
        'search_q': search_q,
        'selected_track': track_filter,
        'tracks': all_tracks,
        'events': events,
    }
    return render(request, 'fairpanel/projects/gallery.html', context)


def public_project_detail(request, project_id):
    project = get_object_or_404(Project.objects.select_related('event', 'team', 'track'), id=project_id)

    is_team_member = request.user.is_authenticated and project.team.memberships.filter(user=request.user).exists()
    is_organizer = request.user.is_authenticated and project.event.memberships.filter(user=request.user, role='organizer').exists()

    # Drafts invisible to public
    if project.status == 'draft' and not (is_team_member or is_organizer):
        raise Http404("Project not found")

    team_members = project.team.memberships.select_related('user').all() if project.team else []

    context = {
        'project': project,
        'team_members': team_members,
        'is_team_member': is_team_member,
        'is_organizer': is_organizer,
    }
    return render(request, 'fairpanel/projects/detail.html', context)


def public_event_results(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    snapshot = event.result_snapshots.order_by('-revision').first()

    context = {
        'event': event,
        'snapshot': snapshot,
        'rows': snapshot.rows.select_related('project').order_by('raw_rank') if snapshot else []
    }
    return render(request, 'fairpanel/events/results.html', context)


# -------------------------------------------------------------
# Auth & Routing Views
# -------------------------------------------------------------

def login_chooser(request):
    return render(request, 'fairpanel/auth/login_chooser.html')


def login_workspace(request, workspace_role=None):
    if request.user.is_authenticated:
        return redirect('dashboard_resolver')

    target_role = workspace_role or 'participant'
    error = None

    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')

        user = authenticate(request, username=email, password=password)
        if user:
            # Check if role matches membership
            if target_role in ('organizer', 'judge'):
                has_role = user.memberships.filter(role=target_role).exists() or user.is_staff
                if not has_role:
                    error = f"This account does not have {target_role} privileges for any event."
                    return render(request, 'fairpanel/auth/login.html', {'role': target_role, 'error': error})

            login(request, user)
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)

            if target_role == 'organizer':
                return redirect('organizer_dashboard')
            elif target_role == 'judge':
                return redirect('judge_dashboard')
            else:
                return redirect('participant_dashboard')
        else:
            error = "Invalid email or password. Please try again."

    return render(request, 'fairpanel/auth/login.html', {'role': target_role, 'error': error})


def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_resolver')

    error = None
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        password = request.POST.get('password', '')
        display_name = request.POST.get('display_name', '').strip()

        if not email or '@' not in email:
            error = "A valid email is required."
        elif not password or len(password) < 8:
            error = "Password must be at least 8 characters long."
        elif User.objects.filter(email=email).exists():
            error = "An account with this email already exists."
        else:
            user = User.objects.create_user(
                email=email,
                password=password,
                display_name=display_name or email.split('@')[0].capitalize()
            )
            WorkspaceSettings.objects.create(
                user=user,
                workspace_type='participant',
                preferences={'display_name': user.display_name, 'skills': [], 'timezone': 'UTC'}
            )
            login(request, user)
            return redirect('participant_dashboard')

    return render(request, 'fairpanel/auth/register.html', {'error': error})


@login_required
def dashboard_resolver(request):
    """
    Resolver redirecting to authorized workspace.
    """
    memberships = list(request.user.memberships.all())
    # If organizer in any event, offer or go to organizer dashboard
    if any(m.role == 'organizer' for m in memberships) or request.user.is_staff:
        return redirect('organizer_dashboard')
    if any(m.role == 'judge' for m in memberships):
        return redirect('judge_dashboard')
    return redirect('participant_dashboard')


@login_required
def workspaces_chooser(request):
    memberships = request.user.memberships.select_related('event').all()
    return render(request, 'fairpanel/auth/workspaces.html', {'memberships': memberships})


@login_required
def account_security(request):
    return render(request, 'fairpanel/auth/security.html')


# -------------------------------------------------------------
# Invitations Views
# -------------------------------------------------------------

def team_invite_accept_page(request, token):
    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    invite = TeamInvite.objects.filter(token_hash=token_hash).select_related('team', 'team__event').first()

    if not invite or not invite.is_valid:
        return render(request, 'fairpanel/participant/team_invite.html', {'invalid': True})

    team = invite.team
    event = team.event

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect(f"/login/participant/?next=/invites/team/{token}/")

        if TeamMembership.objects.filter(team__event=event, user=request.user).exists():
            messages.error(request, "You are already a member of a team in this event.")
            return redirect('participant_dashboard')

        with transaction.atomic():
            TeamMembership.objects.create(team=team, user=request.user)
            invite.times_used += 1
            invite.save()
            EventMembership.objects.get_or_create(user=request.user, event=event, defaults={'role': 'participant'})

        messages.success(request, f"You have joined {team.name}!")
        return redirect('participant_team', event_id=event.id)

    return render(request, 'fairpanel/participant/team_invite.html', {'invite': invite, 'team': team, 'event': event, 'token': token})


def judge_invite_accept_page(request, token):
    token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    invite = JudgeInvite.objects.filter(token_hash=token_hash).select_related('event').first()

    if not invite or not invite.is_valid:
        return render(request, 'fairpanel/judge/judge_invite.html', {'invalid': True})

    event = invite.event

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect(f"/login/judge/?next=/invites/judge/{token}/")

        with transaction.atomic():
            EventMembership.objects.update_or_create(
                user=request.user,
                event=event,
                defaults={'role': 'judge'}
            )
            scope, _ = JudgeTrackScope.objects.get_or_create(judge=request.user, event=event)
            if invite.tracks:
                trks = Track.objects.filter(id__in=invite.tracks, event=event)
                scope.tracks.set(trks)

            invite.times_used += 1
            invite.save()

        messages.success(request, f"You are now a registered judge for {event.name}!")
        return redirect('judge_dashboard')

    return render(request, 'fairpanel/judge/judge_invite.html', {'invite': invite, 'event': event, 'token': token})


# -------------------------------------------------------------
# Participant Workspace Views
# -------------------------------------------------------------

@login_required
def participant_dashboard(request):
    memberships = request.user.memberships.filter(role='participant').select_related('event')
    events_data = []

    for m in memberships:
        e = m.event
        team_mem = TeamMembership.objects.filter(team__event=e, user=request.user).select_related('team').first()
        team = team_mem.team if team_mem else None
        project = Project.objects.filter(team=team).first() if team else None

        events_data.append({
            'event': e,
            'team': team,
            'project': project,
            'is_open': e.is_submission_open,
        })

    all_active_events = Event.objects.filter(status='active').exclude(memberships__user=request.user)

    context = {
        'events_data': events_data,
        'available_events': all_active_events,
    }
    return render(request, 'fairpanel/participant/dashboard.html', context)


@login_required
def participant_team(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    team_mem = TeamMembership.objects.filter(team__event=event, user=request.user).select_related('team').first()
    team = team_mem.team if team_mem else None

    active_invites = team.invites.filter(revoked_at__isnull=True) if team else []
    members = team.memberships.select_related('user').all() if team else []

    context = {
        'event': event,
        'team': team,
        'members': members,
        'is_captain': team.captain == request.user if team else False,
        'invites': active_invites,
    }
    return render(request, 'fairpanel/participant/team.html', context)


@login_required
def participant_submission(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    team_mem = TeamMembership.objects.filter(team__event=event, user=request.user).select_related('team').first()
    if not team_mem:
        messages.warning(request, "Please create or join a team before submitting a project.")
        return redirect('participant_team', event_id=event.id)

    team = team_mem.team
    project = Project.objects.filter(team=team).first()

    tracks = event.tracks.all()
    questions = event.custom_questions.all()

    context = {
        'event': event,
        'team': team,
        'project': project,
        'tracks': tracks,
        'questions': questions,
        'is_open': event.is_submission_open,
    }
    return render(request, 'fairpanel/participant/submission.html', context)


@login_required
def participant_settings(request):
    settings_obj, _ = WorkspaceSettings.objects.get_or_create(
        user=request.user,
        workspace_type='participant',
        defaults={'preferences': {'display_name': request.user.display_name, 'skills': [], 'timezone': 'UTC'}}
    )
    return render(request, 'fairpanel/participant/settings.html', {'settings': settings_obj})


# -------------------------------------------------------------
# Judge Workspace Views
# -------------------------------------------------------------

@login_required
def judge_dashboard(request):
    is_judge = request.user.memberships.filter(role='judge').exists() or request.user.is_staff
    if not is_judge:
        messages.error(request, "You need a judge invitation to access the Judge Workspace.")
        return redirect('dashboard_resolver')

    selected_event_id = request.GET.get('event')
    events = Event.objects.filter(memberships__user=request.user, memberships__role='judge')

    current_event = None
    if selected_event_id:
        current_event = events.filter(id=selected_event_id).first()
    if not current_event and events.exists():
        current_event = events.first()

    assignments = []
    if current_event:
        assignments = Assignment.objects.filter(
            event=current_event,
            judge=request.user
        ).select_related('project', 'project__track', 'review')

    completed_count = sum(1 for a in assignments if hasattr(a, 'review') and a.review.status == 'submitted')

    context = {
        'events': events,
        'current_event': current_event,
        'assignments': assignments,
        'total_count': len(assignments),
        'completed_count': completed_count,
    }
    return render(request, 'fairpanel/judge/dashboard.html', context)


@login_required
def judge_review_project(request, project_id):
    project = get_object_or_404(Project.objects.select_related('event', 'team', 'track'), id=project_id)
    event = project.event

    assignment = Assignment.objects.filter(event=event, project=project, judge=request.user).first()
    if not assignment and not request.user.is_staff:
        # Check if judge in event
        if not event.memberships.filter(user=request.user, role='judge').exists():
            return HttpResponseForbidden("Access denied: You are not an assigned judge for this project.")
        assignment = Assignment.objects.create(event=event, project=project, judge=request.user, status='assigned')

    review = getattr(assignment, 'review', None)

    rubric, _ = Rubric.objects.get_or_create(event=event, defaults={'version': 1})
    criteria = rubric.criteria.all()

    # Queue of assignments for left sidebar
    queue = Assignment.objects.filter(event=event, judge=request.user).select_related('project', 'review')

    # Next project in queue
    next_assignment = None
    for idx, a in enumerate(queue):
        if a.project_id == project.id and idx + 1 < len(queue):
            next_assignment = queue[idx + 1]
            break

    context = {
        'project': project,
        'event': event,
        'assignment': assignment,
        'review': review,
        'criteria': criteria,
        'queue': queue,
        'next_assignment': next_assignment,
    }
    return render(request, 'fairpanel/judge/review.html', context)


@login_required
def judge_settings(request):
    settings_obj, _ = WorkspaceSettings.objects.get_or_create(
        user=request.user,
        workspace_type='judge',
        defaults={'preferences': {'display_name': request.user.display_name, 'bio': '', 'expertise_tags': [], 'timezone': 'UTC'}}
    )
    return render(request, 'fairpanel/judge/settings.html', {'settings': settings_obj})


# -------------------------------------------------------------
# Organizer Workspace Views
# -------------------------------------------------------------

@login_required
def organizer_dashboard(request):
    is_organizer = request.user.memberships.filter(role='organizer').exists() or request.user.is_staff
    if not is_organizer:
        messages.error(request, "Organizer access required.")
        return redirect('dashboard_resolver')

    events = Event.objects.filter(memberships__user=request.user, memberships__role='organizer')

    context = {
        'events': events,
    }
    return render(request, 'fairpanel/organizer/dashboard.html', context)


@login_required
def organizer_event_create(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        timezone_str = request.POST.get('timezone', 'UTC')
        team_capacity = int(request.POST.get('team_capacity', 4))

        if name:
            with transaction.atomic():
                event = Event.objects.create(
                    owner=request.user,
                    name=name,
                    description=description,
                    timezone=timezone_str,
                    team_capacity=team_capacity,
                    status='active'
                )
                EventMembership.objects.create(user=request.user, event=event, role='organizer')
                rubric = Rubric.objects.create(event=event, version=1)
                Criterion.objects.create(rubric=rubric, key='functionality', name='Functionality', weight=1.0)
                Criterion.objects.create(rubric=rubric, key='innovation', name='Innovation', weight=1.0)
                Criterion.objects.create(rubric=rubric, key='quality', name='Quality', weight=1.0)

            messages.success(request, f"Event '{name}' created successfully!")
            return redirect('organizer_event_detail', event_id=event.id)

    return render(request, 'fairpanel/organizer/create_event.html')


@login_required
def organizer_event_detail(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if not event.memberships.filter(user=request.user, role='organizer').exists() and not request.user.is_staff:
        return HttpResponseForbidden("Organizer access required.")

    submissions_count = event.projects.count()
    judges_count = event.memberships.filter(role='judge').count()
    teams_count = event.teams.count()
    reviews_count = Review.objects.filter(project__event=event, status='submitted').count()

    context = {
        'event': event,
        'submissions_count': submissions_count,
        'judges_count': judges_count,
        'teams_count': teams_count,
        'reviews_count': reviews_count,
    }
    return render(request, 'fairpanel/organizer/event_detail.html', context)


@login_required
def organizer_event_settings(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if not event.memberships.filter(user=request.user, role='organizer').exists() and not request.user.is_staff:
        return HttpResponseForbidden("Organizer access required.")

    rubric, _ = Rubric.objects.get_or_create(event=event, defaults={'version': 1})

    context = {
        'event': event,
        'rubric': rubric,
        'criteria': rubric.criteria.all(),
        'tracks': event.tracks.all(),
        'prizes': event.prizes.all(),
        'questions': event.custom_questions.all(),
    }
    return render(request, 'fairpanel/organizer/event_settings.html', context)


@login_required
def organizer_event_submissions(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if not event.memberships.filter(user=request.user, role='organizer').exists() and not request.user.is_staff:
        return HttpResponseForbidden("Organizer access required.")

    projects = event.projects.select_related('team', 'track').annotate(
        review_count=Count('reviews', filter=Q(reviews__status='submitted'))
    )

    # Detect duplicate titles
    title_counts = {}
    for p in projects:
        title_counts[p.title] = title_counts.get(p.title, 0) + 1

    projects_data = []
    for p in projects:
        projects_data.append({
            'project': p,
            'is_duplicate': title_counts.get(p.title, 0) > 1,
            'review_count': p.review_count,
        })

    context = {
        'event': event,
        'projects_data': projects_data,
    }
    return render(request, 'fairpanel/organizer/submissions.html', context)


@login_required
def organizer_event_judges(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if not event.memberships.filter(user=request.user, role='organizer').exists() and not request.user.is_staff:
        return HttpResponseForbidden("Organizer access required.")

    judges = event.memberships.filter(role='judge').select_related('user')
    assignments = event.assignments.select_related('project', 'judge', 'review')
    invites = event.judge_invites.filter(revoked_at__isnull=True)

    context = {
        'event': event,
        'judges': judges,
        'assignments': assignments,
        'invites': invites,
        'tracks': event.tracks.all(),
    }
    return render(request, 'fairpanel/organizer/judges.html', context)


@login_required
def organizer_event_results(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if not event.memberships.filter(user=request.user, role='organizer').exists() and not request.user.is_staff:
        return HttpResponseForbidden("Organizer access required.")

    # Calculate live preview
    projects = list(event.projects.filter(status='submitted', eligibility='eligible').values('id', 'title', 'track_id'))
    rubric = getattr(event, 'rubric', None)
    criteria_defs = {}
    if rubric:
        for c in rubric.criteria.all():
            criteria_defs[c.key] = {'min_score': c.min_score, 'max_score': c.max_score, 'weight': c.weight}

    reviews = list(Review.objects.filter(project__event=event, status='submitted').values('id', 'project_id', 'judge_id', 'criteria_scores'))

    calc = compute_pool_results(projects, reviews, criteria_defs, min_required_reviews=event.min_reviews_per_project)

    snapshot = event.result_snapshots.order_by('-revision').first()

    context = {
        'event': event,
        'preview': calc,
        'snapshot': snapshot,
        'review_count': len(reviews),
    }
    return render(request, 'fairpanel/organizer/results.html', context)


@login_required
def organizer_event_audit(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    if not event.memberships.filter(user=request.user, role='organizer').exists() and not request.user.is_staff:
        return HttpResponseForbidden("Organizer access required.")

    audit_events = event.audit_events.select_related('actor').all()[:150]

    context = {
        'event': event,
        'audit_events': audit_events,
    }
    return render(request, 'fairpanel/organizer/audit.html', context)


@login_required
def organizer_settings(request):
    settings_obj, _ = WorkspaceSettings.objects.get_or_create(
        user=request.user,
        workspace_type='organizer',
        defaults={'preferences': {'display_name': request.user.display_name, 'timezone': 'UTC'}}
    )
    return render(request, 'fairpanel/organizer/settings.html', {'settings': settings_obj})
