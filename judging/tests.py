from django.test import TestCase, Client
from django.utils import timezone
import json

from accounts.models import User
from events.models import Event, EventMembership, Rubric, Criterion
from teams.models import Team
from projects.models import Project
from judging.models import Assignment, Review
from judging.scoring import compute_weighted_score, compute_pool_results


class JudgingAuthorizationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.organizer = User.objects.create_user(
            email='org@example.com',
            password='password123',
            display_name='Organizer'
        )
        self.judge_a = User.objects.create_user(
            email='judge_a@example.com',
            password='password123',
            display_name='Judge A'
        )
        self.judge_b = User.objects.create_user(
            email='judge_b@example.com',
            password='password123',
            display_name='Judge B'
        )
        self.participant = User.objects.create_user(
            email='participant@example.com',
            password='password123',
            display_name='Participant'
        )

        self.event = Event.objects.create(
            owner=self.organizer,
            name='Test Hackathon',
            status='judging'
        )
        EventMembership.objects.create(user=self.organizer, event=self.event, role='organizer')
        EventMembership.objects.create(user=self.judge_a, event=self.event, role='judge')
        EventMembership.objects.create(user=self.judge_b, event=self.event, role='judge')
        EventMembership.objects.create(user=self.participant, event=self.event, role='participant')

        self.team = Team.objects.create(event=self.event, captain=self.participant, name='Team One')
        self.project = Project.objects.create(
            event=self.event,
            team=self.team,
            title='Project One',
            status='submitted',
            eligibility='eligible'
        )

        self.asg_a = Assignment.objects.create(event=self.event, project=self.project, judge=self.judge_a)
        self.rev_a = Review.objects.create(
            assignment=self.asg_a,
            project=self.project,
            judge=self.judge_a,
            criteria_scores={'quality': 4.0},
            status='submitted'
        )

    def test_participant_blocked_from_judge_scores(self):
        self.client.login(username='participant@example.com', password='password123')
        res = self.client.get('/api/v1/judge/scores')
        self.assertEqual(res.status_code, 403)

    def test_judge_sees_own_scores(self):
        self.client.login(username='judge_a@example.com', password='password123')
        res = self.client.get('/api/v1/judge/scores')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn('data', data)
        self.assertEqual(len(data.get('data', [])), 1)

    def test_judge_cannot_see_peer_scores(self):
        # Judge A attempts to query Judge B's scores directly
        self.client.login(username='judge_a@example.com', password='password123')
        res = self.client.get(f'/api/v1/judges/{self.judge_b.id}/scores')
        self.assertEqual(res.status_code, 403)

    def test_csv_export_permissions(self):
        # Participant cannot export CSV
        self.client.login(username='participant@example.com', password='password123')
        res = self.client.get(f'/api/v1/events/{self.event.id}/exports/results.csv')
        self.assertEqual(res.status_code, 403)

        # Organizer can export CSV
        self.client.login(username='org@example.com', password='password123')
        res = self.client.get(f'/api/v1/events/{self.event.id}/exports/results.csv')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res['Content-Type'], 'text/csv; charset=utf-8')


class ScoringEngineTests(TestCase):
    def setUp(self):
        self.criteria_defs = {
            'c1': {'min_score': 1.0, 'max_score': 5.0, 'weight': 2.0},
            'c2': {'min_score': 0.0, 'max_score': 10.0, 'weight': 1.0},
        }

    def test_compute_weighted_score(self):
        # c1: 5.0 -> 1.0 norm * 2/3 weight
        # c2: 10.0 -> 1.0 norm * 1/3 weight
        # total -> 100.0
        scores_max = {'c1': 5.0, 'c2': 10.0}
        self.assertAlmostEqual(compute_weighted_score(scores_max, self.criteria_defs), 100.0)

        # c1: 1.0 -> 0.0 norm
        # c2: 0.0 -> 0.0 norm
        scores_min = {'c1': 1.0, 'c2': 0.0}
        self.assertAlmostEqual(compute_weighted_score(scores_min, self.criteria_defs), 0.0)

        # c1: 3.0 -> 0.5 norm * (2/3) = 1/3
        # c2: 5.0 -> 0.5 norm * (1/3) = 1/6
        # sum = 0.5 * 100 = 50.0
        scores_mid = {'c1': 3.0, 'c2': 5.0}
        self.assertAlmostEqual(compute_weighted_score(scores_mid, self.criteria_defs), 50.0)

    def test_overlap_bias_constant_scorer(self):
        # 3 projects, 3 judges
        projects = [{'id': 'p1', 'title': 'P1'}, {'id': 'p2', 'title': 'P2'}, {'id': 'p3', 'title': 'P3'}]
        # Judge 1 gives constant 50.0 to all 3 projects
        # Judge 2 gives 60, 70, 80
        # Judge 3 gives 40, 50, 60
        reviews = [
            {'id': 'r1', 'judge_id': 'j1', 'project_id': 'p1', 'criteria_scores': {'c1': 3.0, 'c2': 5.0}},
            {'id': 'r2', 'judge_id': 'j1', 'project_id': 'p2', 'criteria_scores': {'c1': 3.0, 'c2': 5.0}},
            {'id': 'r3', 'judge_id': 'j1', 'project_id': 'p3', 'criteria_scores': {'c1': 3.0, 'c2': 5.0}},

            {'id': 'r4', 'judge_id': 'j2', 'project_id': 'p1', 'criteria_scores': {'c1': 3.4, 'c2': 6.0}},
            {'id': 'r5', 'judge_id': 'j2', 'project_id': 'p2', 'criteria_scores': {'c1': 3.8, 'c2': 7.0}},
            {'id': 'r6', 'judge_id': 'j2', 'project_id': 'p3', 'criteria_scores': {'c1': 4.2, 'c2': 8.0}},

            {'id': 'r7', 'judge_id': 'j3', 'project_id': 'p1', 'criteria_scores': {'c1': 2.6, 'c2': 4.0}},
            {'id': 'r8', 'judge_id': 'j3', 'project_id': 'p2', 'criteria_scores': {'c1': 3.0, 'c2': 5.0}},
            {'id': 'r9', 'judge_id': 'j3', 'project_id': 'p3', 'criteria_scores': {'c1': 3.4, 'c2': 6.0}},
        ]
        results = compute_pool_results(projects, reviews, self.criteria_defs, min_required_reviews=3)

        # j1 should be flagged as constant scorer and uncalibrated
        self.assertFalse(results['judge_calibrated']['j1'])
        self.assertEqual(results['judge_severity']['j1'], 0.0)
        self.assertIn("Constant scorer detected", results['judge_warnings']['j1'])

        # j2 and j3 should be calibrated
        self.assertTrue(results['judge_calibrated']['j2'])
        self.assertTrue(results['judge_calibrated']['j3'])
        self.assertTrue(results['is_graph_connected'])
