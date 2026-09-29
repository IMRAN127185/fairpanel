from django.db import models
from django.conf import settings
from fairpanel_core.utils import gen_audit_id


class AuditEvent(models.Model):
    id = models.CharField(max_length=64, primary_key=True, default=gen_audit_id, editable=False)
    event = models.ForeignKey('events.Event', on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_actions')
    action = models.CharField(max_length=64)
    target = models.CharField(max_length=128, blank=True)
    reason = models.TextField(blank=True)
    before_data = models.JSONField(default=dict, blank=True)
    after_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'fairpanel_audit_events'
        ordering = ['-created_at']

    def __str__(self):
        actor_name = self.actor.email if self.actor else "System"
        return f"[{self.created_at.isoformat()}] {actor_name} -> {self.action} ({self.target})"
