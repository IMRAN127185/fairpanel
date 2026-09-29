import uuid
from django.http import JsonResponse
from django.utils import timezone


def generate_id(prefix: str) -> str:
    """Generate an opaque string ID with a given prefix."""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# Top-level named functions for Django model field defaults (serializable by migrations)
def gen_user_id(): return generate_id('usr')
def gen_settings_id(): return generate_id('ws')
def gen_event_id(): return generate_id('evt')
def gen_membership_id(): return generate_id('mem')
def gen_track_id(): return generate_id('trk')
def gen_prize_id(): return generate_id('prz')
def gen_question_id(): return generate_id('qst')
def gen_rubric_id(): return generate_id('rub')
def gen_criterion_id(): return generate_id('crt')
def gen_team_id(): return generate_id('tm')
def gen_team_membership_id(): return generate_id('tmem')
def gen_team_invite_id(): return generate_id('tinv')
def gen_project_id(): return generate_id('prj')
def gen_media_id(): return generate_id('med')
def gen_scope_id(): return generate_id('jts')
def gen_judge_invite_id(): return generate_id('jinv')
def gen_assignment_id(): return generate_id('asg')
def gen_review_id(): return generate_id('rev')
def gen_snapshot_id(): return generate_id('snap')
def gen_result_row_id(): return generate_id('row')
def gen_audit_id(): return generate_id('aud')


def api_success(data, meta=None, status=200):
    """Return standard API success response: {"data": ..., "meta": ...}"""
    payload = {"data": data}
    if meta is not None:
        payload["meta"] = meta
    return JsonResponse(payload, status=status)


def api_error(code: str, message: str, fields=None, status=400):
    """Return standard API error response: {"error": {"code": ..., "message": ..., "fields": {}}}"""
    payload = {
        "error": {
            "code": code,
            "message": message,
            "fields": fields or {}
        }
    }
    return JsonResponse(payload, status=status)
