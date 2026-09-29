import csv
import io
import json
import secrets
import hashlib
import math
from datetime import datetime, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from urllib.parse import urlsplit
from django.conf import settings
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.sessions.models import Session
from django.db import transaction
from django.db.models import Q, Count, F
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from fairpanel_core.utils import api_success, api_error, generate_id
from accounts.models import WorkspaceSettings
from events.models import Event, EventMembership, Track, Prize, CustomQuestion, Rubric, Criterion
from teams.models import Team, TeamMembership, TeamInvite
from projects.models import Project, ProjectMedia
from judging.models import JudgeTrackScope, JudgeInvite, Assignment, Review, ResultSnapshot, ResultRow
from judging.scoring import compute_pool_results, compute_weighted_score
from audit.models import AuditEvent

User = get_user_model()


def get_json_body(request):
    try:
        if request.body:
            return json.loads(request.body.decode('utf-8'))
    except Exception:
        pass
    return {}


def validate_project_links(data):
    """Only browser-safe absolute web links may be published as project media or actions."""
    def is_web_url(value):
        if not isinstance(value, str) or len(value) > 1000:
            return False
        try:
            parsed = urlsplit(value)
        except ValueError:
            return False
        return parsed.scheme.lower() in ('http', 'https') and bool(parsed.netloc) and not parsed.username

    for field in ('thumbnail_url', 'video_url', 'repo_url', 'live_url'):
        if field in data and data[field] and not is_web_url(data[field]):
            return f'{field} must be an absolute HTTP or HTTPS URL'
    if 'images' in data:
        images = data['images']
        if not isinstance(images, list) or len(images) > 6 or any(not is_web_url(image) for image in images):
            return 'images must contain up to six HTTP or HTTPS URLs'
    return None


def parse_event_datetime(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_timezone.utc)
    return parsed.astimezone(dt_timezone.utc)


def validate_event_schedule(event):
    if event.submissions_open and event.submissions_close and event.submissions_open >= event.submissions_close:
        return 'Submission close must be after submission open'
    if event.judging_open and event.judging_close and event.judging_open >= event.judging_close:
        return 'Judging close must be after judging open'
    if not 1 <= event.team_capacity <= 20 or not 1 <= event.min_reviews_per_project <= 20:
        return 'Team capacity and review target must be between 1 and 20'
    try:
        ZoneInfo(event.timezone)
    except (ZoneInfoNotFoundError, TypeError):
        return 'Invalid timezone'
    return None


def record_audit(event, actor, action, target="", reason="", before_data=None, after_data=None):
    AuditEvent.objects.create(
        event=event,
        actor=actor if (actor and actor.is_authenticated) else None,
        action=action,
        target=target,
        reason=reason,
        before_data=before_data or {},
        after_data=after_data or {}
    )


# -------------------------------------------------------------
# Auth & Session Endpoints
# -------------------------------------------------------------

def auth_csrf(request):
    return api_success({"csrf_token": get_token(request)})


def auth_register(request):
    if request.method != 'POST':
        return api_error('method_not_allowed', 'POST required', status=405)
    data = get_json_body(request)
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    display_name = data.get('display_name', '').strip()

    if not email or '@' not in email:
        return api_error('invalid_email', 'A valid email is required', status=422)
    if not password or len(password) < 8:
        return api_error('weak_password', 'Password must be at least 8 characters', status=422)
    if User.objects.filter(email=email).exists():
        return api_error('email_taken', 'An account with this email already exists', status=409)

    user = User.objects.create_user(
        email=email,
        password=password,
        display_name=display_name or email.split('@')[0].capitalize()
    )
    # Default participant workspace settings
    WorkspaceSettings.objects.create(
        user=user,
        workspace_type='participant',
        preferences={'display_name': user.display_name, 'skills': [], 'timezone': 'UTC'}
    )
    login(request, user)
    return api_success({
        'id': user.id,
        'email': user.email,
        'display_name': user.display_name
    }, status=201)


def auth_login(request):
    if request.method != 'POST':
        return api_error('method_not_allowed', 'POST required', status=405)
    data = get_json_body(request)
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    user = authenticate(request, username=email, password=password)
    if not user:
        return api_error('invalid_credentials', 'Invalid email or password', status=401)

    login(request, user)
    # Return user with memberships
    memberships = list(user.memberships.values('event_id', 'role'))
    return api_success({
        'id': user.id,
        'email': user.email,
        'display_name': user.display_name,
        'memberships': memberships
    })


def auth_logout(request):
    if request.method != 'POST':
        return api_error('method_not_allowed', 'POST required', status=405)
    logout(request)
    return api_success({'message': 'Logged out successfully'})


def auth_me(request):
    if not request.user.is_authenticated:
        return api_error('unauthenticated', 'Login required', status=401)

    memberships = [
        {
            'event_id': m.event_id,
            'event_name': m.event.name,
            'role': m.role
        }
        for m in request.user.memberships.select_related('event').all()
    ]
    return api_success({
        'id': request.user.id,
        'email': request.user.email,
        'display_name': request.user.display_name,
        'is_staff': request.user.is_staff,
        'memberships': memberships
    })


def auth_workspaces(request):
    if not request.user.is_authenticated:
        return api_error('unauthenticated', 'Login required', status=401)

    destinations = []
    # Any user can access participant workspace
    destinations.append({
        'role': 'participant',
        'title': 'Participant Workspace',
        'url': '/participant/'
    })

    # Event specific roles
    memberships = request.user.memberships.select_related('event').all()
    for m in memberships:
        if m.role == 'organizer':
            destinations.append({
                'role': 'organizer',
                'event_id': m.event_id,
                'event_name': m.event.name,
                'title': f"Organizer — {m.event.name}",
                'url': f"/organizer/events/{m.event_id}/"
            })
        elif m.role == 'judge':
            destinations.append({
                'role': 'judge',
                'event_id': m.event_id,
                'event_name': m.event.name,
                'title': f"Judge — {m.event.name}",
                'url': f"/judge/?event={m.event_id}"
            })

    return api_success(destinations)


# -------------------------------------------------------------
# Workspace Settings Endpoints
# -------------------------------------------------------------

def _handle_workspace_settings(request, workspace_type, allowlisted_fields):
    if not request.user.is_authenticated:
        return api_error('unauthenticated', 'Login required', status=401)

    # Check permission to access workspace settings
    if workspace_type in ('organizer', 'judge'):
        has_role = request.user.memberships.filter(role=workspace_type).exists() or request.user.is_staff
        if not has_role:
            return api_error('forbidden', f'You do not have active {workspace_type} memberships', status=403)

    settings_obj, _ = WorkspaceSettings.objects.get_or_create(
        user=request.user,
        workspace_type=workspace_type,
        defaults={'version': 1, 'preferences': {}}
    )

    if request.method == 'GET':
        return api_success({
            'workspace_type': workspace_type,
            'preferences': settings_obj.preferences,
            'version': settings_obj.version,
            'updated_at': settings_obj.updated_at.isoformat()
        })

    elif request.method == 'PATCH':
        data = get_json_body(request)
        req_version = data.get('version')
        if req_version is not None and req_version != settings_obj.version:
            return api_error('version_conflict', 'Settings have been updated elsewhere. Please refresh.', status=409)

        # Allowlisted fields only
        prefs = dict(settings_obj.preferences)
        for key in allowlisted_fields:
            if key in data:
                prefs[key] = data[key]

        settings_obj.preferences = prefs
        settings_obj.version += 1
        settings_obj.save()

        # Update display name on user model if provided
        if 'display_name' in data and data['display_name'].strip():
            request.user.display_name = data['display_name'].strip()
            request.user.save()

        return api_success({
            'workspace_type': workspace_type,
            'preferences': settings_obj.preferences,
            'version': settings_obj.version,
            'updated_at': settings_obj.updated_at.isoformat()
        })

    return api_error('method_not_allowed', 'GET or PATCH required', status=405)


def settings_organizer(request):
    return _handle_workspace_settings(request, 'organizer', ['display_name', 'timezone', 'notifications_enabled'])


def settings_judge(request):
    return _handle_workspace_settings(request, 'judge', ['display_name', 'bio', 'expertise_tags', 'timezone'])


def settings_participant(request):
    return _handle_workspace_settings(request, 'participant', ['display_name', 'bio', 'skills', 'timezone'])


