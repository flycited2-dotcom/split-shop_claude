import io
from django.template.loader import render_to_string
from weasyprint import HTML
from apps.catalog.models import Product


def generate_price_pdf(user, request):
    products = Product.objects.filter(is_active=True).select_related(
        'brand', 'category', 'stock'
    ).order_by('brand__title', 'title')

    items = []
    for p in products:
        stock_qty = p.stock.quantity if hasattr(p, 'stock') else 0
        wholesale = user.get_wholesale_price(p.price_wholesale) if p.price_wholesale else None
        items.append({
            'articul': p.articul,
            'title': p.title,
            'brand': str(p.brand) if p.brand else '',
            'stock': stock_qty,
            'ric': p.ric,
            'price': wholesale,
        })

    html_str = render_to_string('export/price_pdf.html', {
        'user': user, 'items': items
    })
    pdf_buf = io.BytesIO()
    HTML(string=html_str, base_url=request.build_absolute_uri('/')).write_pdf(pdf_buf)
    pdf_buf.seek(0)
    return pdf_buf
