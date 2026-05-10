from django.conf import settings


def yandex_metrika(request):
    return {'YANDEX_METRIKA_ID': getattr(settings, 'YANDEX_METRIKA_ID', '')}
