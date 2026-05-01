from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from .models import Cart, CartItem, Order, OrderItem
from .forms import CheckoutForm
from apps.catalog.models import Product


@login_required
def cart_view(request):
    if not request.user.is_approved:
        return redirect('pending')
    cart, _ = Cart.objects.get_or_create(user=request.user)
    return render(request, 'orders/cart.html', {'cart': cart})


@require_POST
@login_required
def cart_add(request):
    if not request.user.is_approved:
        return HttpResponse('Доступ закрыт', status=403)
    product_id = request.POST.get('product_id')
    quantity = int(request.POST.get('quantity', 1))
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    cart, _ = Cart.objects.get_or_create(user=request.user)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if not created:
        item.quantity += quantity
    else:
        item.quantity = quantity
    item.save()
    if request.htmx:
        return HttpResponse(
            '<span class="text-green-600 font-semibold">✓ Добавлено в корзину</span>'
        )
    return redirect('cart')


@require_POST
@login_required
def cart_remove(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
    item.delete()
    cart = request.user.cart
    if request.htmx:
        return render(request, 'orders/partials/cart_table.html', {'cart': cart})
    return redirect('cart')


@require_POST
@login_required
def cart_update(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
    quantity = int(request.POST.get('quantity', 1))
    if quantity > 0:
        item.quantity = quantity
        item.save()
    else:
        item.delete()
    cart = request.user.cart
    if request.htmx:
        return render(request, 'orders/partials/cart_table.html', {'cart': cart})
    return redirect('cart')


@login_required
def checkout(request):
    if not request.user.is_approved:
        return redirect('pending')
    cart = get_object_or_404(Cart, user=request.user)
    if not cart.items.exists():
        return redirect('cart')
    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            order = Order.objects.create(
                user=request.user,
                delivery_address=form.cleaned_data['delivery_address'],
                comment=form.cleaned_data.get('comment', ''),
                total=cart.total,
                status='new',
            )
            for item in cart.items.select_related('product'):
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price_at_order=request.user.get_wholesale_price(
                        item.product.price_wholesale) or 0,
                    ric_at_order=item.product.ric,
                )
            cart.items.all().delete()
            if settings.MANAGER_EMAIL:
                send_mail(
                    subject=f'Новый заказ #{order.pk} — {request.user.company_name}',
                    message=f'Заказ #{order.pk} на сумму {order.total} ₽',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.MANAGER_EMAIL],
                    fail_silently=True,
                )
            messages.success(request, f'Заказ #{order.pk} успешно оформлен!')
            return redirect('order_detail', pk=order.pk)
    else:
        form = CheckoutForm(initial={'delivery_address': request.user.legal_address})
    return render(request, 'orders/checkout.html', {'cart': cart, 'form': form})
