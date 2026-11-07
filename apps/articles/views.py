"""Раздел /articles/ — статьи робота автовыкладки (см. loader.py)."""
import json

from django.conf import settings
from django.core.paginator import EmptyPage, Paginator
from django.http import Http404
from django.shortcuts import render
from django.templatetags.static import static

from .loader import get_articles, render_article

PER_PAGE = 20

# Подписи для карточек ссылок из поля links. Неизвестный путь — подпись
# берётся из товара/подборки, а если не нашлась — карточка не выводится.
PAGE_TITLES = {
    '/': 'Главная SplitHome',
    '/catalog/': 'Каталог кондиционеров',
    '/quiz/': 'Подбор кондиционера за 2 минуты',
    '/selection/': 'Подбор кондиционера',
    '/installation/': 'Монтаж кондиционера',
    '/service/': 'Обслуживание и ремонт',
    '/delivery/': 'Доставка по Крыму',
    '/payment/': 'Оплата',
    '/warranty/': 'Гарантия',
    '/contacts/': 'Контакты',
    '/about/': 'О компании',
}


def _link_title(path):
    if path in PAGE_TITLES:
        return PAGE_TITLES[path]
    parts = [p for p in path.split('/') if p]
    if len(parts) == 2 and parts[0] == 'catalog':
        from apps.catalog.collections import get_collection
        coll = get_collection(parts[1])
        return coll.h1 if coll else ''
    if len(parts) == 2 and parts[0] == 'product':
        from apps.catalog.models import Product
        from apps.catalog.slugs import to_latin
        p = Product.objects.filter(slug=to_latin(parts[1]), is_active=True).only('title').first()
        return p.title if p else ''
    return ''


def _link_cards(article):
    cards = []
    for path in article.links:
        if not path.startswith('/') or path.startswith('//'):
            continue
        title = _link_title(path)
        if title and all(c['url'] != path for c in cards):
            cards.append({'url': path, 'title': title})
        if len(cards) == 4:
            break
    for path in ('/catalog/', '/quiz/'):  # минимум две карточки
        if len(cards) >= 2:
            break
        if all(c['url'] != path for c in cards):
            cards.append({'url': path, 'title': PAGE_TITLES[path]})
    return cards


def _ld(data):
    # </script> внутри строки не должен закрыть тег
    return json.dumps(data, ensure_ascii=False).replace('</', r'<\/')


def article_list(request):
    arts = list(get_articles().values())
    paginator = Paginator(arts, PER_PAGE)
    raw = request.GET.get('page') or '1'
    if not raw.isdigit():
        raise Http404
    try:
        page = paginator.page(int(raw))
    except EmptyPage:
        if int(raw) == 1:
            page = None
        else:
            raise Http404
    canonical = f'{settings.SITE_URL}/articles/'
    if page is not None and page.number > 1:
        canonical += f'?page={page.number}'
    return render(request, 'articles/list.html', {
        'page_obj': page,
        'articles': page.object_list if page else [],
        'canonical_url': canonical,
        'noindex': not arts,
    })


def article_detail(request, slug):
    arts = get_articles()
    article = arts.get(slug)
    if article is None:
        raise Http404('Статья не найдена')
    rendered = render_article(article, arts)
    url = f'{settings.SITE_URL}{article.url}'
    image = article.image or static('img/favicon/og-image.jpg')
    if image.startswith('/'):
        image = settings.SITE_URL + image

    others = [a for a in arts.values() if a.slug != slug]
    # сначала той же категории, внутри — новые сверху (arts уже отсортирован)
    others.sort(key=lambda a: a.category != article.category or not article.category)
    org = {'@type': 'Organization', 'name': 'SplitHome', 'url': settings.SITE_URL + '/'}
    graph = [
        {'@type': 'Article', 'headline': article.h1[:110], 'description': article.description,
         'datePublished': article.date.isoformat(), 'dateModified': article.date.isoformat(),
         'inLanguage': 'ru', 'image': image, 'mainEntityOfPage': url,
         'author': org, 'publisher': {**org, 'logo': {
             '@type': 'ImageObject', 'url': settings.SITE_URL + static('img/favicon/favicon-512.png')}}},
        {'@type': 'BreadcrumbList', 'itemListElement': [
            {'@type': 'ListItem', 'position': 1, 'name': 'Главная', 'item': settings.SITE_URL + '/'},
            {'@type': 'ListItem', 'position': 2, 'name': 'Статьи', 'item': settings.SITE_URL + '/articles/'},
            {'@type': 'ListItem', 'position': 3, 'name': article.h1, 'item': url}]},
    ]
    if rendered['faq']:
        graph.append({'@type': 'FAQPage', 'mainEntity': [
            {'@type': 'Question', 'name': q_text,
             'acceptedAnswer': {'@type': 'Answer', 'text': a_text}}
            for _q, _a, q_text, a_text in rendered['faq']]})
    return render(request, 'articles/detail.html', {
        'article': article,
        'content_html': rendered['html'],
        'toc': rendered['toc'],
        'faq': rendered['faq'],
        'canonical_url': url,
        'og_image': image,
        'link_cards': _link_cards(article),
        'more': others[:4],
        'json_ld': _ld({'@context': 'https://schema.org', '@graph': graph}),
    })
