from django.db import models


class QuickOrder(models.Model):
    name = models.CharField('Имя', max_length=150)
    phone = models.CharField('Телефон', max_length=30)
    product = models.ForeignKey(
        'catalog.Product', null=True, blank=True,
        on_delete=models.SET_NULL, verbose_name='Товар'
    )
    comment = models.TextField('Комментарий', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Заказ в 1 клик'
        verbose_name_plural = 'Заказы в 1 клик'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} {self.phone} ({self.created_at:%d.%m.%Y})'


class SelectionRequest(models.Model):
    name = models.CharField('Имя', max_length=150)
    phone = models.CharField('Телефон', max_length=30)
    city = models.CharField('Город', max_length=100, blank=True)
    area_sqm = models.PositiveIntegerField('Площадь, м²', null=True, blank=True)
    room_type = models.CharField('Тип помещения', max_length=100, blank=True)
    budget = models.CharField('Бюджет', max_length=100, blank=True)
    needs_installation = models.BooleanField('Нужен монтаж', default=False)
    timeline = models.CharField('Когда планируется покупка', max_length=100, blank=True)
    comment = models.TextField('Комментарий', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Заявка на подбор'
        verbose_name_plural = 'Заявки на подбор'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} {self.phone} ({self.created_at:%d.%m.%Y})'


class QuizResult(models.Model):
    ROOM_TYPE_CHOICES = [
        ('apartment', 'Квартира'),
        ('house', 'Дом'),
        ('office', 'Офис'),
        ('commercial', 'Коммерция'),
        ('shop', 'Магазин/HoReCa'),  # legacy: ранние записи до расширения choices
    ]

    area_sqm = models.PositiveIntegerField('Площадь, м²')
    room_type = models.CharField('Тип помещения', max_length=20, choices=ROOM_TYPE_CHOICES)
    budget_max = models.PositiveIntegerField('Бюджет до, ₽', null=True, blank=True)
    needs_inverter = models.BooleanField('Тихий/инвертор', default=False)
    needs_heating = models.BooleanField('Нужен прогрев зимой', default=False)
    needs_wifi = models.BooleanField('Wi-Fi управление', default=False)
    wanted_brand = models.ForeignKey(
        'catalog.Brand', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='quiz_results',
        verbose_name='Предпочитаемый бренд',
    )
    # legacy: шаг «Цвет» убран из UI; поле остаётся для исторических записей.
    needs_black = models.BooleanField('Чёрный цвет (legacy)', default=False)
    recommended_btu = models.PositiveSmallIntegerField('Подобранный BTU, тыс.', null=True, blank=True)
    recommended_product_ids = models.JSONField('ID подобранных товаров', default=list, blank=True)
    contact_name = models.CharField('Имя', max_length=150, blank=True)
    contact_phone = models.CharField('Телефон', max_length=30, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Прохождение квиза'
        verbose_name_plural = 'Прохождения квиза'
        ordering = ['-created_at']

    def __str__(self):
        contact = self.contact_phone or 'без контакта'
        return f'{self.area_sqm} м² — {self.recommended_btu}k BTU ({contact}) {self.created_at:%d.%m.%Y}'


class InstallationRequest(models.Model):
    name = models.CharField('Имя', max_length=150)
    phone = models.CharField('Телефон', max_length=30)
    address = models.TextField('Адрес объекта')
    equipment_type = models.CharField('Тип оборудования', max_length=150, blank=True)
    has_equipment = models.BooleanField('Кондиционер уже куплен', default=False)
    floor = models.PositiveSmallIntegerField('Этаж', null=True, blank=True)
    wall_type = models.CharField('Тип стены', max_length=100, blank=True)
    needs_channel = models.BooleanField('Нужна закладка трассы', default=False)
    comment = models.TextField('Комментарий', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Заявка на монтаж'
        verbose_name_plural = 'Заявки на монтаж'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} {self.phone} ({self.created_at:%d.%m.%Y})'
