"""Защита от многострочных {# … #} в шаблонах.

Django-комментарий `{# … #}` работает ТОЛЬКО в пределах одной строки. Если
открыть его на одной строке, а закрыть на другой, шаблонизатор не считает это
комментарием и печатает текст на страницу. Дважды за 2026-08-29 такой
комментарий уезжал на прод — сначала поверх каталога, потом в карточку квиза.

Проверка статическая: сканирует все шаблоны проекта, не требует БД и ловит
проблему в любом новом файле, а не только на страницах, покрытых view-тестами.
Для многострочных пояснений используйте {% comment %} … {% endcomment %}.
"""
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class TemplateCommentsTest(SimpleTestCase):

    def _template_dirs(self):
        dirs = []
        for engine in settings.TEMPLATES:
            dirs.extend(Path(d) for d in engine.get('DIRS', []))
        return [d for d in dirs if d.exists()]

    def test_no_multiline_django_comments(self):
        offenders = []
        for root in self._template_dirs():
            for path in root.rglob('*.html'):
                for lineno, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
                    # Открыли {# и не закрыли #} в этой же строке — комментарий
                    # не сработает и попадёт в разметку как обычный текст.
                    if '{#' in line and '#}' not in line[line.index('{#'):]:
                        offenders.append(f'{path}:{lineno}: {line.strip()[:80]}')

        self.assertEqual(
            offenders, [],
            'Многострочный {# … #} не работает в Django и печатается на странице. '
            'Замените на {% comment %} … {% endcomment %}:\n' + '\n'.join(offenders),
        )
