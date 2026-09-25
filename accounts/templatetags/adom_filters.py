from django import template

register = template.Library()


@register.filter
def split(value, separator=','):
    """Split strings in legacy templates without failing on missing values."""
    if value is None:
        return []
    return str(value).split(separator)