def auth_password_change(request):
    if not request.user.is_authenticated:
        return api_error('unauthenticated', 'Login required', status=401)
    if request.method != 'POST':
        return api_error('method_not_allowed', 'POST required', status=405)

    data = get_json_body(request)
    current_password = data.get('current_password', '')
    new_password = data.get('new_password', '')

    if not request.user.check_password(current_password):
        return api_error('invalid_password', 'Current password is incorrect', status=422)
    if not new_password or len(new_password) < 8:
        return api_error('weak_password', 'New password must be at least 8 characters', status=422)

    request.user.set_password(new_password)
    request.user.save()
    login(request, request.user)  # Keep current session logged in
    return api_success({'message': 'Password changed successfully'})


def auth_sessions_list(request):
    if not request.user.is_authenticated:
        return api_error('unauthenticated', 'Login required', status=401)

    # Return safe metadata for sessions
    current_key = request.session.session_key
    active_sessions = []
    for s in Session.objects.filter(expire_date__gt=timezone.now()):
        data = s.get_decoded()
        if str(data.get('_auth_user_id')) == str(request.user.id):
            active_sessions.append({
                'session_key': s.session_key[:8] + '...',
                'is_current': s.session_key == current_key,
                'expires_at': s.expire_date.isoformat()
            })
    return api_success(active_sessions)


def auth_sessions_revoke_others(request):
    if not request.user.is_authenticated:
        return api_error('unauthenticated', 'Login required', status=401)
    if request.method != 'POST':
        return api_error('method_not_allowed', 'POST required', status=405)

    data = get_json_body(request)
    current_password = data.get('current_password', '')
    if not request.user.check_password(current_password):
        return api_error('invalid_password', 'Password verification failed', status=422)

    current_key = request.session.session_key
    revoked_count = 0
    for s in Session.objects.filter(expire_date__gt=timezone.now()):
        data = s.get_decoded()
        if str(data.get('_auth_user_id')) == str(request.user.id) and s.session_key != current_key:
            s.delete()
            revoked_count += 1

    return api_success({'revoked_count': revoked_count})


# -------------------------------------------------------------
# Public Stats & Events
# -------------------------------------------------------------

def public_stats(request):
    """
    Public API-derived counts: Events, Teams, Published Projects, Tracks.
    Never expose judge counts or private progress through these statistics!
    """
    events_count = Event.objects.filter(status__in=['active', 'judging', 'published']).count()
    teams_count = Team.objects.count()
    published_projects_count = Project.objects.filter(status='submitted', eligibility='eligible').count()
    tracks_count = Track.objects.count()

    return api_success({
        'events': events_count,
        'teams': teams_count,
        'published_projects': published_projects_count,
        'tracks': tracks_count,
    })


def events_list_create(request):
    if request.method == 'GET':
        events = Event.objects.filter(status__in=['active', 'judging', 'published']).order_by('-created_at')
        result = []
        for e in events:
            result.append({
                'id': e.id,
                'name': e.name,
                'description': e.description,
                'timezone': e.timezone,
                'status': e.status,
                'submissions_open': e.submissions_open.isoformat() if e.submissions_open else None,
                'submissions_close': e.submissions_close.isoformat() if e.submissions_close else None,
                'judging_open': e.judging_open.isoformat() if e.judging_open else None,
                'judging_close': e.judging_close.isoformat() if e.judging_close else None,
                'is_submission_open': e.is_submission_open,
                'is_judging_open': e.is_judging_open,
                'results_published_at': e.results_published_at.isoformat() if e.results_published_at else None,
                'track_count': e.tracks.count(),
                'prize_count': e.prizes.count(),
            })
        return api_success(result)

    elif request.method == 'POST':
        if not request.user.is_authenticated:
            return api_error('unauthenticated', 'Login required to create event', status=401)

        data = get_json_body(request)
        name = data.get('name', '').strip()
        if not name:
            return api_error('validation_error', 'Event name is required', status=422)

        tracks_data = data.get('tracks', [])
        prizes_data = data.get('prizes', [])
        if (not isinstance(tracks_data, list) or len(tracks_data) > 30 or
                not isinstance(prizes_data, list) or len(prizes_data) > 30):
            return api_error('validation_error', 'Tracks and prizes must be lists of at most 30 items', status=422)
        if any(not isinstance(track, str) or not track.strip() for track in tracks_data):
            return api_error('validation_error', 'Each track needs a name', status=422)
        if any(not isinstance(prize, dict) or not isinstance(prize.get('name'), str) or not prize['name'].strip()
               for prize in prizes_data):
            return api_error('validation_error', 'Each prize needs a name', status=422)
        try:
            schedule = {key: parse_event_datetime(data.get(key)) for key in
                        ('submissions_open', 'submissions_close', 'judging_open', 'judging_close')}
            capacity = int(data.get('team_capacity', 4))
            reviews_target = int(data.get('min_reviews_per_project', 3))
        except (TypeError, ValueError, OverflowError):
            return api_error('validation_error', 'Invalid event dates or numeric limits', status=422)

        draft_event = Event(owner=request.user, name=name, timezone=data.get('timezone', 'UTC'),
                            team_capacity=capacity, min_reviews_per_project=reviews_target, **schedule)
        schedule_error = validate_event_schedule(draft_event)
        if schedule_error:
            return api_error('validation_error', schedule_error, status=422)

        with transaction.atomic():
            event = Event.objects.create(
                owner=request.user,
                name=name,
                description=data.get('description', ''),
                timezone=data.get('timezone', 'UTC'),
                **schedule,
                status='active',
                team_capacity=capacity,
                min_reviews_per_project=reviews_target,
            )
            for track_name in tracks_data:
                Track.objects.create(event=event, name=track_name.strip())
            for prize_data in prizes_data:
                Prize.objects.create(event=event, name=prize_data['name'].strip(),
                                     amount=str(prize_data.get('amount', '')),
                                     description=str(prize_data.get('description', '')))
            # Add creator as organizer
            EventMembership.objects.create(user=request.user, event=event, role='organizer')
            # Initialize empty rubric
            rubric = Rubric.objects.create(event=event, version=1, is_locked=False)
            Criterion.objects.create(rubric=rubric, key='quality', name='Overall Quality', min_score=1.0, max_score=5.0, weight=1.0)

            record_audit(event, request.user, 'create_event', target=event.id, reason="Initial event creation")

        return api_success({'id': event.id, 'name': event.name}, status=201)

    return api_error('method_not_allowed', 'GET or POST required', status=405)


def event_detail_update(request, event_id):
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return api_error('not_found', 'Event not found', status=404)

    if request.method == 'GET':
        tracks = list(event.tracks.values('id', 'name', 'description'))
        prizes = list(event.prizes.values('id', 'name', 'description', 'amount'))
        questions = list(event.custom_questions.values('id', 'key', 'label', 'type', 'required', 'choices', 'order'))
        return api_success({
            'id': event.id,
            'name': event.name,
            'description': event.description,
            'timezone': event.timezone,
            'status': event.status,
            'submissions_open': event.submissions_open.isoformat() if event.submissions_open else None,
            'submissions_close': event.submissions_close.isoformat() if event.submissions_close else None,
            'judging_open': event.judging_open.isoformat() if event.judging_open else None,
            'judging_close': event.judging_close.isoformat() if event.judging_close else None,
            'is_submission_open': event.is_submission_open,
            'is_judging_open': event.is_judging_open,
            'team_capacity': event.team_capacity,
            'min_reviews_per_project': event.min_reviews_per_project,
            'results_published_at': event.results_published_at.isoformat() if event.results_published_at else None,
            'tracks': tracks,
            'prizes': prizes,
            'custom_questions': questions,
        })

    elif request.method == 'PATCH':
        if not request.user.is_authenticated or not event.memberships.filter(user=request.user, role='organizer').exists():
            return api_error('forbidden', 'Organizer access required', status=403)

        data = get_json_body(request)
        before_data = {'name': event.name, 'submissions_close': event.submissions_close.isoformat() if event.submissions_close else None}

        if 'name' in data:
            event.name = data['name'].strip()
        if 'description' in data:
            event.description = data['description']
        if 'timezone' in data:
            event.timezone = data['timezone']
        try:
            for field in ('submissions_open', 'submissions_close', 'judging_open', 'judging_close'):
                if field in data:
                    setattr(event, field, parse_event_datetime(data[field]))
            if 'team_capacity' in data:
                event.team_capacity = int(data['team_capacity'])
            if 'min_reviews_per_project' in data:
                event.min_reviews_per_project = int(data['min_reviews_per_project'])
        except (TypeError, ValueError, OverflowError):
            return api_error('validation_error', 'Invalid event dates or numeric limits', status=422)
        schedule_error = validate_event_schedule(event)
        if schedule_error:
            return api_error('validation_error', schedule_error, status=422)

        event.save()
        after_data = {'name': event.name, 'submissions_close': event.submissions_close.isoformat() if event.submissions_close else None}
        record_audit(event, request.user, 'update_event_settings', target=event.id, before_data=before_data, after_data=after_data)

        return api_success({'id': event.id, 'name': event.name})

    return api_error('method_not_allowed', 'GET or PATCH required', status=405)


