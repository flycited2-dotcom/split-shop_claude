from django.db.models import Count, Q

from .models import Brand
from .filters import (
    BTU_VALUES, AREA_CHOICES, INVERTER_CHOICES, COLOR_CHOICES,
    ProductFilter, _btu_q, _area_q, _color_q, WIFI_Q,
)


def _apply_filters_excluding(get_data, exclude_key, base_qs):
    """Re-apply ProductFilter on base_qs, dropping `exclude_key` from query data
    so the resulting queryset shows what *other* filters constrain to.
    """
    data = get_data.copy()
    # Pop both single-value and list-style keys
    while exclude_key in data:
        del data[exclude_key]
    return ProductFilter(data, queryset=base_qs).qs


def compute_facets(get_data, base_qs):
    """Return facet groups (with counts) for the catalog sidebar.

    Each group's count is computed against `base_qs` filtered by every other
    active group except itself. Selected entries with count=0 are kept so the
    user can see and un-tick them.
    """
    selected_brand_ids = {str(v) for v in get_data.getlist('brand')}
    selected_btu = set(get_data.getlist('btu'))
    selected_area = set(get_data.getlist('area'))
    selected_inv = set(get_data.getlist('inverter'))
    selected_color = set(get_data.getlist('color'))
    selected_wifi = get_data.get('wifi') in ('1', 'true', 'on', 'True')

    qs_no_brand    = _apply_filters_excluding(get_data, 'brand', base_qs)
    qs_no_btu      = _apply_filters_excluding(get_data, 'btu', base_qs)
    qs_no_area     = _apply_filters_excluding(get_data, 'area', base_qs)
    qs_no_inverter = _apply_filters_excluding(get_data, 'inverter', base_qs)
    qs_no_color    = _apply_filters_excluding(get_data, 'color', base_qs)
    qs_no_wifi     = _apply_filters_excluding(get_data, 'wifi', base_qs)

    # --- Brand: single GROUP BY query --------------------------------------
    brand_counts = dict(
        qs_no_brand.values_list('brand_id').annotate(n=Count('id'))
    )
    visible_brand_ids = {bid for bid, n in brand_counts.items() if n > 0}
    visible_brand_ids.update(int(b) for b in selected_brand_ids if b.isdigit())
    brand_qs = Brand.objects.filter(id__in=visible_brand_ids).order_by('title')

    brand_facet = []
    for b in brand_qs:
        brand_facet.append({
            'value':    str(b.id),
            'label':    b.title,
            'count':    brand_counts.get(b.id, 0),
            'selected': str(b.id) in selected_brand_ids,
        })

    # --- BTU: 11 individual counts ----------------------------------------
    btu_facet = []
    for code in BTU_VALUES:
        n = qs_no_btu.filter(_btu_q([code])).count()
        if n == 0 and code not in selected_btu:
            continue
        btu_facet.append({
            'value':    code,
            'label':    f'{int(code)} 000 BTU',
            'count':    n,
            'selected': code in selected_btu,
        })

    # --- Area (м²): 6 counts -------------------------------------------------
    area_facet = []
    for code, label in AREA_CHOICES:
        n = qs_no_area.filter(_area_q([code])).count()
        if n == 0 and code not in selected_area:
            continue
        area_facet.append({
            'value':    code,
            'label':    label,
            'count':    n,
            'selected': code in selected_area,
        })

    # --- Inverter: 2 counts ------------------------------------------------
    inv_q = Q(title__iregex=r'инвертор|inverter')
    inv_facet = [
        {
            'value':    'inverter',
            'label':    'Инвертор',
            'count':    qs_no_inverter.filter(inv_q).count(),
            'selected': 'inverter' in selected_inv,
        },
        {
            'value':    'onoff',
            'label':    'Он-офф',
            'count':    qs_no_inverter.exclude(inv_q).count(),
            'selected': 'onoff' in selected_inv,
        },
    ]

    # --- Color: 4 counts ---------------------------------------------------
    color_facet = []
    for key, label in COLOR_CHOICES:
        n = qs_no_color.filter(_color_q([key])).count()
        if n == 0 and key not in selected_color:
            continue
        color_facet.append({
            'value':    key,
            'label':    label,
            'count':    n,
            'selected': key in selected_color,
        })

    # --- Wi-Fi: 1 count (простой чекбокс, не пара «есть/нет») ---------------
    wifi_facet = {
        'count':    qs_no_wifi.filter(WIFI_Q).distinct().count(),
        'selected': selected_wifi,
    }

    return {
        'brand':    brand_facet,
        'btu':      btu_facet,
        'area':     area_facet,
        'inverter': inv_facet,
        'color':    color_facet,
        'wifi':     wifi_facet,
    }
