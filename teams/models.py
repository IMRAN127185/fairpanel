from django.db import models
from django.conf import settings
from fairpanel_core.utils import gen_team_id, gen_team_membership_id, gen_team_invite_id


class Team(models.Model):
    id = models.CharField(max_length=64, primary_key=True, default=gen_team_id, editable=False)
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE, related_name='teams')
    captain = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='captained_teams')
    name = models.CharField(max_length=255)
    capacity = models.PositiveIntegerField(default=4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fairpanel_teams'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.id})"

    @property
    def member_count(self):
        return self.memberships.count()

    @property
    def is_full(self):
        return self.member_count >= self.capacity


class TeamMembership(models.Model):
    id = models.CharField(max_length=64, primary_key=True, default=gen_team_membership_id, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='team_memberships')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fairpanel_team_memberships'
        unique_together = ('team', 'user')

    def __str__(self):
        return f"{self.user.email} in {self.team.name}"


class TeamInvite(models.Model):
    id = models.CharField(max_length=64, primary_key=True, default=gen_team_invite_id, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='invites')
    token_hash = models.CharField(max_length=128, unique=True)
    raw_token = models.CharField(max_length=128, blank=True)
    invited_email = models.EmailField(blank=True, null=True)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    expiry = models.DateTimeField(null=True, blank=True)
    usage_limit = models.PositiveIntegerField(default=1)
    times_used = models.PositiveIntegerField(default=0)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fairpanel_team_invites'

    def __str__(self):
        return f"Invite to {self.team.name} ({self.id})"

    @property
    def is_valid(self):
        from django.utils import timezone
        if self.revoked_at is not None:
            return False
        if self.times_used >= self.usage_limit:
            return False
        if self.expiry and timezone.now() > self.expiry:
            return False
        if self.team.is_full:
            return False
        return True
