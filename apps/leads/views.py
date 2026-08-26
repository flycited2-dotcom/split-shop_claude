import logging
import os
from html import escape

from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.http import HttpResponse
from django.conf import settings

from apps.catalog.models import Brand, Product
from apps.notifications.telegram import send_telegram
from .forms import (
    InstallationRequestForm, QuickOrderForm, SelectionRequestForm,
    ServiceRequestForm,
)
from .models import (
    InstallationRequest, QuickOrder, QuizResult, SelectionRequest,
    ServiceRequest,
)
from . import quiz_logic

logger = logging.getLogger(__name__)


# Inline success — для модалки (quick-order), где сам контейнер модалки уже виден.
SUCCESS_HTML = '<p class="text-green-600 font-semibold py-4">✅ Заявка принята! Менеджер свяжется с вами в ближайшее время.</p>'

# Overlay-модалка — для full-page форм (/selection/, /installation/). HTMX
# подменяет контейнер с формой на этот блок, и он fixed-overlay'ом
# отображается поверх страницы.
SUCCESS_MODAL_HTML = '''
<div class="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4 animate-in fade-in"
     onclick="if(event.target===this){this.remove();}">
  <div class="bg-white rounded-2xl shadow-xl p-6 sm:p-8 w-full max-w-md text-center relative">
    <button type="button" onclick="this.closest('.fixed').remove()"
            class="absolute top-3 right-4 text-ink-3 hover:text-ink text-2xl leading-none"
            aria-label="Закрыть">&times;</button>
    <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-green-100 flex items-center justify-center">
      <svg class="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7"/>
      </svg>
    </div>
    <h3 class="text-2xl font-bold mb-2">Заявка принята!</h3>
    <p class="text-ink-3 mb-6">Менеджер свяжется с вами в течение часа.</p>
    <a href="/" class="inline-block w-full bg-blue-600 text-white rounded-lg px-6 py-3 text-sm font-semibold hover:bg-blue-700 transition">На главную</a>
  </div>
</div>
'''


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

    return HttpResponse(SUCCESS_MODAL_HTML)


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

    return HttpResponse(SUCCESS_MODAL_HTML)


def selection_page(request):
    form = SelectionRequestForm()
    return render(request, 'leads/selection.html', {'form': form})


def installation_page(request):
    form = InstallationRequestForm()
    return render(request, 'leads/installation.html', {'form': form})


def service_page(request):
    initial = {
        key: request.GET.get(key, '')[:limit]
        for key, limit in (
            ('utm_source', 100), ('utm_medium', 100),
            ('utm_campaign', 150), ('utm_content', 150),
        )
    }
    return render(request, 'leads/service.html', {
        'form': ServiceRequestForm(initial=initial),
        'service_sent': request.GET.get('sent') == '1',
    })


@require_POST
def service_submit(request):
    form = ServiceRequestForm(request.POST)
    if not form.is_valid():
        template = ('leads/partials/service_form.html'
                    if request.headers.get('HX-Request') == 'true'
                    else 'leads/service.html')
        return render(request, template, {'form': form})

    d = form.cleaned_data
    obj = ServiceRequest.objects.create(
        name=d['name'],
        phone=d['phone'],
        locality=d.get('locality', ''),
        equipment_type=d['equipment_type'],
        service_type=d['service_type'],
        equipment_model=d.get('equipment_model', ''),
        comment=d.get('comment', ''),
        preferred_time=d.get('preferred_time', ''),
        privacy_accepted=d['privacy_accepted'],
        utm_source=d.get('utm_source', ''),
        utm_medium=d.get('utm_medium', ''),
        utm_campaign=d.get('utm_campaign', ''),
        utm_content=d.get('utm_content', ''),
    )

    attribution = ' / '.join(filter(None, (
        obj.utm_source, obj.utm_campaign, obj.utm_content,
    ))) or 'прямой переход'
    send_telegram(
        f'🛠 <b>Заявка на сервисное обслуживание</b>\n'
        f'👤 {escape(obj.name)} | 📞 {escape(obj.phone)}\n'
        f'📍 {escape(obj.locality or "—")}\n'
        f'⚙️ {escape(obj.get_equipment_type_display())}\n'
        f'🔧 {escape(obj.get_service_type_display())}\n'
        f'🏷 {escape(obj.equipment_model or "марка и модель не указаны")}\n'
        f'🕐 {escape(obj.preferred_time or "любое время")}\n'
        f'💬 {escape(obj.comment or "—")}\n'
        f'📊 Источник: {escape(attribution)}'
    )

    if settings.MANAGER_EMAIL:
        send_mail(
            subject=f'Заявка на сервис — {obj.name}',
            message=(
                f'Имя: {obj.name}\nТелефон: {obj.phone}\nНаселённый пункт: {obj.locality}\n'
                f'Оборудование: {obj.get_equipment_type_display()}\n'
                f'Вид обращения: {obj.get_service_type_display()}\n'
                f'Марка и модель: {obj.equipment_model or "—"}\n'
                f'Удобное время: {obj.preferred_time or "—"}\n'
                f'Описание: {obj.comment or "—"}\nИсточник: {attribution}'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.MANAGER_EMAIL],
            fail_silently=True,
        )

    if request.headers.get('HX-Request') == 'true':
        return HttpResponse(SUCCESS_MODAL_HTML)
    return redirect(f"{reverse('service')}?sent=1")


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
    ('20',  'до 20 м² (7 000 BTU)'),
    ('25',  'до 25 м² (9 000 BTU)'),
    ('35',  'до 35 м² (12 000 BTU)'),
    ('45',  'до 45 м² (18 000 BTU)'),
    ('65',  'до 65 м² (24 000 BTU)'),
    ('100', 'более 65 м² (30 000 BTU)'),
]

