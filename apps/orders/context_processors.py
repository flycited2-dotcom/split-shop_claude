def cart_count(request):
    if request.user.is_authenticated and getattr(request.user, 'is_approved', False):
        try:
            return {'cart_count': request.user.cart.count}
        except Exception:
            return {'cart_count': 0}
    return {'cart_count': 0}
