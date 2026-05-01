from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import RegistrationForm


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request,
                'Регистрация прошла успешно. Ожидайте одобрения менеджера.')
            return redirect('pending')
    else:
        form = RegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})


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
