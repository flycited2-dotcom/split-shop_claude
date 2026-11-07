from apps.catalog.sitemaps import SiteSitemap

from .loader import get_articles


class ArticleSitemap(SiteSitemap):
    """Список /articles/ + каждая статья; lastmod — дата выхода из state.json."""
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        arts = list(get_articles().values())
        if not arts:
            return []  # пустой раздел закрыт noindex — в карту не кладём
        return ['__index__'] + arts

    def location(self, item):
        return '/articles/' if item == '__index__' else item.url

    def lastmod(self, item):
        arts = list(get_articles().values())
        if item == '__index__':
            return max(a.date for a in arts) if arts else None
        return item.date
