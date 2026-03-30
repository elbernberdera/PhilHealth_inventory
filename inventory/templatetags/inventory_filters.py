from django import template
from datetime import date

register = template.Library()


@register.simple_tag(takes_context=True)
def page_query(context, page_key, page_num):
    """
    Merge GET params and set one page key (e.g. page_all=2) for pagination links.
    Preserves search (q) and other query keys.
    """
    request = context["request"]
    q = request.GET.copy()
    q[str(page_key)] = str(page_num)
    return q.urlencode()

@register.filter(name='days_until_expiration')
def days_until_expiration(expiration_date):
    """
    Calculate the number of days until expiration.
    Returns a tuple (days, is_expired) where:
    - days: number of days (positive if future, negative if past)
    - is_expired: boolean indicating if already expired
    """
    if not expiration_date:
        return None
    
    today = date.today()
    delta = expiration_date - today
    days = delta.days
    
    return days

@register.filter(name='expiration_badge_class')
def expiration_badge_class(days):
    """
    Return the appropriate badge class based on days until expiration.
    """
    if days is None:
        return 'badge-secondary'
    elif days < 0:
        return 'badge-danger'
    elif days <= 7:
        return 'badge-danger'
    elif days <= 30:
        return 'badge-warning'
    else:
        return 'badge-info'

@register.filter(name='expiration_text')
def expiration_text(days):
    """
    Return human-readable text for expiration status.
    """
    if days is None:
        return 'N/A'
    elif days < 0:
        return f'Expired ({abs(days)} days ago)'
    elif days == 0:
        return 'Expires today'
    elif days == 1:
        return '1 day remaining'
    else:
        return f'{days} days remaining'