_BRAND_LOGO_EXTENSIONS = ('.svg', '.png', '.webp', '.jpg', '.jpeg')


def _brand_logo_static(slug):
    """Возвращает путь от STATIC_URL (`images/brands/{slug}.{ext}`), если
    файл лежит в `static/` (dev) или `STATIC_ROOT` (после collectstatic в
    docker-volume). Иначе — пустую строку.
    """
    candidate_bases = [
        os.path.join(settings.BASE_DIR, 'static'),
        str(settings.STATIC_ROOT) if settings.STATIC_ROOT else '',
    ]
    for ext in _BRAND_LOGO_EXTENSIONS:
        rel = f'images/brands/{slug}{ext}'
        for base in candidate_bases:
            if base and os.path.exists(os.path.join(base, rel)):
                return rel
    return ''


def _brand_options():
    return [
        {
            'id': b.id,
            'slug': b.slug,
            'title': b.title,
            'logo_static': _brand_logo_static(b.slug),
        }
        for b in Brand.objects.filter(featured_in_quiz=True).order_by('order', 'title')
    ]


def _quiz_ctx_base(step, post=None):
    post = post or {}
    return {
        'step': step,
        'area_sqm': post.get('area_sqm', ''),
        'room_type': post.get('room_type', ''),
        'inverter': post.get('inverter', ''),
        'wifi': post.get('wifi', ''),
        'heating': post.get('heating', ''),
        'budget': post.get('budget', ''),
        'brand': post.get('brand', ''),
        'room_options': ROOM_OPTIONS,
        'budget_options': BUDGET_OPTIONS,
        'area_options': AREA_OPTIONS,
        'brand_options': _brand_options(),
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

    # Кнопка «Назад» — рендерим предыдущий шаг с сохранёнными ответами.
    if request.POST.get('action') == 'back':
        prev = max(1, current - 1)
        return render(request, 'leads/partials/_quiz_step.html',
                      _quiz_ctx_base(prev, request.POST))

    next_step = current + 1
    ctx = _quiz_ctx_base(next_step, request.POST)

    if next_step <= 7:
        return render(request, 'leads/partials/_quiz_step.html', ctx)

    area = max(5, _quiz_int(ctx['area_sqm'], 25))
    btu, secondary_btus = quiz_logic.btu_candidates(area)
    budget_max = _quiz_int(ctx['budget']) or None
    needs_inverter = ctx['inverter'] == 'yes'
    needs_wifi = ctx['wifi'] == 'yes'
    needs_heating = ctx['heating'] == 'yes'
    brand_id = _quiz_int(ctx['brand']) or None

    brand_obj = None
    if brand_id:
        brand_obj = Brand.objects.filter(pk=brand_id).first()
        if brand_obj is None:
            brand_id = None

    products, relaxed = quiz_logic.recommend_products(
        btu,
        budget_max=budget_max,
        needs_inverter=needs_inverter,
        needs_wifi=needs_wifi,
        brand_id=brand_id,
        room_type=ctx['room_type'] or None,
        secondary_btus=secondary_btus,
    )
    if not products or 'btu_relaxed' in relaxed:
        logger.warning(
            'quiz_empty_or_btu_relaxed btu=%s budget=%s inverter=%s wifi=%s brand=%s room=%s relaxed=%s found=%s',
            btu, budget_max, needs_inverter, needs_wifi, brand_id,
            ctx['room_type'], relaxed, len(products),
        )

    quiz = QuizResult.objects.create(
        area_sqm=area,
        room_type=ctx['room_type'] or 'apartment',
        budget_max=budget_max,
        needs_inverter=needs_inverter,
        needs_heating=needs_heating,
        needs_wifi=needs_wifi,
        wanted_brand=brand_obj,
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
        'brand_title': brand_obj.title if brand_obj else '',
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

    quiz = QuizResult.objects.select_related('wanted_brand').filter(pk=quiz_id).first()
    if not quiz:
        return HttpResponse(
            '<p class="text-red-500 text-sm py-2">Сессия квиза истекла, начните заново</p>',
            status=404,
        )

    quiz.contact_name = name
    quiz.contact_phone = phone
    quiz.save(update_fields=['contact_name', 'contact_phone'])

    budget_str = f'до {quiz.budget_max:,} ₽'.replace(',', ' ') if quiz.budget_max else 'любой'
    brand_str = quiz.wanted_brand.title if quiz.wanted_brand else 'любой'

    send_telegram(
        f'🎯 <b>Quiz: подбор</b>\n'
        f'👤 {name} | 📞 {phone}\n'
        f'📐 {quiz.area_sqm} м² | {quiz.get_room_type_display()}\n'
        f'💰 Бюджет: {budget_str}\n'
        f'⚙️ BTU: {quiz.recommended_btu}k · Инвертор: {"да" if quiz.needs_inverter else "нет"} · '
        f'Wi-Fi: {"да" if quiz.needs_wifi else "нет"} · '
        f'Обогрев: {"да" if quiz.needs_heating else "нет"}\n'
        f'🏷 Бренд: {brand_str}\n'
        f'🔗 /admin/leads/quizresult/{quiz.id}/'
    )

    return render(request, 'leads/partials/_quiz_thanks.html', {'name': name})
