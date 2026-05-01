from django.db import models as db_models
from django.core.exceptions import ObjectDoesNotExist


def cart_count(request):
    """Inject cart item count into all templates."""
    if not request.user.is_authenticated:
        return {'cart_count': 0}
    if not getattr(request.user, 'is_approved', False):
        return {'cart_count': 0}
    try:
        count = request.user.cart.items.aggregate(
            total=db_models.Sum('quantity')
        )['total'] or 0
        return {'cart_count': count}
    except ObjectDoesNotExist:
        return {'cart_count': 0}
