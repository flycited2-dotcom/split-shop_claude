from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import IndividualRegistrationForm, CompanyRegistrationForm


def register(request):
    """Регистрация с двумя табами: физлицо (по умолчанию) и юрлицо."""
    active_tab = request.POST.get('account_type') or request.GET.get('tab') or 'individual'
    if active_tab not in ('individual', 'company'):
        active_tab = 'individual'

    individual_form = IndividualRegistrationForm()
    company_form = CompanyRegistrationForm()

    if request.method == 'POST':
        if active_tab == 'individual':
            individual_form = IndividualRegistrationForm(request.POST)
            if individual_form.is_valid():
                user = individual_form.save()
                login(request, user)
                messages.success(request, 'Аккаунт создан. Добро пожаловать!')
                return redirect('home')
        else:
            company_form = CompanyRegistrationForm(request.POST)
            if company_form.is_valid():
                company_form.save()
                messages.success(
                    request,
                    'Заявка отправлена. Менеджер проверит данные и откроет '
                    'доступ к оптовым ценам.',
                )
                return redirect('pending')

    return render(request, 'accounts/register.html', {
        'individual_form': individual_form,
        'company_form': company_form,
        'active_tab': active_tab,
    })


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('account_dashboard')
        messages.error(request, 'Неверный логин или пароль')
    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    return redirect('home')


def pending(request):
    return render(request, 'accounts/pending.html')


@login_required
def dashboard(request):
    if not request.user.is_approved:
        return redirect('pending')
    orders = request.user.orders.all()[:10]
    return render(request, 'accounts/dashboard.html', {'orders': orders})


@login_required
def order_list(request):
    orders = request.user.orders.all()
    return render(request, 'orders/order_list.html', {'orders': orders})


@login_required
def order_detail(request, pk):
    from django.shortcuts import get_object_or_404
    from apps.orders.models import Order
    order = get_object_or_404(Order, pk=pk, user=request.user)
    return render(request, 'orders/order_detail.html', {'order': order})
