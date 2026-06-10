from django.conf import settings


def yandex_metrika(request):
    return {'YANDEX_METRIKA_ID': getattr(settings, 'YANDEX_METRIKA_ID', '')}


def seo_verification(request):
    """Токены подтверждения прав для панелей вебмастеров (Google/Yandex/Bing).
    Рендерятся в base.html как <meta> только при заполненном значении.
    """
    return {
        'GOOGLE_SITE_VERIFICATION': getattr(settings, 'GOOGLE_SITE_VERIFICATION', ''),
        'YANDEX_VERIFICATION': getattr(settings, 'YANDEX_VERIFICATION', ''),
        'BING_SITE_VERIFICATION': getattr(settings, 'BING_SITE_VERIFICATION', ''),
    }
