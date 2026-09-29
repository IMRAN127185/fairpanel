from django.db import models
from django.conf import settings
from fairpanel_core.utils import (
    gen_scope_id, gen_judge_invite_id, gen_assignment_id,
    gen_review_id, gen_snapshot_id, gen_result_row_id
)


class JudgeTrackScope(models.Model):
    id = models.CharField(max_length=64, primary_key=True, default=gen_scope_id, editable=False)
    judge = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='judge_scopes')
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE, related_name='judge_track_scopes')
    tracks = models.ManyToManyField('events.Track', blank=True, related_name='scoped_judges')

    class Meta:
        db_table = 'fairpanel_judge_track_scopes'
        unique_together = ('judge', 'event')

    def __str__(self):
        return f"{self.judge.email} scopes for {self.event.name}"


class JudgeInvite(models.Model):
    id = models.CharField(max_length=64, primary_key=True, default=gen_judge_invite_id, editable=False)
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE, related_name='judge_invites')
    token_hash = models.CharField(max_length=128, unique=True)
    raw_token = models.CharField(max_length=128, blank=True)
    invited_email = models.EmailField(blank=True, null=True)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    tracks = models.JSONField(default=list, blank=True)
    expiry = models.DateTimeField(null=True, blank=True)
    usage_limit = models.PositiveIntegerField(default=1)
    times_used = models.PositiveIntegerField(default=0)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fairpanel_judge_invites'

    def __str__(self):
        return f"Judge invite for {self.event.name} ({self.id})"

    @property
    def is_valid(self):
        from django.utils import timezone
        if self.revoked_at is not None:
            return False
        if self.times_used >= self.usage_limit:
            return False
        if self.expiry and timezone.now() > self.expiry:
            return False
        return True


class Assignment(models.Model):
    STATUS_CHOICES = [
        ('assigned', 'Assigned'),
        ('conflict', 'Conflict Reported'),
        ('completed', 'Completed'),
    ]

    id = models.CharField(max_length=64, primary_key=True, default=gen_assignment_id, editable=False)
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE, related_name='assignments')
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='assignments')
    judge = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assignments')
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='assigned')
    conflict_reason = models.TextField(blank=True)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fairpanel_assignments'
        unique_together = ('project', 'judge')

    def __str__(self):
        return f"{self.judge.email} -> {self.project.title} ({self.status})"


class Review(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
    ]

    id = models.CharField(max_length=64, primary_key=True, default=gen_review_id, editable=False)
    assignment = models.OneToOneField(Assignment, on_delete=models.CASCADE, related_name='review', null=True, blank=True)
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='reviews')
    judge = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    rubric_version = models.PositiveIntegerField(default=1)
    criteria_scores = models.JSONField(default=dict)
    comment = models.TextField(blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='draft')
    version = models.PositiveIntegerField(default=1)
    submitted_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fairpanel_reviews'
        unique_together = ('project', 'judge')

    def __str__(self):
        return f"Review by {self.judge.email} on {self.project.title} ({self.status})"


class ResultSnapshot(models.Model):
    METHOD_CHOICES = [
        ('raw', 'Raw Score'),
        ('adjusted', 'Adjusted Score (overlap_bias_v1)'),
    ]

    id = models.CharField(max_length=64, primary_key=True, default=gen_snapshot_id, editable=False)
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE, related_name='result_snapshots')
    revision = models.PositiveIntegerField(default=1)
    ranking_method = models.CharField(max_length=32, choices=METHOD_CHOICES, default='raw')
    input_fingerprint = models.CharField(max_length=128)
    warnings_acknowledged = models.JSONField(default=list)
    reason = models.TextField(blank=True)
    published_at = models.DateTimeField(auto_now_add=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = 'fairpanel_result_snapshots'
        ordering = ['-revision']

    def __str__(self):
        return f"{self.event.name} Results Rev {self.revision} ({self.ranking_method})"


class ResultRow(models.Model):
    id = models.CharField(max_length=64, primary_key=True, default=gen_result_row_id, editable=False)
    snapshot = models.ForeignKey(ResultSnapshot, on_delete=models.CASCADE, related_name='rows')
    project = models.ForeignKey('projects.Project', on_delete=models.CASCADE, related_name='result_rows')
    project_title = models.CharField(max_length=255, blank=True)
    project_tagline = models.CharField(max_length=500, blank=True)
    track_name = models.CharField(max_length=255, blank=True)
    raw_score = models.FloatField(null=True, blank=True)
    adjusted_score = models.FloatField(null=True, blank=True)
    raw_rank = models.IntegerField(null=True, blank=True)
    adjusted_rank = models.IntegerField(null=True, blank=True)
    review_count = models.IntegerField(default=0)
    eligible_review_count = models.IntegerField(default=0)
    normalization_status = models.CharField(max_length=64, default="calibrated")
    warnings = models.JSONField(default=list)
    tied = models.BooleanField(default=False)

    class Meta:
        db_table = 'fairpanel_result_rows'
        ordering = ['raw_rank']

    def __str__(self):
        return f"Rank #{self.raw_rank}: {self.project_title or self.project.title}"
