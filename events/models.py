from django.db import models
from django.conf import settings
from fairpanel_core.utils import (
    gen_event_id, gen_membership_id, gen_track_id, gen_prize_id,
    gen_question_id, gen_rubric_id, gen_criterion_id
)


class Event(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('judging', 'Judging'),
        ('published', 'Results Published'),
        ('archived', 'Archived'),
    ]

    id = models.CharField(max_length=64, primary_key=True, default=gen_event_id, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='owned_events')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    timezone = models.CharField(max_length=64, default="UTC")
    submissions_open = models.DateTimeField(null=True, blank=True)
    submissions_close = models.DateTimeField(null=True, blank=True)
    judging_open = models.DateTimeField(null=True, blank=True)
    judging_close = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='active')
    team_capacity = models.PositiveIntegerField(default=4)
    min_reviews_per_project = models.PositiveIntegerField(default=3)
    results_published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fairpanel_events'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.id})"

    @property
    def is_submission_open(self):
        from django.utils import timezone
        now = timezone.now()
        if self.submissions_open and now < self.submissions_open:
            return False
        if self.submissions_close and now >= self.submissions_close:
            return False
        return True

    @property
    def is_judging_open(self):
        from django.utils import timezone
        now = timezone.now()
        if self.judging_open and now < self.judging_open:
            return False
        if self.judging_close and now >= self.judging_close:
            return False
        return True


class EventMembership(models.Model):
    ROLE_CHOICES = [
        ('organizer', 'Organizer'),
        ('judge', 'Judge'),
        ('participant', 'Participant'),
    ]

    id = models.CharField(max_length=64, primary_key=True, default=gen_membership_id, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='memberships')
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=32, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fairpanel_event_memberships'
        unique_together = ('user', 'event')

    def __str__(self):
        return f"{self.user.email} - {self.event.name} ({self.role})"


class Track(models.Model):
    id = models.CharField(max_length=64, primary_key=True, default=gen_track_id, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='tracks')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        db_table = 'fairpanel_tracks'
        ordering = ['id']

    def __str__(self):
        return f"{self.name} ({self.id})"


class Prize(models.Model):
    id = models.CharField(max_length=64, primary_key=True, default=gen_prize_id, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='prizes')
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    amount = models.CharField(max_length=100, blank=True)

    class Meta:
        db_table = 'fairpanel_prizes'
        ordering = ['id']

    def __str__(self):
        return f"{self.name} ({self.id})"


class CustomQuestion(models.Model):
    TYPE_CHOICES = [
        ('text', 'Short Text'),
        ('textarea', 'Long Text'),
        ('select', 'Single Select'),
        ('checkbox', 'Checkbox'),
    ]

    id = models.CharField(max_length=64, primary_key=True, default=gen_question_id, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='custom_questions')
    key = models.CharField(max_length=64)
    label = models.CharField(max_length=255)
    type = models.CharField(max_length=32, choices=TYPE_CHOICES, default='text')
    required = models.BooleanField(default=False)
    choices = models.JSONField(default=list, blank=True)
    order = models.IntegerField(default=0)

    class Meta:
        db_table = 'fairpanel_custom_questions'
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.label} ({self.key})"


class Rubric(models.Model):
    id = models.CharField(max_length=64, primary_key=True, default=gen_rubric_id, editable=False)
    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name='rubric')
    version = models.PositiveIntegerField(default=1)
    is_locked = models.BooleanField(default=False)

    class Meta:
        db_table = 'fairpanel_rubrics'

    def __str__(self):
        return f"Rubric v{self.version} for {self.event.name}"


class Criterion(models.Model):
    id = models.CharField(max_length=64, primary_key=True, default=gen_criterion_id, editable=False)
    rubric = models.ForeignKey(Rubric, on_delete=models.CASCADE, related_name='criteria')
    key = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    min_score = models.FloatField(default=1.0)
    max_score = models.FloatField(default=5.0)
    weight = models.FloatField(default=1.0)
    order = models.IntegerField(default=0)

    class Meta:
        db_table = 'fairpanel_criteria'
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.name} (w={self.weight})"
