from django import template

register = template.Library()

@register.filter(name='dict_key')
def dict_key(d, key):
    if not isinstance(d, dict):
        return None
    val = d.get(key)
    if val is None:
        val = d.get(str(key))
    if val is not None:
        return str(val)
    return None

@register.filter(name='sub')
def sub(value, arg):
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return ''
