from django import template
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter(name='sort_by')
def sort_by(queryset, order_by):
    """
    Sort a queryset by the specified order_by field.
    """
    if not queryset:
        return []

    # Assuming the order_by field is a string field
    return sorted(queryset, key=lambda obj: getattr(obj, order_by, ''))

@register.filter(name='sort_by_int')
def sort_by_int(queryset, order_by):
    """
    Sort a queryset by the specified order_by field (integer field).
    """
    if not queryset:
        return []

    # Assuming the order_by field is an integer field
    return sorted(queryset, key=lambda obj: getattr(obj, order_by, 0))