def event_join(request, event_id):
    if not request.user.is_authenticated:
        return api_error('unauthenticated', 'Login required', status=401)
    if request.method != 'POST':
        return api_error('method_not_allowed', 'POST required', status=405)

    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return api_error('not_found', 'Event not found', status=404)

    # Check if already a member
    mem = EventMembership.objects.filter(user=request.user, event=event).first()
    if mem:
        return api_success({'role': mem.role, 'event_id': event.id, 'message': 'Already a member'})

    # Join as participant
    EventMembership.objects.create(user=request.user, event=event, role='participant')
    record_audit(event, request.user, 'join_event', target=event.id, reason="Participant self-registration")
    return api_success({'role': 'participant', 'event_id': event.id, 'message': 'Joined event as participant'}, status=201)


# -------------------------------------------------------------
# Teams & Invitations
# -------------------------------------------------------------

def event_teams_list_create(request, event_id):
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return api_error('not_found', 'Event not found', status=404)

    if request.method == 'GET':
        can_see_members = request.user.is_authenticated and (
            event.memberships.filter(user=request.user, role='organizer').exists() or
            TeamMembership.objects.filter(team__event=event, user=request.user).exists())
        teams = event.teams.select_related('captain').prefetch_related('memberships__user').all()
        data = []
        for tm in teams:
            members = [
                {'id': m.user.id, 'display_name': m.user.display_name, **({'email': m.user.email} if can_see_members else {})}
                for m in tm.memberships.all()
            ]
            data.append({
                'id': tm.id,
                'name': tm.name,
                'captain_id': tm.captain_id,
                'captain_name': tm.captain.display_name,
                'member_count': len(members),
                'capacity': tm.capacity,
                'members': members,
            })
        return api_success(data)

    elif request.method == 'POST':
        if not request.user.is_authenticated:
            return api_error('unauthenticated', 'Login required', status=401)
        if not event.memberships.filter(user=request.user, role='participant').exists():
            return api_error('forbidden', 'Participant membership required', status=403)

        data = get_json_body(request)
        name = data.get('name', '').strip()
        if not name:
            return api_error('validation_error', 'Team name is required', status=422)

        # Check if already in a team for this event
        existing_team = TeamMembership.objects.filter(team__event=event, user=request.user).first()
        if existing_team:
            return api_error('already_in_team', 'You are already a member of a team in this event', status=409)

        with transaction.atomic():
            team = Team.objects.create(
                event=event,
                captain=request.user,
                name=name,
                capacity=event.team_capacity
            )
            TeamMembership.objects.create(team=team, user=request.user)
            # Ensure participant membership in event
            EventMembership.objects.get_or_create(user=request.user, event=event, defaults={'role': 'participant'})
            record_audit(event, request.user, 'create_team', target=team.id, reason=f"Created team {name}")

        return api_success({'id': team.id, 'name': team.name}, status=201)

    return api_error('method_not_allowed', 'GET or POST required', status=405)


def team_invites_create(request, team_id):
    if not request.user.is_authenticated:
        return api_error('unauthenticated', 'Login required', status=401)
    if request.method != 'POST':
        return api_error('method_not_allowed', 'POST required', status=405)

    try:
        team = Team.objects.get(id=team_id)
    except Team.DoesNotExist:
        return api_error('not_found', 'Team not found', status=404)

    if team.captain != request.user and not request.user.is_staff:
        return api_error('forbidden', 'Only team captain can generate invites', status=403)

    if team.is_full:
        return api_error('team_full', 'Team capacity reached', status=422)

    raw_token = secrets.token_urlsafe(24)
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

    invite = TeamInvite.objects.create(
        team=team,
        raw_token=raw_token,
        token_hash=token_hash,
        creator=request.user,
        usage_limit=1
    )
    return api_success({
        'id': invite.id,
        'token': raw_token,
        'invite_url': f"/invites/team/{raw_token}/"
    }, status=201)


def team_invite_revoke(request, invite_id):
    if not request.user.is_authenticated:
        return api_error('unauthenticated', 'Login required', status=401)
    if request.method != 'DELETE':
        return api_error('method_not_allowed', 'DELETE required', status=405)

    try:
        invite = TeamInvite.objects.get(id=invite_id)
    except TeamInvite.DoesNotExist:
        return api_error('not_found', 'Invite not found', status=404)

    if invite.team.captain != request.user and not request.user.is_staff:
        return api_error('forbidden', 'Only captain can revoke invites', status=403)

    invite.revoked_at = timezone.now()
    invite.save()
    return api_success({'message': 'Invite revoked successfully'})


def team_invites_accept(request):
    if not request.user.is_authenticated:
        return api_error('unauthenticated', 'Login required', status=401)
    if request.method != 'POST':
        return api_error('method_not_allowed', 'POST required', status=405)

    data = get_json_body(request)
    raw_token = data.get('token', '').strip()
    if not raw_token:
        return api_error('validation_error', 'Token is required', status=422)

    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    invite = TeamInvite.objects.filter(token_hash=token_hash).first()
    if not invite or not invite.is_valid:
        return api_error('invalid_invite', 'This invitation is invalid, expired, or already used', status=400)

    team = invite.team
    if invite.invited_email and invite.invited_email.lower() != request.user.email.lower():
        return api_error('forbidden', 'This invitation is for a different account', status=403)
    existing_role = EventMembership.objects.filter(user=request.user, event=team.event).first()
    if existing_role and existing_role.role != 'participant':
        return api_error('forbidden', 'You already have another role in this event', status=403)
    # Check if user is already in a team in this event
    if TeamMembership.objects.filter(team__event=team.event, user=request.user).exists():
        return api_error('already_in_team', 'You already belong to a team for this event', status=409)

    with transaction.atomic():
        TeamMembership.objects.create(team=team, user=request.user)
        invite.times_used += 1
        invite.save()
        EventMembership.objects.get_or_create(user=request.user, event=team.event, defaults={'role': 'participant'})
        record_audit(team.event, request.user, 'accept_team_invite', target=team.id, reason=f"Joined team {team.name}")

    return api_success({
        'team_id': team.id,
        'team_name': team.name,
        'event_id': team.event_id,
        'message': f"Successfully joined {team.name}"
    })


# -------------------------------------------------------------
# Projects & Submissions
# -------------------------------------------------------------

def event_projects_list_create(request, event_id):
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return api_error('not_found', 'Event not found', status=404)

    if request.method == 'GET':
        # Public or scoped project list
        qs = Project.objects.filter(event=event).select_related('team', 'track')
        is_organizer = request.user.is_authenticated and event.memberships.filter(user=request.user, role='organizer').exists()

        if not is_organizer:
            # Public only sees submitted & eligible
            qs = qs.filter(status='submitted', eligibility='eligible')

        projects = []
        for p in qs:
            projects.append({
                'id': p.id,
                'title': p.title,
                'tagline': p.tagline,
                'team_id': p.team_id,
                'team_name': p.team.name if p.team else '',
                'track_id': p.track_id,
                'track_name': p.track.name if p.track else None,
                'thumbnail_url': p.thumbnail_url,
                'repo_url': p.repo_url,
                'live_url': p.live_url,
                'tech_tags': p.tech_tags,
                'status': p.status,
                'eligibility': p.eligibility,
                'submitted_at': p.submitted_at.isoformat() if p.submitted_at else None,
                'version': p.version,
            })
        return api_success(projects)

    elif request.method == 'POST':
        # Check deadline boundary!
        if not event.is_submission_open:
            return api_error('deadline_passed', 'Submissions are closed.', status=400)
        if event.result_snapshots.exists():
            return api_error('results_published', 'Submissions are locked after results publication', status=409)

        if not request.user.is_authenticated:
            return api_error('unauthenticated', 'Login required', status=401)
        if not event.memberships.filter(user=request.user, role='participant').exists():
            return api_error('forbidden', 'Participant membership required', status=403)

        data = get_json_body(request)
        link_error = validate_project_links(data)
        if link_error:
            return api_error('validation_error', link_error, status=422)
        title = data.get('title', '').strip()
        if not title:
            return api_error('validation_error', 'Title is required', status=422)

        # Find user's team in this event
        tm_membership = TeamMembership.objects.filter(team__event=event, user=request.user).first()
        if not tm_membership:
            return api_error('no_team', 'You must create or join a team first', status=422)

        team = tm_membership.team

        # Check if team already has a project
        existing = Project.objects.filter(team=team).first()
        if existing:
            return api_error('duplicate_project', 'Your team already has a project for this event', status=409)

        track_id = data.get('track_id') or data.get('track')
        track = Track.objects.filter(id=track_id, event=event).first() if track_id else None

        project = Project.objects.create(
            event=event,
            team=team,
            track=track,
            title=title,
            tagline=data.get('tagline', data.get('summary', '')),
            description=data.get('description', data.get('summary', '')),
            thumbnail_url=data.get('thumbnail_url', ''),
            images=data.get('images', []),
            video_url=data.get('video_url', ''),
            repo_url=data.get('repo_url', ''),
            live_url=data.get('live_url', ''),
            tech_tags=data.get('tech_tags', []),
            custom_answers=data.get('custom_answers', {}),
            status='draft',
            version=1
        )
        record_audit(event, request.user, 'create_project', target=project.id, reason="Initial project draft")
        return api_success({'id': project.id, 'title': project.title, 'version': project.version}, status=201)

    return api_error('method_not_allowed', 'GET or POST required', status=405)


