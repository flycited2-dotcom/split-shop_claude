import logging

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
from apps.notifications.telegram import send_telegram

logger = logging.getLogger(__name__)


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
            # Формируем состав заказа для уведомлений
            order_items = order.items.select_related('product')
            lines = []
            for item in order_items:
                sku = item.product.articul or item.product.nc_code
                lines.append(f'• {sku} × {item.quantity} = {item.subtotal:,.0f} ₽')
            items_text = '\n'.join(lines)

            # Email менеджеру
            if settings.MANAGER_EMAIL:
                email_body = (
                    f'Заказ #{order.pk}\n'
                    f'Компания: {request.user.company_name}\n'
                    f'Телефон: {request.user.phone}\n'
                    f'Email: {request.user.email}\n'
                    f'Адрес доставки: {order.delivery_address}\n\n'
                    f'Состав заказа:\n{items_text}\n\n'
                    f'Итого: {order.total:,.0f} ₽\n'
                    f'Комментарий: {order.comment or "—"}\n'
                )
                send_mail(
                    subject=f'Новый заказ #{order.pk} — {request.user.company_name}',
                    message=email_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.MANAGER_EMAIL],
                    fail_silently=True,
                )

            # Telegram менеджеру
            try:
                created_str = order.created_at.strftime('%d.%m.%Y %H:%M')
                company = request.user.company_name or request.user.email
                phone = request.user.phone or '—'
                comment_line = f'\n💬 Комментарий: {order.comment}' if order.comment else ''
                tg_text = (
                    f'🛒 Новый заказ #{order.pk}\n'
                    f'📅 {created_str}\n'
                    f'👤 {company}\n'
                    f'📞 {phone}\n'
                    f'📧 {request.user.email}\n\n'
                    f'Состав:\n{items_text}'
                    f'\n\n💰 Итого: {order.total:,.0f} ₽'
                    f'{comment_line}\n\n'
                    f'🔗 /admin/orders/order/{order.pk}/change/'
                )
                send_telegram(tg_text)
            except Exception as exc:
                logger.warning('Telegram order notification failed: %s', exc)
            messages.success(request, f'Заказ #{order.pk} успешно оформлен!')
            return redirect('order_detail', pk=order.pk)
    else:
        form = CheckoutForm(initial={'delivery_address': request.user.legal_address})
    return render(request, 'orders/checkout.html', {'cart': cart, 'form': form})
