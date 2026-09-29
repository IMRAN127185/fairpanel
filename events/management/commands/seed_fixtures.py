import os
import json
from datetime import datetime, timezone as dt_timezone
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.auth import get_user_model
from events.models import Event, EventMembership, Track, Prize, CustomQuestion, Rubric, Criterion
from teams.models import Team, TeamMembership
from projects.models import Project
from judging.models import JudgeTrackScope, Assignment, Review
from accounts.models import WorkspaceSettings


class Command(BaseCommand):
    help = 'Seed official fixture data idempotently and generate .dogfood.toml'

    def add_arguments(self, parser):
        parser.add_argument('--fixtures', default='fixtures.json', help='Path to fixtures.json')
        parser.add_argument('--reset', action='store_true', help='Reset database before seeding')

    def handle(self, *args, **options):
        fixture_path = options['fixtures']
        if not os.path.isabs(fixture_path):
            fixture_path = os.path.join(os.getcwd(), fixture_path)

        if not os.path.exists(fixture_path):
            fixture_path = os.path.join(os.getcwd(), 'spec', 'fixtures.json')

        self.stdout.write(f"Loading fixtures from {fixture_path}...")
        with open(fixture_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        User = get_user_model()

        with transaction.atomic():
            # 1. Create Core Demo Users
            organizer_user, _ = User.objects.get_or_create(
                email='organizer@fairpanel.local',
                defaults={
                    'id': 'usr_organizer',
                    'username': 'organizer@fairpanel.local',
                    'display_name': 'Alex Rivera (Organizer)',
                    'is_staff': True,
                }
            )
            organizer_user.set_password('DemoPassword2026!')
            organizer_user.save()

            participant_user, _ = User.objects.get_or_create(
                email='participant@fairpanel.local',
                defaults={
                    'id': 'usr_participant',
                    'username': 'participant@fairpanel.local',
                    'display_name': 'Sam Patel (Participant)',
                }
            )
            participant_user.set_password('DemoPassword2026!')
            participant_user.save()

            # Ensure WorkspaceSettings for core users
            WorkspaceSettings.objects.get_or_create(
                user=organizer_user,
                workspace_type='organizer',
                defaults={'preferences': {'display_name': 'Alex Rivera', 'timezone': 'UTC'}}
            )
            WorkspaceSettings.objects.get_or_create(
                user=participant_user,
                workspace_type='participant',
                defaults={'preferences': {'display_name': 'Sam Patel', 'skills': ['Python', 'Django', 'Full Stack'], 'timezone': 'UTC'}}
            )

            # 2. Seed Official Event
            evt_data = data['event']
            event_close = datetime.fromisoformat(evt_data['submissions_close'].replace('Z', '+00:00'))
            event, _ = Event.objects.update_or_create(
                id=evt_data['id'],
                defaults={
                    'name': evt_data['name'],
                    'owner': organizer_user,
                    'submissions_close': event_close,
                    'timezone': 'UTC',
                    'status': 'active',
                    'team_capacity': 4,
                    'min_reviews_per_project': 3,
                    'description': 'Official DOGFOOD 2026 fixture event. Submissions are closed.',
                }
            )

            # Organizer membership
            EventMembership.objects.get_or_create(
                user=organizer_user,
                event=event,
                defaults={'role': 'organizer'}
            )

            # 3. Seed Tracks
            track_objs = {}
            for t in data.get('tracks', []):
                trk, _ = Track.objects.update_or_create(
                    id=t['id'],
                    defaults={
                        'event': event,
                        'name': t['name'],
                        'description': f"Track for {t['name']}",
                    }
                )
                track_objs[t['id']] = trk

            # 4. Seed Judges
            judge_objs = {}
            for idx, j in enumerate(data.get('judges', [])):
                j_id = j['id']
                email = j.get('email', f"{j_id}@example.org")
                name = j.get('name', f"Judge {j_id}")

                u, _ = User.objects.get_or_create(
                    id=j_id,
                    defaults={
                        'email': email,
                        'username': email,
                        'display_name': name,
                    }
                )
                u.display_name = name
                u.email = email
                u.set_password('DemoPassword2026!')
                u.save()

                EventMembership.objects.get_or_create(
                    user=u,
                    event=event,
                    defaults={'role': 'judge'}
                )

                WorkspaceSettings.objects.get_or_create(
                    user=u,
                    workspace_type='judge',
                    defaults={'preferences': {'display_name': name, 'expertise_tags': j.get('tracks', []), 'timezone': 'UTC'}}
                )

                # Track scopes
                scope, _ = JudgeTrackScope.objects.get_or_create(
                    judge=u,
                    event=event
                )
                j_tracks = [track_objs[tid] for tid in j.get('tracks', []) if tid in track_objs]
                scope.tracks.set(j_tracks)

                judge_objs[j_id] = u

            # Map judge_a and judge_b for checker
            judge_a_user = judge_objs.get('jdg_01')
            judge_b_user = judge_objs.get('jdg_02')

            # 5. Seed Rubric and Criteria from scores
            rubric, _ = Rubric.objects.get_or_create(
                event=event,
                defaults={'version': 1, 'is_locked': True}
            )
            criteria_names = [
                ('functionality', 'Functionality', 1.0, 5.0, 1.0),
                ('innovation', 'Innovation', 1.0, 5.0, 1.0),
                ('quality', 'Quality', 1.0, 5.0, 1.0),
            ]
            for order, (key, name, min_s, max_s, weight) in enumerate(criteria_names):
                Criterion.objects.update_or_create(
                    rubric=rubric,
                    key=key,
                    defaults={
                        'id': f"crt_{key}",
                        'name': name,
                        'min_score': min_s,
                        'max_score': max_s,
                        'weight': weight,
                        'order': order,
                    }
                )

            # 6. Seed Teams & Memberships
            team_objs = {}
            for t in data.get('teams', []):
                t_id = t['id']
                member_emails = t.get('members', [])
                captain_user = None

                # Find or create members
                for idx, m_email in enumerate(member_emails):
                    m_user, _ = User.objects.get_or_create(
                        email=m_email,
                        defaults={
                            'username': m_email,
                            'display_name': m_email.split('@')[0].capitalize(),
                        }
                    )
                    m_user.set_password('DemoPassword2026!')
                    m_user.save()

                    EventMembership.objects.get_or_create(
                        user=m_user,
                        event=event,
                        defaults={'role': 'participant'}
                    )

                    if idx == 0:
                        captain_user = m_user

                if not captain_user:
                    captain_user = participant_user

                tm, _ = Team.objects.update_or_create(
                    id=t_id,
                    defaults={
                        'event': event,
                        'name': t['name'],
                        'captain': captain_user,
                        'capacity': max(4, len(member_emails)),
                    }
                )
                team_objs[t_id] = tm

                for m_email in member_emails:
                    m_user = User.objects.get(email=m_email)
                    TeamMembership.objects.get_or_create(
                        team=tm,
                        user=m_user
                    )

            # Assign participant_user to tm_01
            tm_01 = team_objs.get('tm_01')
            if tm_01:
                TeamMembership.objects.get_or_create(team=tm_01, user=participant_user)
                EventMembership.objects.get_or_create(user=participant_user, event=event, defaults={'role': 'participant'})

            # 7. Seed Projects
            project_objs = {}
            for p in data.get('projects', []):
                p_id = p['id']
                tm = team_objs.get(p.get('team'))
                trk = track_objs.get(p.get('track'))
                sub_at = datetime.fromisoformat(p['submitted_at'].replace('Z', '+00:00')) if 'submitted_at' in p else timezone.now()

                prj, _ = Project.objects.update_or_create(
                    id=p_id,
                    defaults={
                        'event': event,
                        'team': tm,
                        'track': trk,
                        'title': p['title'],
                        'tagline': p.get('summary', ''),
                        'description': p.get('summary', ''),
                        'repo_url': p.get('repo_url', ''),
                        'submitted_at': sub_at,
                        'status': 'submitted',
                        'eligibility': 'eligible',
                        'version': 1,
                    }
                )
                project_objs[p_id] = prj

            # 8. Seed Scores (Assignments and Reviews)
            for idx, s in enumerate(data.get('scores', [])):
                j_id = s.get('judge')
                p_id = s.get('project')
                judge = judge_objs.get(j_id)
                project = project_objs.get(p_id)

                if not judge or not project:
                    continue

                asg, _ = Assignment.objects.get_or_create(
                    event=event,
                    project=project,
                    judge=judge,
                    defaults={'status': 'completed'}
                )
                asg.status = 'completed'
                asg.save()

                Review.objects.update_or_create(
                    project=project,
                    judge=judge,
                    defaults={
                        'id': f"rev_{idx+1:04d}",
                        'assignment': asg,
                        'rubric_version': 1,
                        'criteria_scores': s.get('criteria', {}),
                        'comment': s.get('comment', ''),
                        'status': 'submitted',
                        'version': 1,
                        'submitted_at': timezone.now(),
                    }
                )

            # 9. Create Active Open Demo Event for Live Interactive Testing
            demo_event, _ = Event.objects.get_or_create(
                id='evt_demo',
                defaults={
                    'name': 'Open TechFest 2026',
                    'owner': organizer_user,
                    'submissions_open': timezone.now() - timezone.timedelta(days=1),
                    'submissions_close': timezone.now() + timezone.timedelta(days=365),
                    'judging_open': timezone.now() - timezone.timedelta(days=1),
                    'judging_close': timezone.now() + timezone.timedelta(days=366),
                    'timezone': 'UTC',
                    'status': 'active',
                    'team_capacity': 5,
                    'min_reviews_per_project': 3,
                    'description': 'Live open hackathon for testing project submissions, team formation, and real-time judging.',
                }
            )
            # Memberships for demo event
            EventMembership.objects.get_or_create(user=organizer_user, event=demo_event, defaults={'role': 'organizer'})
            EventMembership.objects.get_or_create(user=judge_a_user, event=demo_event, defaults={'role': 'judge'})
            EventMembership.objects.get_or_create(user=participant_user, event=demo_event, defaults={'role': 'participant'})

            # Tracks for demo event
            d_trk1, _ = Track.objects.get_or_create(id='trk_demo_ai', event=demo_event, defaults={'name': 'Artificial Intelligence & Agents', 'description': 'Autonomous agents, ML tools, and intelligence platforms'})
            d_trk2, _ = Track.objects.get_or_create(id='trk_demo_dev', event=demo_event, defaults={'name': 'Developer Tools & Infra', 'description': 'Productivity, dev environments, self-hosted infrastructure'})
            d_trk3, _ = Track.objects.get_or_create(id='trk_demo_open', event=demo_event, defaults={'name': 'Open Track', 'description': 'General software innovations'})

            # Prizes for demo event
            Prize.objects.get_or_create(id='prz_demo_1', event=demo_event, defaults={'name': 'Grand Prize', 'amount': '$10,000', 'description': 'Best overall hackathon submission'})
            Prize.objects.get_or_create(id='prz_demo_2', event=demo_event, defaults={'name': 'Best Developer Tool', 'amount': '$3,000', 'description': 'Most useful developer tool'})

            # Custom questions for demo event
            CustomQuestion.objects.get_or_create(id='qst_demo_1', event=demo_event, defaults={'key': 'built_with_ai', 'label': 'Did you use AI coding assistants to build this project?', 'type': 'select', 'choices': ['Yes, extensively', 'Yes, partially', 'No'], 'order': 1})
            CustomQuestion.objects.get_or_create(id='qst_demo_2', event=demo_event, defaults={'key': 'challenges_faced', 'label': 'What was the hardest challenge your team overcame?', 'type': 'textarea', 'order': 2})

            # Rubric for demo event
            demo_rubric, _ = Rubric.objects.get_or_create(event=demo_event, defaults={'version': 1, 'is_locked': False})
            for order, (key, name, min_s, max_s, weight) in enumerate(criteria_names):
                Criterion.objects.get_or_create(
                    rubric=demo_rubric,
                    key=key,
                    defaults={'id': f"crt_demo_{key}", 'name': name, 'min_score': min_s, 'max_score': max_s, 'weight': weight, 'order': order}
                )

        # 10. Generate Real Sessions for Checker & Demo Logins
        def create_session(user):
            s = SessionStore()
            s['_auth_user_id'] = user.id
            s['_auth_user_backend'] = 'django.contrib.auth.backends.ModelBackend'
            s['_auth_user_hash'] = user.get_session_auth_hash()
            s.save()
            return s.session_key

        org_sess = create_session(organizer_user)
        jdg_a_sess = create_session(judge_a_user)
        jdg_b_sess = create_session(judge_b_user)
        prt_sess = create_session(participant_user)

        self.stdout.write(self.style.SUCCESS('Seeded successfully!'))
        self.stdout.write("Test logins:")
        self.stdout.write(f"  organizer    Cookie: sessionid={org_sess} (email: organizer@fairpanel.local / DemoPassword2026!)")
        self.stdout.write(f"  judge_a      Cookie: sessionid={jdg_a_sess} (email: tomas.varga@example.org / DemoPassword2026!)")
        self.stdout.write(f"  judge_b      Cookie: sessionid={jdg_b_sess} (email: sara.lindqvist@example.org / DemoPassword2026!)")
        self.stdout.write(f"  participant  Cookie: sessionid={prt_sess} (email: participant@fairpanel.local / DemoPassword2026!)")

        # 11. Write .dogfood.toml
        dogfood_content = f"""[portal]
base_url = "http://localhost:8080"

[tiers]
claimed = ["T1", "T2"]
pitch = "Self-hosted hackathon submission and transparent judging portal with conservative normalization."

[auth]
organizer   = "Cookie: sessionid={org_sess}"
judge_a     = "Cookie: sessionid={jdg_a_sess}"
judge_b     = "Cookie: sessionid={jdg_b_sess}"
participant = "Cookie: sessionid={prt_sess}"

[routes]
gallery      = "/projects"
submit       = "/api/v1/events/evt_01/projects"
judge_scores = "/api/v1/judge/scores"
peer_scores  = "/api/v1/judges/jdg_01/scores"
csv_export   = "/api/v1/events/evt_01/exports/results.csv"
"""
        with open('.dogfood.toml', 'w', encoding='utf-8') as f:
            f.write(dogfood_content)
        self.stdout.write(self.style.SUCCESS("Generated .dogfood.toml successfully!"))