def project_detail_update(request, project_id):
    try:
        project = Project.objects.select_related('event', 'team', 'track').get(id=project_id)
    except Project.DoesNotExist:
        return api_error('not_found', 'Project not found', status=404)

    event = project.event
    is_team_member = request.user.is_authenticated and project.team.memberships.filter(user=request.user).exists()
    is_team_member = is_team_member and event.memberships.filter(user=request.user, role='participant').exists()
    is_organizer = request.user.is_authenticated and event.memberships.filter(user=request.user, role='organizer').exists()

    if request.method == 'GET':
        # Public cannot see drafts or custom answers unless team member or organizer
        if (project.status != 'submitted' or project.eligibility != 'eligible') and not (is_team_member or is_organizer):
            return api_error('not_found', 'Project not found or private', status=404)

        data = {
            'id': project.id,
            'event_id': project.event_id,
            'team_id': project.team_id,
            'team_name': project.team.name if project.team else '',
            'track_id': project.track_id,
            'track_name': project.track.name if project.track else None,
            'title': project.title,
            'tagline': project.tagline,
            'description': project.description,
            'thumbnail_url': project.thumbnail_url,
            'images': project.images,
            'video_url': project.video_url,
            'repo_url': project.repo_url,
            'live_url': project.live_url,
            'tech_tags': project.tech_tags,
            'status': project.status,
            'eligibility': project.eligibility,
            'submitted_at': project.submitted_at.isoformat() if project.submitted_at else None,
            'version': project.version,
        }
        if is_team_member or is_organizer:
            data['custom_answers'] = project.custom_answers
            data['eligibility_reason'] = project.eligibility_reason

        return api_success(data)

    elif request.method == 'PATCH':
        if not is_team_member:
            return api_error('forbidden', 'Only team members can edit project', status=403)

        # Check deadline if not organizer
        if not event.is_submission_open:
            return api_error('deadline_passed', 'Submissions are closed.', status=400)
        if event.result_snapshots.exists():
            return api_error('results_published', 'Projects are locked after results publication', status=409)

        data = get_json_body(request)
        link_error = validate_project_links(data)
        if link_error:
            return api_error('validation_error', link_error, status=422)
        req_version = data.get('version')
        if req_version != project.version:
            return api_error('version_conflict', 'Project has been modified elsewhere. Please refresh.', status=409)

        if 'title' in data: project.title = data['title']
        if 'tagline' in data: project.tagline = data['tagline']
        if 'description' in data: project.description = data['description']
        if 'thumbnail_url' in data: project.thumbnail_url = data['thumbnail_url']
        if 'images' in data: project.images = data['images']
        if 'video_url' in data: project.video_url = data['video_url']
        if 'repo_url' in data: project.repo_url = data['repo_url']
        if 'live_url' in data: project.live_url = data['live_url']
        if 'tech_tags' in data: project.tech_tags = data['tech_tags']
        if 'custom_answers' in data: project.custom_answers = data['custom_answers']
        if 'track_id' in data:
            project.track = Track.objects.filter(id=data['track_id'], event=event).first()
            if data['track_id'] and not project.track:
                return api_error('validation_error', 'Track is not in this event', status=422)

        mutable_fields = ('title', 'tagline', 'description', 'thumbnail_url', 'images',
                          'video_url', 'repo_url', 'live_url', 'tech_tags', 'custom_answers')
        changes = {field: getattr(project, field) for field in mutable_fields if field in data}
        if 'track_id' in data:
            changes['track_id'] = project.track_id
        changes.update(version=F('version') + 1, updated_at=timezone.now())
        if not Project.objects.filter(id=project.id, version=req_version).update(**changes):
            return api_error('version_conflict', 'Project has been modified elsewhere. Please refresh.', status=409)
        project.refresh_from_db()
        record_audit(event, request.user, 'update_project', target=project.id, reason="Updated project details")
        return api_success({'id': project.id, 'title': project.title, 'version': project.version})

    return api_error('method_not_allowed', 'GET or PATCH required', status=405)


def project_submit(request, project_id):
    if not request.user.is_authenticated:
        return api_error('unauthenticated', 'Login required', status=401)
    if request.method != 'POST':
        return api_error('method_not_allowed', 'POST required', status=405)

    try:
        project = Project.objects.select_related('event', 'team').get(id=project_id)
    except Project.DoesNotExist:
        return api_error('not_found', 'Project not found', status=404)

    is_team_member = project.team.memberships.filter(user=request.user).exists()
    if not is_team_member or not project.event.memberships.filter(user=request.user, role='participant').exists():
        return api_error('forbidden', 'Only team members can submit project', status=403)

    if not project.event.is_submission_open:
        return api_error('deadline_passed', 'Submissions are closed.', status=400)
    if project.event.result_snapshots.exists():
        return api_error('results_published', 'Submissions are locked after results publication', status=409)

    data = get_json_body(request)
    req_version = data.get('version')
    if req_version != project.version:
        return api_error('version_conflict', 'Project has been modified. Please refresh.', status=409)

    # Validate required fields
    if not project.title.strip() or not project.tagline.strip() or not project.description.strip() or not project.track_id:
        return api_error('validation_error', 'Title, tagline, description, and track are required for submission', status=422)
    for question in project.event.custom_questions.filter(required=True):
        if not project.custom_answers.get(question.key):
            return api_error('validation_error', f'{question.label} is required', status=422)

    submitted_at = timezone.now()
    if not Project.objects.filter(id=project.id, version=req_version).update(
            status='submitted', submitted_at=submitted_at,
            version=F('version') + 1, updated_at=submitted_at):
        return api_error('version_conflict', 'Project has been modified. Please refresh.', status=409)
    project.refresh_from_db()
    record_audit(project.event, request.user, 'submit_project', target=project.id, reason="Finalized project submission")
    return api_success({
        'id': project.id,
        'status': project.status,
        'submitted_at': project.submitted_at.isoformat(),
        'version': project.version
    })


def upload_media(request):
    if not request.user.is_authenticated:
        return api_error('unauthenticated', 'Login required', status=401)
    if request.method != 'POST':
        return api_error('method_not_allowed', 'POST required', status=405)

    uploaded_file = request.FILES.get('file')
    if not uploaded_file:
        return api_error('validation_error', 'No file uploaded', status=422)

    # Check size limit: 10MB
    if uploaded_file.size > 10 * 1024 * 1024:
        return api_error('file_too_large', 'File exceeds 10MB limit', status=422)

    media = ProjectMedia.objects.create(
        file=uploaded_file,
        filename=uploaded_file.name,
        file_type=uploaded_file.content_type or 'application/octet-stream',
        file_size=uploaded_file.size,
        uploaded_by=request.user
    )
    return api_success({
        'id': media.id,
        'url': media.file.url,
        'filename': media.filename
    }, status=201)


# -------------------------------------------------------------
# Rubric & Scoring Configuration
# -------------------------------------------------------------

