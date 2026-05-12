from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'company_name', 'inn',
                    'is_approved', 'date_joined']
    list_filter = ['is_approved', 'is_staff', 'is_active']
    search_fields = ['username', 'email', 'company_name', 'inn']
    actions = ['approve_users']
    readonly_fields = ['approved_at', 'approved_by', 'date_joined', 'last_login']

    fieldsets = UserAdmin.fieldsets + (
        ('Реквизиты компании', {
            'fields': ('company_name', 'inn', 'kpp', 'legal_address',
                       'phone', 'contact_person')
        }),
        ('Статус дилера', {
            'fields': ('is_approved', 'approved_at', 'approved_by',
                       'discount_percent')
        }),
    )

    def approve_users(self, request, queryset):
        count = 0
        for user in queryset.filter(is_approved=False):
            user.is_approved = True
            user.approved_at = timezone.now()
            user.approved_by = request.user
            user.save()
            count += 1
            if user.email:
                send_mail(
                    subject='Ваш аккаунт одобрен — СплитХаб',
                    message=(
                        f'Здравствуйте, {user.company_name}!\n\n'
                        f'Ваш аккаунт одобрен. Теперь вы можете оформлять заказы '
                        f'на сайте СплитХаб.'
                    ),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user.email],
                    fail_silently=True,
                )
        self.message_user(request, f'Одобрено пользователей: {count}')
    approve_users.short_description = 'Одобрить выбранных пользователей'
