import datetime
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from .excel import generate_price_excel
from .pdf import generate_price_pdf


@login_required
def export_excel(request):
    if not request.user.is_approved:
        return HttpResponse('Доступ закрыт', status=403)
    buf = generate_price_excel(request.user)
    date = datetime.date.today().strftime('%Y-%m-%d')
    response = HttpResponse(
        buf.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="splithub-price-{date}.xlsx"'
    return response


@login_required
def export_pdf(request):
    if not request.user.is_approved:
        return HttpResponse('Доступ закрыт', status=403)
    buf = generate_price_pdf(request.user, request)
    date = datetime.date.today().strftime('%Y-%m-%d')
    response = HttpResponse(buf.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="splithub-price-{date}.pdf"'
    return response