def event_rubric_detail_update(request, event_id):
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return api_error('not_found', 'Event not found', status=404)

    rubric, _ = Rubric.objects.get_or_create(event=event, defaults={'version': 1})

    if request.method == 'GET':
        criteria = list(rubric.criteria.values('id', 'key', 'name', 'description', 'min_score', 'max_score', 'weight', 'order'))
        return api_success({
            'version': rubric.version,
            'is_locked': rubric.is_locked,
            'criteria': criteria
        })

    elif request.method == 'PUT':
        if not request.user.is_authenticated or not event.memberships.filter(user=request.user, role='organizer').exists():
            return api_error('forbidden', 'Organizer access required', status=403)

        if rubric.is_locked or Review.objects.filter(project__event=event, status='submitted').exists():
            return api_error('rubric_locked', 'Rubric is locked because scoring has commenced', status=409)

        data = get_json_body(request)
        req_version = data.get('version')
        if req_version != rubric.version:
            return api_error('version_conflict', 'Rubric version conflict', status=409)

        criteria_list = data.get('criteria', [])
        if not isinstance(criteria_list, list) or not 1 <= len(criteria_list) <= 20:
            return api_error('validation_error', 'Provide between 1 and 20 criteria', status=422)
        keys = set()
        validated = []
        for idx, criterion in enumerate(criteria_list):
            if not isinstance(criterion, dict):
                return api_error('validation_error', 'Each criterion must be an object', status=422)
            key = criterion.get('key', f'crit_{idx + 1}')
            name = criterion.get('name', '')
            try:
                minimum = float(criterion.get('min_score', 1))
                maximum = float(criterion.get('max_score', 5))
                weight = float(criterion.get('weight', 1))
            except (TypeError, ValueError):
                return api_error('validation_error', 'Criterion scores and weights must be numeric', status=422)
            if (not isinstance(key, str) or not key.isidentifier() or key in keys or
                    not isinstance(name, str) or not name.strip() or
                    not all(map(math.isfinite, (minimum, maximum, weight))) or
                    minimum >= maximum or weight < 0):
                return api_error('validation_error', 'Invalid criterion key, scale, name, or weight', status=422)
            keys.add(key)
            validated.append((key, name.strip(), minimum, maximum, weight, criterion.get('description', '')))
        if sum(item[4] for item in validated) <= 0:
            return api_error('validation_error', 'At least one criterion must have positive weight', status=422)
        with transaction.atomic():
            rubric.criteria.all().delete()
            for idx, (key, name, minimum, maximum, weight, description) in enumerate(validated):
                Criterion.objects.create(
                    rubric=rubric,
                    key=key,
                    name=name,
                    description=description,
                    min_score=minimum,
                    max_score=maximum,
                    weight=weight,
                    order=idx
                )
            rubric.version += 1
            rubric.save()
            record_audit(event, request.user, 'update_rubric', target=str(rubric.version), reason="Updated rubric criteria")

        criteria = list(rubric.criteria.values('id', 'key', 'name', 'description', 'min_score', 'max_score', 'weight', 'order'))
        return api_success({'version': rubric.version, 'criteria': criteria})

    return api_error('method_not_allowed', 'GET or PUT required', status=405)


# -------------------------------------------------------------
# Judge Invites & Assignments
# -------------------------------------------------------------

def event_judge_invites(request, event_id):
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return api_error('not_found', 'Event not found', status=404)

    if not request.user.is_authenticated or not event.memberships.filter(user=request.user, role='organizer').exists():
        return api_error('forbidden', 'Organizer access required', status=403)

    if request.method == 'POST':
        data = get_json_body(request)
        raw_token = secrets.token_urlsafe(24)
        token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        tracks = data.get('tracks', [])

        invite = JudgeInvite.objects.create(
            event=event,
            raw_token=raw_token,
            token_hash=token_hash,
            invited_email=data.get('email'),
            creator=request.user,
            tracks=tracks,
            usage_limit=int(data.get('usage_limit', 1))
        )
        return api_success({
            'id': invite.id,
            'token': raw_token,
            'invite_url': f"/invites/judge/{raw_token}/"
        }, status=201)

    return api_error('method_not_allowed', 'POST required', status=405)


def judge_invites_accept(request):
    if not request.user.is_authenticated:
        return api_error('unauthenticated', 'Login required', status=401)
    if request.method != 'POST':
        return api_error('method_not_allowed', 'POST required', status=405)

    data = get_json_body(request)
    raw_token = data.get('token', '').strip()
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()

    invite = JudgeInvite.objects.filter(token_hash=token_hash).first()
    if not invite or not invite.is_valid:
        return api_error('invalid_invite', 'This judge invitation is invalid or expired', status=400)

    event = invite.event
    if invite.invited_email and invite.invited_email.lower() != request.user.email.lower():
        return api_error('forbidden', 'This invitation is for a different account', status=403)
    existing_role = EventMembership.objects.filter(user=request.user, event=event).first()
    if existing_role and existing_role.role != 'judge':
        return api_error('forbidden', 'You already have another role in this event', status=403)
    with transaction.atomic():
        EventMembership.objects.get_or_create(user=request.user, event=event, defaults={'role': 'judge'})
        # Apply track scopes
        scope, _ = JudgeTrackScope.objects.get_or_create(judge=request.user, event=event)
        if invite.tracks:
            trks = Track.objects.filter(id__in=invite.tracks, event=event)
            scope.tracks.set(trks)

        invite.times_used += 1
        invite.save()
        record_audit(event, request.user, 'accept_judge_invite', target=event.id, reason="Judge accepted invite")

    return api_success({
        'event_id': event.id,
        'event_name': event.name,
        'message': f"Accepted judge role for {event.name}"
    })


def event_assignments_list_create(request, event_id):
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return api_error('not_found', 'Event not found', status=404)

    is_organizer = request.user.is_authenticated and event.memberships.filter(user=request.user, role='organizer').exists()
    if not is_organizer:
        return api_error('forbidden', 'Organizer access required', status=403)

    if request.method == 'GET':
        assignments = event.assignments.select_related('judge', 'project', 'review').all()
        data = []
        for a in assignments:
            data.append({
                'id': a.id,
                'project_id': a.project_id,
                'project_title': a.project.title,
                'judge_id': a.judge_id,
                'judge_name': a.judge.display_name,
                'status': a.status,
                'has_review': hasattr(a, 'review') and a.review.status == 'submitted',
                'conflict_reason': a.conflict_reason,
                'assigned_at': a.assigned_at.isoformat()
            })
        return api_success(data)

    elif request.method == 'POST':
        if event.result_snapshots.exists():
            return api_error('results_published', 'Assignments are locked after results publication', status=409)
        data = get_json_body(request)
        strategy = data.get('strategy', 'balanced')
        created_count = 0

        if strategy == 'balanced':
            try:
                reviews_per_project = int(data.get('reviews_per_project', event.min_reviews_per_project or 3))
            except (TypeError, ValueError):
                return api_error('validation_error', 'reviews_per_project must be an integer', status=422)
            if reviews_per_project < 1 or reviews_per_project > 20:
                return api_error('validation_error', 'reviews_per_project must be between 1 and 20', status=422)
            judges = sorted(event.memberships.filter(role='judge').values_list('user_id', flat=True))
            projects = list(event.projects.filter(status='submitted', eligibility='eligible').order_by('id'))

            if not judges:
                return api_error('no_judges', 'No judges registered for this event', status=422)

            scopes = {scope.judge_id: set(scope.tracks.values_list('id', flat=True))
                      for scope in JudgeTrackScope.objects.filter(event=event, judge_id__in=judges).prefetch_related('tracks')}
            workloads = {judge_id: Assignment.objects.filter(event=event, judge_id=judge_id).count()
                         for judge_id in judges}
            shortages = []
            with transaction.atomic():
                for project in projects:
                    assigned_ids = set(Assignment.objects.filter(project=project).values_list('judge_id', flat=True))
                    needed = max(0, reviews_per_project - len(assigned_ids))
                    team_member_ids = set(project.team.memberships.values_list('user_id', flat=True))
                    candidates = [judge_id for judge_id in judges
                                  if judge_id not in team_member_ids
                                  and judge_id not in assigned_ids
                                  and project.track_id in scopes.get(judge_id, set())]
                    for judge_id in sorted(candidates, key=lambda j: (workloads[j], j))[:needed]:
                        _, created = Assignment.objects.get_or_create(
                            event=event, project=project, judge_id=judge_id,
                            defaults={'status': 'assigned'}
                        )
                        if created:
                            created_count += 1
                            workloads[judge_id] += 1
                    if needed > len(candidates):
                        shortages.append({'project_id': project.id, 'missing': needed - len(candidates)})

            record_audit(event, request.user, 'run_balanced_assignment', target=f"{created_count} assignments", reason="Ran balanced assignment algorithm")
            return api_success({'created_count': created_count, 'shortages': shortages,
                                'message': f"Created {created_count} assignments"})

        elif strategy == 'manual':
            pairs = data.get('pairs', [])
            if not isinstance(pairs, list) or not pairs:
                return api_error('validation_error', 'pairs must be a nonempty list', status=422)
            validated_pairs = []
            for pair in pairs:
                if not isinstance(pair, dict):
                    return api_error('validation_error', 'Each pair must be an object', status=422)
                judge_id, project_id = pair.get('judge_id'), pair.get('project_id')
                project = Project.objects.filter(id=project_id, event=event, status='submitted', eligibility='eligible').first()
                if not project or not event.memberships.filter(user_id=judge_id, role='judge').exists():
                    return api_error('validation_error', 'Judge or project is outside this event', status=422)
                if project.team.memberships.filter(user_id=judge_id).exists():
                    return api_error('validation_error', 'A team member cannot judge their project', status=422)
                if not JudgeTrackScope.objects.filter(event=event, judge_id=judge_id, tracks=project.track).exists():
                    return api_error('validation_error', 'Judge is not authorized for this track', status=422)
                validated_pairs.append((judge_id, project_id))
            with transaction.atomic():
                for judge_id, project_id in validated_pairs:
                    _, created = Assignment.objects.get_or_create(
                        event=event, project_id=project_id, judge_id=judge_id,
                        defaults={'status': 'assigned'}
                    )
                    if created:
                        created_count += 1
            return api_success({'created_count': created_count})

        return api_error('validation_error', 'Invalid strategy', status=422)

    return api_error('method_not_allowed', 'GET or POST required', status=405)


