import json

from django.test import Client, TestCase
from django.core import signing

from accounts.models import User
from events.models import Event, EventMembership, Track
from judging.models import Assignment, JudgeTrackScope, Review
from projects.models import Project
from teams.models import Team, TeamMembership


class WorkspaceIsolationTests(TestCase):
    def setUp(self):
        self.organizer = User.objects.create_user(email='organizer@test.local', password='strongpass123')
        self.judge = User.objects.create_user(email='judge@test.local', password='strongpass123')
        self.participant = User.objects.create_user(email='participant@test.local', password='strongpass123')
        self.other = User.objects.create_user(email='other@test.local', password='strongpass123')
        self.event = Event.objects.create(owner=self.organizer, name='Scoped event')
        self.track = Track.objects.create(event=self.event, name='Tools')
        for user, role in ((self.organizer, 'organizer'), (self.judge, 'judge'),
                           (self.participant, 'participant')):
            EventMembership.objects.create(user=user, event=self.event, role=role)
        scope = JudgeTrackScope.objects.create(event=self.event, judge=self.judge)
        scope.tracks.add(self.track)
        self.team = Team.objects.create(event=self.event, captain=self.participant, name='Team')
        TeamMembership.objects.create(team=self.team, user=self.participant)
        self.project = Project.objects.create(event=self.event, team=self.team, track=self.track,
                                              title='Project', status='submitted')

    def test_demo_headers_and_cookies_cannot_impersonate(self):
        response = self.client.get('/api/v1/auth/me', HTTP_X_DEMO_ROLE='organizer',
                                   HTTP_COOKIE='session=org_anything')
        self.assertEqual(response.status_code, 401)

    def test_json_write_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.participant)
        endpoint = f'/api/v1/events/{self.event.id}/teams'
        response = client.post(endpoint, json.dumps({'name': 'New team'}), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        csrf = client.get('/api/v1/auth/csrf').json()['data']['csrf_token']
        response = client.post(endpoint, json.dumps({'name': 'New team'}),
                               content_type='application/json', HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code, 409)  # already in a team; CSRF passed

    def test_checker_bearer_reaches_business_rule_without_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.project.delete()
        token = signing.TimestampSigner(salt='fairpanel-checker').sign(self.participant.id)
        response = client.post(f'/api/v1/events/{self.event.id}/projects',
                               json.dumps({'title': 'Valid draft'}), content_type='application/json',
                               HTTP_AUTHORIZATION=f'Bearer {token}')
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Project.objects.filter(title='Valid draft').exists())

    def test_invalid_bearer_does_not_bypass_csrf_or_auth(self):
        client = Client(enforce_csrf_checks=True)
        response = client.get('/api/v1/auth/me', HTTP_AUTHORIZATION='Bearer forged')
        self.assertEqual(response.status_code, 401)

    def test_organizer_cannot_rewrite_participant_project(self):
        self.client.force_login(self.organizer)
        response = self.client.patch(f'/api/v1/projects/{self.project.id}',
                                     json.dumps({'title': 'Hijacked', 'version': 1}),
                                     content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.project.refresh_from_db()
        self.assertEqual(self.project.title, 'Project')

    def test_judge_cannot_create_own_assignment(self):
        self.client.force_login(self.judge)
        response = self.client.put(f'/api/v1/projects/{self.project.id}/review',
                                   json.dumps({'criteria_scores': {'quality': 5}, 'version': 0}),
                                   content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Assignment.objects.filter(project=self.project, judge=self.judge).exists())

    def test_manual_assignment_requires_track_scope(self):
        other_track = Track.objects.create(event=self.event, name='Other')
        other_project = Project.objects.create(event=self.event, team=self.team, track=other_track,
                                               title='Other project', status='submitted')
        self.client.force_login(self.organizer)
        response = self.client.post(f'/api/v1/events/{self.event.id}/assignments',
                                    json.dumps({'strategy': 'manual', 'pairs': [
                                        {'judge_id': self.judge.id, 'project_id': other_project.id}]}),
                                    content_type='application/json')
        self.assertEqual(response.status_code, 422)
        self.assertFalse(Assignment.objects.filter(project=other_project).exists())

    def test_role_specific_settings_are_not_interchangeable(self):
        self.client.force_login(self.participant)
        self.assertEqual(self.client.get('/api/v1/settings/judge').status_code, 403)
        self.assertEqual(self.client.get('/api/v1/settings/organizer').status_code, 403)
        self.assertEqual(self.client.get('/api/v1/settings/participant').status_code, 200)

    def test_organizer_sees_only_own_events_in_peer_scores(self):
        other_organizer = User.objects.create_user(email='owner2@test.local', password='strongpass123')
        other_event = Event.objects.create(owner=other_organizer, name='Private event')
        EventMembership.objects.create(user=other_organizer, event=other_event, role='organizer')
        EventMembership.objects.create(user=self.judge, event=other_event, role='judge')
        other_team = Team.objects.create(event=other_event, captain=self.other, name='Private team')
        other_project = Project.objects.create(event=other_event, team=other_team,
                                               title='Private project', status='submitted')
        other_assignment = Assignment.objects.create(event=other_event, project=other_project, judge=self.judge)
        Review.objects.create(assignment=other_assignment, project=other_project,
                              judge=self.judge, criteria_scores={'quality': 4}, status='submitted')
        self.client.force_login(self.organizer)
        response = self.client.get(f'/api/v1/judges/{self.judge.id}/scores')
        self.assertEqual(response.status_code, 403)
