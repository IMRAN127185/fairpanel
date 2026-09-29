from django.db import models
from django.conf import settings
from fairpanel_core.utils import gen_project_id, gen_media_id


class Project(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
    ]
    ELIGIBILITY_CHOICES = [
        ('eligible', 'Eligible'),
        ('ineligible', 'Ineligible'),
    ]

    id = models.CharField(max_length=64, primary_key=True, default=gen_project_id, editable=False)
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE, related_name='projects')
    team = models.ForeignKey('teams.Team', on_delete=models.CASCADE, related_name='projects')
    track = models.ForeignKey('events.Track', on_delete=models.SET_NULL, null=True, blank=True, related_name='projects')
    title = models.CharField(max_length=255)
    tagline = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    thumbnail_url = models.CharField(max_length=1000, blank=True)
    images = models.JSONField(default=list, blank=True)
    video_url = models.CharField(max_length=1000, blank=True)
    repo_url = models.CharField(max_length=1000, blank=True)
    live_url = models.CharField(max_length=1000, blank=True)
    tech_tags = models.JSONField(default=list, blank=True)
    custom_answers = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default='draft')
    eligibility = models.CharField(max_length=32, choices=ELIGIBILITY_CHOICES, default='eligible')
    eligibility_reason = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = 'fairpanel_projects'
        ordering = ['-submitted_at', '-updated_at', 'id']

    def __str__(self):
        return f"{self.title} ({self.id})"


class ProjectMedia(models.Model):
    id = models.CharField(max_length=64, primary_key=True, default=gen_media_id, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='media_files', null=True, blank=True)
    file = models.FileField(upload_to='projects/')
    filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=64)
    file_size = models.PositiveIntegerField(default=0)
    order = models.IntegerField(default=0)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fairpanel_project_media'
        ordering = ['order', 'id']

    def __str__(self):
        return f"{self.filename} ({self.id})"
