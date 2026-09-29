from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone
from fairpanel_core.utils import gen_user_id, gen_settings_id


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, display_name=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email).lower()
        if not display_name:
            display_name = email.split('@')[0].capitalize()
        user_id = extra_fields.pop('id', None) or gen_user_id()
        username = extra_fields.pop('username', None) or email
        user = self.model(
            id=user_id,
            email=email,
            username=username,
            display_name=display_name,
            **extra_fields
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    id = models.CharField(max_length=64, primary_key=True, default=gen_user_id, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    username = models.CharField(max_length=150, unique=True, db_index=True)
    display_name = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['display_name']

    class Meta:
        db_table = 'fairpanel_users'
        ordering = ['date_joined']

    def __str__(self):
        return f"{self.display_name} ({self.email})"


class WorkspaceSettings(models.Model):
    WORKSPACE_CHOICES = [
        ('organizer', 'Organizer'),
        ('judge', 'Judge'),
        ('participant', 'Participant'),
    ]

    id = models.CharField(max_length=64, primary_key=True, default=gen_settings_id, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='workspace_settings')
    workspace_type = models.CharField(max_length=32, choices=WORKSPACE_CHOICES)
    preferences = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fairpanel_workspace_settings'
        unique_together = ('user', 'workspace_type')

    def __str__(self):
        return f"{self.user.email} - {self.workspace_type} (v{self.version})"
