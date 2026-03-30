import re
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter(name='format_description')
def format_description(value):
    if not value:
        return ''
    
    raw = value.strip()
    parts = [s.strip() for s in re.split(r'[\\/]', raw) if s.strip()]
    
    if len(parts) <= 1:
        escaped_html = escape(raw).replace('\n', '<br>')
        return mark_safe(escaped_html)
    
    html = ''.join(f'<p>{escape(part)}</p>' for part in parts)
    return mark_safe(html)