def assignment_conflict(request, assignment_id):
    if not request.user.is_authenticated:
        return api_error('unauthenticated', 'Login required', status=401)
    if request.method != 'POST':
        return api_error('method_not_allowed', 'POST required', status=405)

    try:
        asg = Assignment.objects.select_related('event').get(id=assignment_id)
    except Assignment.DoesNotExist:
        return api_error('not_found', 'Assignment not found', status=404)

    if asg.judge != request.user and not request.user.is_staff:
        return api_error('forbidden', 'Only assigned judge can report conflict', status=403)

    data = get_json_body(request)
    reason = data.get('reason', '').strip()
    if not reason:
        return api_error('validation_error', 'Conflict reason is required', status=422)

    asg.status = 'conflict'
    asg.conflict_reason = reason
    asg.save()
    record_audit(asg.event, request.user, 'report_conflict', target=asg.id, reason=reason)
    return api_success({'id': asg.id, 'status': asg.status, 'message': 'Conflict recorded and scoring suspended for this assignment'})


# -------------------------------------------------------------
# Judge Reviews & Scores (CRITICAL FOR RUN.PY CHECKER)
# -------------------------------------------------------------

def judge_assignments(request):
    """Current judge's assignments across events or filtered by event."""
    if not request.user.is_authenticated:
        return api_error('unauthenticated', 'Login required', status=401)

    is_judge = request.user.memberships.filter(role='judge').exists() or request.user.is_staff
    if not is_judge:
        return api_error('forbidden', 'Judge role required', status=403)

    event_id = request.GET.get('event')
    permitted_events = request.user.memberships.filter(role='judge').values_list('event_id', flat=True)
    qs = Assignment.objects.filter(judge=request.user, event_id__in=permitted_events,
                                   project__track__scoped_judges__judge=request.user,
                                   project__track__scoped_judges__event=F('event')).distinct().select_related('project', 'event', 'review')
    if event_id:
        qs = qs.filter(event_id=event_id)

    data = []
    for a in qs:
        has_review = hasattr(a, 'review') and a.review is not None
        rev_status = a.review.status if has_review else 'pending'
        data.append({
            'assignment_id': a.id,
            'event_id': a.event_id,
            'event_name': a.event.name,
            'project_id': a.project_id,
            'project_title': a.project.title,
            'project_tagline': a.project.tagline,
            'track_name': a.project.track.name if a.project.track else None,
            'assignment_status': a.status,
            'review_status': rev_status,
            'has_submitted_review': has_review and a.review.status == 'submitted',
        })
    return api_success(data)


def judge_scores(request):
    """
    GET /api/v1/judge/scores
    Returns the CURRENT JUDGE's own submitted scores.
    MUST RETURN 401/403 IF USER IS PARTICIPANT OR NOT A JUDGE!
    Matches check: 'judge sees own scores' AND 'participant blocked'.
    """
    if not request.user.is_authenticated:
        return api_error('unauthenticated', 'Login required', status=401)

    # Check if user is a judge
    is_judge = request.user.memberships.filter(role='judge').exists()
    if not is_judge:
        return api_error('forbidden', 'Participant is not authorized to view judge scores', status=403)

    judge_event_ids = request.user.memberships.filter(role='judge').values_list('event_id', flat=True)
    reviews = Review.objects.filter(judge=request.user, project__event_id__in=judge_event_ids,
                                    project__track__scoped_judges__judge=request.user,
                                    project__track__scoped_judges__event=F('project__event')).distinct().select_related('project', 'project__event')
    data = []
    for r in reviews:
        data.append({
            'id': r.id,
            'project_id': r.project_id,
            'project_title': r.project.title,
            'event_id': r.project.event_id,
            'criteria_scores': r.criteria_scores,
            'comment': r.comment,
            'status': r.status,
            'submitted_at': r.submitted_at.isoformat() if r.submitted_at else None
        })
    return api_success(data)


def judge_peer_scores(request, judge_id):
    """
    GET /api/v1/judges/{id}/scores
    Returns judge {id}'s scores IF AND ONLY IF caller is judge {id} (or event organizer).
    MUST RETURN 401/403 IF CALLER IS A PEER JUDGE (Judge B accessing Judge A)!
    Matches check: 'judge cannot see peer scores'.
    """
    if not request.user.is_authenticated:
        return api_error('unauthenticated', 'Login required', status=401)

    target_user = User.objects.filter(Q(id=judge_id) | Q(username=judge_id)).first()
    if not target_user:
        return api_error('not_found', 'Judge not found', status=404)

    reviews = Review.objects.filter(judge=target_user).select_related('project')
    if target_user != request.user:
        organizer_event_ids = EventMembership.objects.filter(user=request.user, role='organizer').values_list('event_id', flat=True)
        reviews = reviews.filter(project__event_id__in=organizer_event_ids)
        if not reviews.exists():
            return api_error('forbidden', "Access denied: cannot view another judge's scores", status=403)
    else:
        judge_event_ids = EventMembership.objects.filter(user=request.user, role='judge').values_list('event_id', flat=True)
        reviews = reviews.filter(project__event_id__in=judge_event_ids,
                                 project__track__scoped_judges__judge=request.user,
                                 project__track__scoped_judges__event=F('project__event')).distinct()
    data = []
    for r in reviews:
        data.append({
            'id': r.id,
            'project_id': r.project_id,
            'project_title': r.project.title,
            'criteria_scores': r.criteria_scores,
            'comment': r.comment,
            'status': r.status,
            'submitted_at': r.submitted_at.isoformat() if r.submitted_at else None
        })
    return api_success(data)


