from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.http import HttpResponse
from django.conf import settings

from apps.catalog.models import Product
from apps.notifications.telegram import send_telegram
from .forms import QuickOrderForm, SelectionRequestForm, InstallationRequestForm
from .models import QuickOrder, SelectionRequest, InstallationRequest


SUCCESS_HTML = '<p class="text-green-600 font-semibold py-4">✅ Заявка принята! Менеджер свяжется с вами в ближайшее время.</p>'


@require_POST
def quick_order_submit(request):
    form = QuickOrderForm(request.POST)
    if not form.is_valid():
        return render(request, 'leads/partials/quick_order_form.html', {'form': form})

    product = None
    try:
        product_id = int(request.POST.get('product_id', ''))
        product = Product.objects.filter(pk=product_id).first()
    except (ValueError, TypeError):
        pass

    obj = QuickOrder.objects.create(
        name=form.cleaned_data['name'],
        phone=form.cleaned_data['phone'],
        product=product,
        comment=form.cleaned_data.get('comment', ''),
    )

    product_info = ''
    if obj.product:
        sku = obj.product.articul or obj.product.nc_code
        product_info = f'\n📦 {sku} — {obj.product.title}'

    send_telegram(
        f'⚡ <b>Заказ в 1 клик</b>\n'
        f'👤 {obj.name} | 📞 {obj.phone}'
        f'{product_info}\n'
        f'💬 {obj.comment or "—"}'
    )

    if settings.MANAGER_EMAIL:
        send_mail(
            subject=f'Заказ в 1 клик — {obj.name}',
            message=f'Имя: {obj.name}\nТелефон: {obj.phone}\nТовар: {obj.product or "не указан"}\nКомментарий: {obj.comment or "—"}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.MANAGER_EMAIL],
            fail_silently=True,
        )

    return HttpResponse(SUCCESS_HTML)


@require_POST
def selection_submit(request):
    form = SelectionRequestForm(request.POST)
    if not form.is_valid():
        return render(request, 'leads/partials/selection_form.html', {'form': form})

    d = form.cleaned_data
    obj = SelectionRequest.objects.create(
        name=d['name'],
        phone=d['phone'],
        city=d.get('city', ''),
        area_sqm=d.get('area_sqm'),
        room_type=d.get('room_type', ''),
        budget=d.get('budget', ''),
        needs_installation=d.get('needs_installation', False),
        timeline=d.get('timeline', ''),
        comment=d.get('comment', ''),
    )

    send_telegram(
        f'🔍 <b>Заявка на подбор</b>\n'
        f'👤 {obj.name} | 📞 {obj.phone}\n'
        f'📍 {obj.city or "—"} | 📐 {obj.area_sqm or "—"} м²\n'
        f'🏠 {obj.room_type or "—"} | 💰 {obj.budget or "—"}\n'
        f'🔧 Монтаж: {"Да" if obj.needs_installation else "Нет"}\n'
        f'📅 {obj.timeline or "—"}\n'
        f'💬 {obj.comment or "—"}'
    )

    if settings.MANAGER_EMAIL:
        send_mail(
            subject=f'Заявка на подбор — {obj.name}',
            message=(
                f'Имя: {obj.name}\nТелефон: {obj.phone}\nГород: {obj.city}\n'
                f'Площадь: {obj.area_sqm} м²\nТип: {obj.room_type}\nБюджет: {obj.budget}\n'
                f'Монтаж: {"Да" if obj.needs_installation else "Нет"}\n'
                f'Срок: {obj.timeline}\nКомментарий: {obj.comment or "—"}'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.MANAGER_EMAIL],
            fail_silently=True,
        )

    return HttpResponse(SUCCESS_HTML)


@require_POST
def installation_submit(request):
    form = InstallationRequestForm(request.POST)
    if not form.is_valid():
        return render(request, 'leads/partials/installation_form.html', {'form': form})

    d = form.cleaned_data
    obj = InstallationRequest.objects.create(
        name=d['name'],
        phone=d['phone'],
        address=d['address'],
        equipment_type=d.get('equipment_type', ''),
        has_equipment=d.get('has_equipment', False),
        floor=d.get('floor'),
        wall_type=d.get('wall_type', ''),
        needs_channel=d.get('needs_channel', False),
        comment=d.get('comment', ''),
    )

    send_telegram(
        f'🔧 <b>Заявка на монтаж</b>\n'
        f'👤 {obj.name} | 📞 {obj.phone}\n'
        f'📍 {obj.address}\n'
        f'🏗️ {obj.equipment_type or "—"} | Этаж: {obj.floor or "—"}\n'
        f'🧱 Стена: {obj.wall_type or "—"}\n'
        f'✅ Уже куплен: {"Да" if obj.has_equipment else "Нет"}\n'
        f'🔩 Закладка трассы: {"Да" if obj.needs_channel else "Нет"}\n'
        f'💬 {obj.comment or "—"}'
    )

    if settings.MANAGER_EMAIL:
        send_mail(
            subject=f'Заявка на монтаж — {obj.name}',
            message=(
                f'Имя: {obj.name}\nТелефон: {obj.phone}\nАдрес: {obj.address}\n'
                f'Оборудование: {obj.equipment_type}\nУже куплен: {"Да" if obj.has_equipment else "Нет"}\n'
                f'Этаж: {obj.floor}\nСтена: {obj.wall_type}\n'
                f'Закладка трассы: {"Да" if obj.needs_channel else "Нет"}\n'
                f'Комментарий: {obj.comment or "—"}'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.MANAGER_EMAIL],
            fail_silently=True,
        )

    return HttpResponse(SUCCESS_HTML)


def selection_page(request):
    form = SelectionRequestForm()
    return render(request, 'leads/selection.html', {'form': form})


def installation_page(request):
    form = InstallationRequestForm()
    return render(request, 'leads/installation.html', {'form': form})
