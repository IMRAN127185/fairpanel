from django.test import TestCase, Client
from django.utils import timezone
from datetime import timedelta
import json

from accounts.models import User
from events.models import Event, EventMembership
from teams.models import Team, TeamMembership
from projects.models import Project


class ProjectTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.organizer = User.objects.create_user(
            email='org@example.com',
            password='password123',
            display_name='Organizer'
        )
        self.participant = User.objects.create_user(
            email='part@example.com',
            password='password123',
            display_name='Participant'
        )

        now = timezone.now()
        # Open event
        self.open_event = Event.objects.create(
            owner=self.organizer,
            name='Open Hackathon',
            submissions_open=now - timedelta(days=1),
            submissions_close=now + timedelta(days=2),
            status='active'
        )
        # Closed event
        self.closed_event = Event.objects.create(
            owner=self.organizer,
            name='Closed Hackathon',
            submissions_open=now - timedelta(days=5),
            submissions_close=now - timedelta(days=1),
            status='judging'
        )

        # Memberships and teams
        self.team_open = Team.objects.create(
            event=self.open_event,
            captain=self.participant,
            name='Alpha Team'
        )
        TeamMembership.objects.create(team=self.team_open, user=self.participant)

        self.team_closed = Team.objects.create(
            event=self.closed_event,
            captain=self.participant,
            name='Beta Team'
        )
        TeamMembership.objects.create(team=self.team_closed, user=self.participant)

    def test_closed_event_refuses_submissions(self):
        self.client.login(username='part@example.com', password='password123')
        payload = json.dumps({'title': 'Late Submission', 'description': 'Too late'})
        res = self.client.post(
            f'/api/v1/events/{self.closed_event.id}/projects',
            data=payload,
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertFalse(data.get('ok'))
        self.assertEqual(data.get('error', {}).get('code'), 'deadline_passed')

    def test_open_event_allows_submission(self):
        self.client.login(username='part@example.com', password='password123')
        payload = json.dumps({'title': 'On Time Submission', 'description': 'Great hack'})
        res = self.client.post(
            f'/api/v1/events/{self.open_event.id}/projects',
            data=payload,
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertIn('data', data)
        self.assertTrue(Project.objects.filter(title='On Time Submission').exists())

    def test_optimistic_concurrency_version_conflict(self):
        self.client.login(username='part@example.com', password='password123')
        project = Project.objects.create(
            event=self.open_event,
            team=self.team_open,
            title='Concurrency Test',
            version=2
        )
        # Attempt PATCH with stale version=1
        stale_payload = json.dumps({'title': 'Conflicting Edit', 'version': 1})
        res = self.client.patch(
            f'/api/v1/projects/{project.id}',
            data=stale_payload,
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 409)
        data = res.json()
        self.assertEqual(data.get('error', {}).get('code'), 'version_conflict')

        # Attempt PATCH with correct version=2 succeeds
        correct_payload = json.dumps({'title': 'Valid Edit', 'version': 2})
        res = self.client.patch(
            f'/api/v1/projects/{project.id}',
            data=correct_payload,
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        project.refresh_from_db()
        self.assertEqual(project.title, 'Valid Edit')
        self.assertEqual(project.version, 3)