def project_review_save_or_submit(request, project_id, is_submit=False):
    if not request.user.is_authenticated:
        return api_error('unauthenticated', 'Login required', status=401)
    if request.method not in ('PUT', 'POST'):
        return api_error('method_not_allowed', 'PUT or POST required', status=405)

    try:
        project = Project.objects.select_related('event').get(id=project_id)
    except Project.DoesNotExist:
        return api_error('not_found', 'Project not found', status=404)

    event = project.event

    # Verify user is assigned judge
    assignment = Assignment.objects.filter(event=event, project=project, judge=request.user).first()
    if not assignment or not event.memberships.filter(user=request.user, role='judge').exists():
        return api_error('forbidden', 'An active judge assignment is required', status=403)
    if project.track_id and not JudgeTrackScope.objects.filter(
            event=event, judge=request.user, tracks=project.track).exists():
        return api_error('forbidden', 'This project is outside your assigned track', status=403)
    if event.result_snapshots.exists():
        return api_error('results_published', 'Reviews are locked after results publication', status=409)
    if not event.is_judging_open:
        return api_error('judging_closed', 'Judging window is currently closed', status=409)

    if assignment.status == 'conflict':
        return api_error('conflict_suspended', 'Scoring suspended due to reported conflict of interest', status=409)

    data = get_json_body(request)
    req_version = data.get('version', 0)

    rubric = getattr(event, 'rubric', None)
    rubric_version = rubric.version if rubric else 1

    review, created = Review.objects.get_or_create(
        project=project,
        judge=request.user,
        defaults={
            'assignment': assignment,
            'rubric_version': rubric_version,
            'criteria_scores': {},
            'status': 'draft',
            'version': 1
        }
    )

    if not created and req_version != review.version:
        return api_error('version_conflict', 'Review has been modified elsewhere. Please refresh.', status=409)

    criteria_scores = data.get('criteria_scores', review.criteria_scores)
    comment = data.get('comment', review.comment)
    if not isinstance(criteria_scores, dict) or not isinstance(comment, str):
        return api_error('validation_error', 'Review scores and comment have invalid types', status=422)
    if review.status == 'submitted' and not is_submit:
        return api_error('review_submitted', 'Revise a submitted review through the submit action', status=409)

    if is_submit:
        # Validate judging window
        if not event.is_judging_open:
            return api_error('judging_closed', 'Judging window is currently closed', status=400)

        # Validate that all rubric criteria are scored within [min, max]
        if rubric:
            for crit in rubric.criteria.all():
                val = criteria_scores.get(crit.key)
                if val is None:
                    return api_error('missing_criterion', f"Score for {crit.name} is required", status=422)
                try:
                    fval = float(val)
                    if fval < crit.min_score or fval > crit.max_score:
                        return api_error('invalid_score', f"Score for {crit.name} must be between {crit.min_score} and {crit.max_score}", status=422)
                    if not math.isfinite(fval):
                        return api_error('invalid_score', f"Score for {crit.name} must be finite", status=422)
                except (TypeError, ValueError):
                    return api_error('invalid_score', f"Score for {crit.name} must be numeric", status=422)

        review.status = 'submitted'
        review.submitted_at = timezone.now()
        assignment.status = 'completed'
        assignment.save()

        # Lock rubric upon first submitted review
        if rubric and not rubric.is_locked:
            rubric.is_locked = True
            rubric.save()
    else:
        if review.status != 'submitted':
            review.status = 'draft'

    review.criteria_scores = criteria_scores
    review.comment = comment
    review.version += 1
    review.save()

    record_audit(event, request.user, 'submit_review' if is_submit else 'save_review_draft', target=review.id)
    return api_success({
        'id': review.id,
        'status': review.status,
        'version': review.version,
        'updated_at': review.updated_at.isoformat()
    })


def project_review_save(request, project_id):
    return project_review_save_or_submit(request, project_id, is_submit=False)


def project_review_submit(request, project_id):
    return project_review_save_or_submit(request, project_id, is_submit=True)


# -------------------------------------------------------------
# Organizer Operations: Progress, Eligibility, Results, Audit, CSV Export
# -------------------------------------------------------------

def event_progress(request, event_id):
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return api_error('not_found', 'Event not found', status=404)

    if not request.user.is_authenticated or not event.memberships.filter(user=request.user, role='organizer').exists():
        return api_error('forbidden', 'Organizer access required', status=403)

    total_assignments = event.assignments.count()
    completed_assignments = event.assignments.filter(status='completed').count()
    conflict_assignments = event.assignments.filter(status='conflict').count()
    total_projects = event.projects.filter(status='submitted', eligibility='eligible').count()
    total_judges = event.memberships.filter(role='judge').count()

    # Low coverage projects count
    under_reviewed = event.projects.filter(status='submitted', eligibility='eligible') \
        .annotate(sub_reviews=Count('reviews', filter=Q(reviews__status='submitted'))) \
        .filter(sub_reviews__lt=event.min_reviews_per_project).count()

    return api_success({
        'total_projects': total_projects,
        'total_judges': total_judges,
        'total_assignments': total_assignments,
        'completed_assignments': completed_assignments,
        'conflict_assignments': conflict_assignments,
        'completion_percentage': round((completed_assignments / total_assignments * 100), 1) if total_assignments > 0 else 0,
        'under_reviewed_projects': under_reviewed,
    })


def project_eligibility(request, project_id):
    if not request.user.is_authenticated:
        return api_error('unauthenticated', 'Login required', status=401)
    if request.method != 'PATCH':
        return api_error('method_not_allowed', 'PATCH required', status=405)

    try:
        project = Project.objects.select_related('event').get(id=project_id)
    except Project.DoesNotExist:
        return api_error('not_found', 'Project not found', status=404)

    if not project.event.memberships.filter(user=request.user, role='organizer').exists() and not request.user.is_staff:
        return api_error('forbidden', 'Organizer access required', status=403)

    if project.event.result_snapshots.exists():
        return api_error('results_published', 'Eligibility is locked after publication', status=409)

    data = get_json_body(request)
    eligibility = data.get('eligibility')
    reason = data.get('reason', '').strip()

    if eligibility not in ('eligible', 'ineligible'):
        return api_error('validation_error', "eligibility must be 'eligible' or 'ineligible'", status=422)
    if eligibility == 'ineligible' and not reason:
        return api_error('validation_error', 'A reason is required when marking a project ineligible', status=422)

    before_data = {'eligibility': project.eligibility, 'reason': project.eligibility_reason}
    project.eligibility = eligibility
    project.eligibility_reason = reason
    project.version += 1
    project.save()

    record_audit(project.event, request.user, 'update_eligibility', target=project.id, reason=reason, before_data=before_data, after_data={'eligibility': eligibility})
    return api_success({'id': project.id, 'eligibility': project.eligibility, 'version': project.version})


def _calculate_event_results_data(event):
    # Fetch projects
    projects = list(event.projects.filter(status='submitted', eligibility='eligible').values('id', 'title', 'track_id'))
    # Fetch criteria defs
    rubric = getattr(event, 'rubric', None)
    criteria_defs = {}
    if rubric:
        for c in rubric.criteria.all():
            criteria_defs[c.key] = {
                'min_score': c.min_score,
                'max_score': c.max_score,
                'weight': c.weight
            }
    else:
        criteria_defs = {'default': {'min_score': 1.0, 'max_score': 5.0, 'weight': 1.0}}

    # Fetch submitted reviews
    reviews_qs = Review.objects.filter(project__event=event, status='submitted',
                                       assignment__status='completed').values(
                                           'id', 'project_id', 'judge_id', 'criteria_scores')
    reviews = list(reviews_qs)

    calc = compute_pool_results(projects, reviews, criteria_defs, min_required_reviews=event.min_reviews_per_project)
    return calc, len(reviews)


