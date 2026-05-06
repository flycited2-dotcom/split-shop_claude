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
