from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.http import HttpResponse
from django.conf import settings

from apps.catalog.models import Product
from apps.notifications.telegram import send_telegram
from .forms import QuickOrderForm, SelectionRequestForm, InstallationRequestForm
from .models import QuickOrder, SelectionRequest, InstallationRequest, QuizResult
from . import quiz_logic


SUCCESS_HTML = '<p class="text-green-600 font-semibold py-4">✅ Заявка принята! Менеджер свяжется с вами в ближайшее время.</p>'


@require_POST
def quick_order_submit(request):
    form = QuickOrderForm(request.POST)
    if not form.is_valid():
        return render(request, 'leads/partials/quick_order_form.html', {
            'form': form,
            'product_id': request.POST.get('product_id', ''),
        })

    product = None
    try:
        product_id = int(request.POST.get('product_id', ''))
        product = Product.objects.filter(pk=product_id, is_active=True).first()
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


ROOM_OPTIONS = [
    ('apartment', 'Квартира', '🏠'),
    ('house', 'Дом', '🏡'),
    ('office', 'Офис', '💼'),
    ('commercial', 'Коммерция', '🏪'),
]
BUDGET_OPTIONS = [
    ('30000', 'до 30 000 ₽'),
    ('40000', 'до 40 000 ₽'),
    ('50000', 'до 50 000 ₽'),
    ('70000', 'до 70 000 ₽'),
    ('0', 'Не важно'),
]
# Пилюли шага 1: (значение area_sqm, подпись). BTU считается на сервере через
# quiz_logic.btu_candidates() — на границах автоматически добавится secondary.
AREA_OPTIONS = [
    ('20',  'до 20 м² (7 BTU)'),
    ('25',  'до 25 м² (9 BTU)'),
    ('35',  'до 35 м² (12 BTU)'),
    ('45',  'до 45 м² (18 BTU)'),
    ('65',  'до 65 м² (24 BTU)'),
    ('100', 'более 65 м² (30 BTU)'),
]


def _quiz_ctx_base(step, post=None):
    post = post or {}
    return {
        'step': step,
        'area_sqm': post.get('area_sqm', ''),
        'room_type': post.get('room_type', ''),
        'budget': post.get('budget', ''),
        'inverter': post.get('inverter', ''),
        'heating': post.get('heating', ''),
        'color': post.get('color', ''),
        'room_options': ROOM_OPTIONS,
        'budget_options': BUDGET_OPTIONS,
        'area_options': AREA_OPTIONS,
    }


def quiz_page(request):
    return render(request, 'leads/quiz.html', _quiz_ctx_base(1))


def _quiz_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@require_POST
def quiz_step(request):
    current = _quiz_int(request.POST.get('step'), 1)
    next_step = current + 1
    ctx = _quiz_ctx_base(next_step, request.POST)

    if next_step <= 6:
        return render(request, 'leads/partials/_quiz_step.html', ctx)

    area = max(5, _quiz_int(ctx['area_sqm'], 25))
    btu, secondary_btus = quiz_logic.btu_candidates(area)
    budget_max = _quiz_int(ctx['budget']) or None
    needs_inverter = ctx['inverter'] == 'yes'
    needs_heating = ctx['heating'] == 'yes'
    needs_black = ctx['color'] == 'black'

    products, relaxed = quiz_logic.recommend_products(
        btu,
        budget_max=budget_max,
        needs_inverter=needs_inverter,
        needs_black=needs_black,
        room_type=ctx['room_type'] or None,
        secondary_btus=secondary_btus,
    )

    quiz = QuizResult.objects.create(
        area_sqm=area,
        room_type=ctx['room_type'] or 'apartment',
        budget_max=budget_max,
        needs_inverter=needs_inverter,
        needs_heating=needs_heating,
        needs_black=needs_black,
        recommended_btu=btu,
        recommended_product_ids=[p.id for p in products],
    )

    ctx.update({
        'step': 'result',
        'btu': btu,
        'secondary_btus': secondary_btus,
        'products': products,
        'relaxed': relaxed,
        'quiz_id': quiz.id,
        'budget_max': budget_max,
    })
    return render(request, 'leads/partials/_quiz_step.html', ctx)


@require_POST
def quiz_lead(request, quiz_id):
    name = request.POST.get('name', '').strip()
    phone = request.POST.get('phone', '').strip()
    if not name or not phone:
        return HttpResponse(
            '<p class="text-red-500 text-sm py-2">Заполните имя и телефон</p>',
            status=400,
        )

    quiz = QuizResult.objects.filter(pk=quiz_id).first()
    if not quiz:
        return HttpResponse(
            '<p class="text-red-500 text-sm py-2">Сессия квиза истекла, начните заново</p>',
            status=404,
        )

    quiz.contact_name = name
    quiz.contact_phone = phone
    quiz.save(update_fields=['contact_name', 'contact_phone'])

    send_telegram(
        f'🎯 <b>Quiz: подбор</b>\n'
        f'👤 {name} | 📞 {phone}\n'
        f'📐 {quiz.area_sqm} м² | {quiz.get_room_type_display()}\n'
        f'💰 Бюджет: {f"до {quiz.budget_max:,} ₽".replace(",", " ") if quiz.budget_max else "любой"}\n'
        f'⚙️ BTU: {quiz.recommended_btu}k · Инвертор: {"да" if quiz.needs_inverter else "нет"} · '
        f'Обогрев: {"да" if quiz.needs_heating else "нет"} · '
        f'Цвет: {"чёрный" if quiz.needs_black else "любой"}\n'
        f'🔗 /admin/leads/quizresult/{quiz.id}/'
    )

    return render(request, 'leads/partials/_quiz_thanks.html', {'name': name})