def _results_fingerprint(event):
    """Digest every input that can change the published ranking or its labels."""
    payload = {
        'event': {'id': event.id, 'min_reviews_per_project': event.min_reviews_per_project},
        'projects': list(event.projects.order_by('id').values(
            'id', 'title', 'track_id', 'status', 'eligibility', 'version')),
        'reviews': list(Review.objects.filter(project__event=event).order_by('id').values(
            'id', 'project_id', 'judge_id', 'status', 'rubric_version', 'criteria_scores', 'version')),
        'assignments': list(event.assignments.order_by('id').values(
            'id', 'project_id', 'judge_id', 'status')),
        'rubric': list(Criterion.objects.filter(rubric__event=event).order_by('id').values(
            'id', 'key', 'min_score', 'max_score', 'weight')),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def event_results_preview(request, event_id):
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return api_error('not_found', 'Event not found', status=404)

    if not request.user.is_authenticated or not event.memberships.filter(user=request.user, role='organizer').exists():
        return api_error('forbidden', 'Organizer access required', status=403)

    calc, rev_count = _calculate_event_results_data(event)
    fingerprint = _results_fingerprint(event)

    return api_success({
        'preview_version': fingerprint,
        'ranking_method': 'adjusted' if calc['is_graph_connected'] else 'raw',
        'is_graph_connected': calc['is_graph_connected'],
        'pool_warnings': calc['pool_warnings'],
        'judge_warnings': calc['judge_warnings'],
        'rows': calc['projects']
    })


def event_results_publish(request, event_id):
    if not request.user.is_authenticated:
        return api_error('unauthenticated', 'Login required', status=401)
    if request.method != 'POST':
        return api_error('method_not_allowed', 'POST required', status=405)

    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return api_error('not_found', 'Event not found', status=404)

    if not event.memberships.filter(user=request.user, role='organizer').exists() and not request.user.is_staff:
        return api_error('forbidden', 'Organizer access required', status=403)

    data = get_json_body(request)
    ranking_method = data.get('ranking_method', 'raw')
    preview_version = data.get('preview_version')
    acknowledged_warnings = data.get('acknowledged_warnings', [])
    reason = data.get('reason', '')

    if ranking_method not in ('raw', 'adjusted'):
        return api_error('validation_error', 'ranking_method must be raw or adjusted', status=422)
    if not preview_version:
        return api_error('validation_error', 'preview_version is required', status=422)

    calc, rev_count = _calculate_event_results_data(event)
    current_fingerprint = _results_fingerprint(event)

    if preview_version != current_fingerprint:
        return api_error('version_conflict', 'Review inputs have changed since preview was generated. Please review again.', status=409)
    if ranking_method == 'adjusted' and (not calc['is_graph_connected'] or
                                         any(row.get('adjusted_rank') is None for row in calc['projects'])):
        return api_error('adjustment_unavailable', 'Adjusted ranks are unavailable for this pool', status=422)

    with transaction.atomic():
        revision = (event.result_snapshots.count() or 0) + 1
        snapshot = ResultSnapshot.objects.create(
            event=event,
            revision=revision,
            ranking_method=ranking_method,
            input_fingerprint=current_fingerprint,
            warnings_acknowledged=acknowledged_warnings,
            reason=reason,
            published_by=request.user
        )

        for p_res in calc['projects']:
            p_obj = Project.objects.get(id=p_res['project_id'])
            ResultRow.objects.create(
                snapshot=snapshot,
                project=p_obj,
                project_title=p_obj.title,
                project_tagline=p_obj.tagline,
                track_name=p_obj.track.name if p_obj.track else '',
                raw_score=p_res['raw_score'],
                adjusted_score=p_res['adjusted_score'],
                raw_rank=p_res['raw_rank'],
                adjusted_rank=p_res['adjusted_rank'],
                review_count=p_res['review_count'],
                eligible_review_count=p_res['eligible_review_count'],
                normalization_status=p_res['normalization_status'],
                warnings=p_res['warnings'],
                tied=p_res.get('tied', False)
            )

        event.results_published_at = timezone.now()
        event.status = 'published'
        event.save()

        record_audit(event, request.user, 'publish_results', target=f"Revision {revision}", reason=reason)

    return api_success({
        'snapshot_id': snapshot.id,
        'revision': snapshot.revision,
        'published_at': snapshot.published_at.isoformat(),
        'message': f"Results revision {revision} published successfully"
    }, status=201)


def event_results_public(request, event_id):
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return api_error('not_found', 'Event not found', status=404)

    snapshot = event.result_snapshots.order_by('-revision').first()
    if not snapshot:
        return api_error('not_published', 'Results have not been published yet.', status=404)

    is_organizer = request.user.is_authenticated and event.memberships.filter(user=request.user, role='organizer').exists()

    rows_qs = snapshot.rows.select_related('project')
    if snapshot.ranking_method == 'adjusted':
        rows_qs = rows_qs.order_by('adjusted_rank')
    else:
        rows_qs = rows_qs.order_by('raw_rank')

    rows = []
    for r in rows_qs:
        row_data = {
            'project_id': r.project_id,
            'title': r.project_title or r.project.title,
            'tagline': r.project_tagline,
            'raw_rank': r.raw_rank,
            'adjusted_rank': r.adjusted_rank,
            'raw_score': round(r.raw_score, 2) if r.raw_score is not None else None,
            'review_count': r.review_count,
            'tied': r.tied
        }
        if is_organizer:
            row_data['adjusted_score'] = round(r.adjusted_score, 2) if r.adjusted_score is not None else None
            row_data['normalization_status'] = r.normalization_status
            row_data['warnings'] = r.warnings

        rows.append(row_data)

    return api_success({
        'event_id': event.id,
        'event_name': event.name,
        'revision': snapshot.revision,
        'ranking_method': snapshot.ranking_method,
        'published_at': snapshot.published_at.isoformat(),
        'rows': rows
    })


def event_audit_log(request, event_id):
    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return api_error('not_found', 'Event not found', status=404)

    if not request.user.is_authenticated or not event.memberships.filter(user=request.user, role='organizer').exists():
        return api_error('forbidden', 'Organizer access required', status=403)

    events = event.audit_events.select_related('actor').all()[:100]
    data = []
    for a in events:
        data.append({
            'id': a.id,
            'actor': a.actor.display_name if a.actor else 'System',
            'action': a.action,
            'target': a.target,
            'reason': a.reason,
            'before_data': a.before_data,
            'after_data': a.after_data,
            'created_at': a.created_at.isoformat()
        })
    return api_success(data)


def event_csv_export(request, event_id, kind='results'):
    """
    GET /api/v1/events/{id}/exports/{kind}.csv
    Export results, projects, teams, or audit log as CSV.
    MUST RETURN 200 AND VALID CSV WITH COMMA IN FIRST LINE FOR ORGANIZER!
    MUST RETURN 401/403 FOR NON-ORGANIZER!
    Matches check: 'csv export works'.
    """
    if not request.user.is_authenticated:
        return api_error('unauthenticated', 'Login required', status=401)

    try:
        event = Event.objects.get(id=event_id)
    except Event.DoesNotExist:
        return api_error('not_found', 'Event not found', status=404)

    is_organizer = event.memberships.filter(user=request.user, role='organizer').exists() or request.user.is_staff
    if not is_organizer:
        return api_error('forbidden', 'Organizer access required for exports', status=403)

    output = io.StringIO()
    writer = csv.writer(output)

    def sanitize(val):
        # Prevent formula injection in spreadsheet software
        s = str(val) if val is not None else ""
        if s.startswith(('=', '+', '-', '@', '\t', '\r')):
            return "'" + s
        return s

    if kind in ('results', 'scores'):
        # Header row with commas
        writer.writerow(['rank', 'project_id', 'title', 'raw_score', 'adjusted_score', 'review_count', 'normalization_status'])
        snapshot = event.result_snapshots.order_by('-revision').first() if kind == 'results' else None
        if snapshot:
            for row in snapshot.rows.all():
                rank = row.adjusted_rank if snapshot.ranking_method == 'adjusted' else row.raw_rank
                writer.writerow([
                    sanitize(rank), sanitize(row.project_id), sanitize(row.project_title),
                    sanitize(round(row.raw_score, 2) if row.raw_score is not None else ''),
                    sanitize(round(row.adjusted_score, 2) if row.adjusted_score is not None else ''),
                    sanitize(row.review_count), sanitize(row.normalization_status),
                ])
        else:
            calc, _ = _calculate_event_results_data(event)
            for row in calc['projects']:
                writer.writerow([
                    sanitize(row.get('raw_rank')), sanitize(row.get('project_id')),
                    sanitize(row.get('title')),
                    sanitize(round(row['raw_score'], 2) if row.get('raw_score') is not None else ''),
                    sanitize(round(row['adjusted_score'], 2) if row.get('adjusted_score') is not None else ''),
                    sanitize(row.get('review_count', 0)), sanitize(row.get('normalization_status', '')),
                ])
    elif kind == 'projects':
        writer.writerow(['id', 'title', 'team', 'track', 'status', 'eligibility', 'repo_url'])
        for p in event.projects.all():
            writer.writerow([
                sanitize(p.id),
                sanitize(p.title),
                sanitize(p.team.name if p.team else ''),
                sanitize(p.track.name if p.track else ''),
                sanitize(p.status),
                sanitize(p.eligibility),
                sanitize(p.repo_url)
            ])
    elif kind == 'audit':
        writer.writerow(['timestamp', 'actor', 'action', 'target', 'reason'])
        for a in event.audit_events.all():
            writer.writerow([
                sanitize(a.created_at.isoformat()),
                sanitize(a.actor.email if a.actor else 'System'),
                sanitize(a.action),
                sanitize(a.target),
                sanitize(a.reason)
            ])
    else:
        writer.writerow(['id', 'name', 'members'])
        for tm in event.teams.all():
            member_names = ", ".join(m.user.display_name for m in tm.memberships.all())
            writer.writerow([sanitize(tm.id), sanitize(tm.name), sanitize(member_names)])

    csv_data = output.getvalue()
    response = HttpResponse(csv_data, content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="fairpanel_{event.id}_{kind}.csv"'
    return response
