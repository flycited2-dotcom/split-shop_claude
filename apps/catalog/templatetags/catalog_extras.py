import html
import re

from django import template
from django.template.defaultfilters import striptags

from apps.catalog.btu import extract_btu, btu_label

register = template.Library()


@register.simple_tag
def btu_for(product):
    """Возвращает '9 000 BTU (до 25 м²)' для карточки в листинге, либо ''."""
    if product is None:
        return ''
    btu = extract_btu(getattr(product, 'articul', ''))
    return btu_label(btu, with_area=True)


_BLOCK_TAGS = re.compile(r'</?(p|br|div|ul|ol|li|h[1-6])\b[^>]*>', re.IGNORECASE)
_WS = re.compile(r'\n\s*\n\s*\n+')


@register.filter
def clean_description(value):
    """Очистка описаний от поставщиков (Бриз/Rusklimat хранят escaped HTML).

    1. Декодируем HTML entities (`&lt;p&gt;` → `<p>`).
    2. Блочные теги заменяем на двойные переносы — чтобы абзацы остались
       читаемыми после striptags.
    3. Убираем оставшиеся теги.
    4. Нормализуем пустые строки (не больше двух подряд переносов).

    Чистый plain text (например, синтезированный для Daichi) пройдёт без
    изменений.
    """
    if not value:
        return ''
    # Двойной unescape: в БД встречается двойное экранирование (`&amp;ndash;`),
    # один проход даёт `&ndash;`, второй — нормальный «–».
    text = html.unescape(html.unescape(str(value)))
    text = _BLOCK_TAGS.sub('\n\n', text)
    text = striptags(text)
    text = _WS.sub('\n\n', text)
    return text.strip()
