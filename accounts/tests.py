from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, WorkspaceSettings


class AccountsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='alice@example.com',
            password='secretpassword123',
            display_name='Alice'
        )

    def test_user_creation(self):
        self.assertEqual(self.user.email, 'alice@example.com')
        self.assertEqual(self.user.display_name, 'Alice')
        self.assertTrue(self.user.check_password('secretpassword123'))
        self.assertTrue(self.user.id.startswith('usr_'))

    def test_workspace_settings_creation_and_version(self):
        settings = WorkspaceSettings.objects.create(
            user=self.user,
            workspace_type='participant',
            preferences={'theme': 'dark', 'notifications': True},
            version=1
        )
        self.assertEqual(settings.version, 1)
        self.assertEqual(settings.preferences['theme'], 'dark')

        # Test unique constraint (user, workspace_type)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            WorkspaceSettings.objects.create(
                user=self.user,
                workspace_type='participant',
                preferences={'theme': 'light'}
            )

    def test_security_auth_required(self):
        # Unauthenticated access to security settings should redirect to login
        res = self.client.get('/account/security/')
        self.assertEqual(res.status_code, 302)

        # Authenticated access succeeds
        self.client.login(username='alice@example.com', password='secretpassword123')
        res = self.client.get('/account/security/')
        self.assertEqual(res.status_code, 200)
