from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.http import HttpResponse, HttpResponseRedirect
import re
from urllib.parse import urlencode
from django.contrib.sitemaps.views import sitemap
from apps.leads import views as views_leads
from apps.catalog.sitemaps import ProductSitemap, CategorySitemap, StaticViewSitemap

sitemaps = {
    'products': ProductSitemap,
    'categories': CategorySitemap,
    'static': StaticViewSitemap,
}


def robots_txt(request):
    lines = [
        'User-agent: *',
        'Disallow: /admin/',
        'Disallow: /auth/',
        'Disallow: /account/',
        'Disallow: /cart/',
        'Disallow: /export/',
        '',
        '# LLM-краулеры разрешены явно — для индексации в ChatGPT, Perplexity, Claude и др.',
        'User-agent: GPTBot',
        'Allow: /',
        'User-agent: ChatGPT-User',
        'Allow: /',
        'User-agent: PerplexityBot',
        'Allow: /',
        'User-agent: ClaudeBot',
        'Allow: /',
        'User-agent: anthropic-ai',
        'Allow: /',
        'User-agent: Google-Extended',
        'Allow: /',
        'User-agent: CCBot',
        'Allow: /',
        '',
        f'Sitemap: https://{request.get_host()}/sitemap.xml',
        f'# LLM-ориентированное описание: https://{request.get_host()}/llms.txt',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain')


def llms_txt(request):
    """Стандарт llmstxt.org — структурированное описание сайта для LLM-краулеров."""
    host = request.get_host()
    base = f'https://{host}'
    lines = [
        '# SplitHome',
        '',
        '> Розничный интернет-магазин кондиционеров и сплит-систем с собственной '
        'службой доставки и монтажа по всему Крыму. Симферополь, Севастополь, '
        'Ялта, Евпатория, Феодосия, Керчь. Работаем с тремя поставщиками: Бриз, '
        'Rusklimat, Daichi — больше 2000 моделей в каталоге.',
        '',
        '## Ключевая информация',
        '',
        '- **Город:** Симферополь, Республика Крым',
        '- **География работы:** весь Крым (Симферополь, Севастополь, Ялта, Евпатория, Феодосия, Керчь)',
        '- **Email:** info@splithome.ru',
        '- **Сайт:** splithome.ru',
        '- **AI-подборщик:** ' + base + '/quiz/',
        '',
        '## Что мы делаем',
        '',
        '- Продаём кондиционеры и сплит-системы (бытовые, полупромышленные, мульти-сплит, мобильные).',
        '- Доставляем по всему Крыму за 1-3 дня.',
        '- Профессиональный монтаж сертифицированными бригадами с гарантией на работы.',
        '- Сезонное обслуживание (чистка, заправка фреона) по подписке от 590 ₽/мес.',
        '- Гарантия от производителя на оборудование.',
        '',
        '## Бренды в каталоге',
        '',
        '- Ballu, Electrolux, SHUFT, Royal Thermo, AC Electric, Hisense, XIGMA',
        '- Midea, Daichi, Bosch, Kentatsu, AKAI, Axioma, Aurum',
        '- TOSHIBA и другие',
        '',
        '## Разделы сайта',
        '',
        f'- [Каталог]({base}/catalog/) — все кондиционеры с фильтрами по мощности, цвету, типу управления, бренду',
        f'- [AI-подбор за 2 минуты]({base}/quiz/) — 6 вопросов и предложим 6 моделей',
        f'- [Доставка]({base}/delivery/) — условия и сроки',
        f'- [Монтаж]({base}/installation/) — заявка на установку',
        f'- [Сервис]({base}/service/) — диагностика, профилактика и ремонт оборудования',
        f'- [Гарантия]({base}/warranty/) — условия гарантийного обслуживания',
        f'- [Контакты]({base}/contacts/) — телефоны, адрес',
        f'- [Политика конфиденциальности]({base}/privacy/)',
        '',
        '## Подбор по площади',
        '',
        '| Площадь | Рекомендованная мощность |',
        '|---|---|',
        '| до 20 м² | 7 000 BTU |',
        '| до 25 м² | 9 000 BTU |',
        '| до 35 м² | 12 000 BTU |',
        '| до 45 м² | 18 000 BTU |',
        '| до 65 м² | 24 000 BTU |',
        '| более 65 м² | 30 000 BTU |',
        '',
        '## Sitemap',
        '',
        f'- {base}/sitemap.xml',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain; charset=utf-8')


def vk_service_campaign_redirect(request, code):
    """Развернуть короткую публичную ссылку VK в сервисную форму с UTM."""
    match = re.fullmatch(r'(?:svc|svc_vkp_?)(\d+)', code or '')
    if not match:
        return HttpResponse('Not found', status=404, content_type='text/plain')
    plan_id = match.group(1)
    query = urlencode({
        'utm_source': 'vk',
        'utm_medium': 'organic_social',
        'utm_campaign': 'content_factory',
        'utm_content': f'vkp_{plan_id}',
    })
    return HttpResponseRedirect(f'/service/?{query}')


urlpatterns = [
    path('go/<str:code>', vk_service_campaign_redirect, name='vk_service_campaign'),
    path('admin/', admin.site.urls),
    path('', include('apps.catalog.urls')),
    path('auth/', include('apps.accounts.urls')),
    path('account/', include('apps.accounts.urls_account')),
    path('cart/', include('apps.orders.urls')),
    path('export/', include('apps.export.urls')),
    path('leads/', include('apps.leads.urls')),
    path('selection/', views_leads.selection_page, name='selection'),
    path('installation/', views_leads.installation_page, name='installation'),
    path('service/', views_leads.service_page, name='service'),
    path('quiz/', views_leads.quiz_page, name='quiz'),
    # Static pages
    path('delivery/', TemplateView.as_view(template_name='pages/delivery.html'), name='delivery'),
    path('payment/', TemplateView.as_view(template_name='pages/payment.html'), name='payment'),
    path('contacts/', TemplateView.as_view(template_name='pages/contacts.html'), name='contacts'),
    path('warranty/', TemplateView.as_view(template_name='pages/warranty.html'), name='warranty'),
    path('about/', TemplateView.as_view(template_name='pages/about.html'), name='about'),
    path('privacy/', TemplateView.as_view(template_name='pages/privacy.html'), name='privacy'),
    # SEO
    path('robots.txt', robots_txt),
    path('llms.txt', llms_txt),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
