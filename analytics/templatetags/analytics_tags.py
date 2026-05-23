from django import template
from ..settings import get_config

register = template.Library()

@register.simple_tag
def get_analytics_config():
    return get_config()