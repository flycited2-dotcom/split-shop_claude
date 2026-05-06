from django import forms


class QuickOrderForm(forms.Form):
    name = forms.CharField(label='Ваше имя', max_length=150,
                           widget=forms.TextInput(attrs={'placeholder': 'Иван Иванов'}))
    phone = forms.CharField(label='Телефон', max_length=30,
                            widget=forms.TextInput(attrs={'placeholder': '+7 999 123-45-67'}))
    comment = forms.CharField(label='Комментарий', required=False,
                              widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Любые пожелания...'}))


class SelectionRequestForm(forms.Form):
    name = forms.CharField(label='Ваше имя', max_length=150,
                           widget=forms.TextInput(attrs={'placeholder': 'Иван Иванов'}))
    phone = forms.CharField(label='Телефон', max_length=30,
                            widget=forms.TextInput(attrs={'placeholder': '+7 999 123-45-67'}))
    city = forms.CharField(label='Город', max_length=100, required=False,
                           widget=forms.TextInput(attrs={'placeholder': 'Москва'}))
    area_sqm = forms.IntegerField(label='Площадь помещения, м²', required=False,
                                  widget=forms.NumberInput(attrs={'placeholder': '25', 'min': 1}))
    room_type = forms.CharField(label='Тип помещения', max_length=100, required=False,
                                widget=forms.TextInput(attrs={'placeholder': 'Квартира, офис, магазин...'}))
    budget = forms.CharField(label='Бюджет', max_length=100, required=False,
                             widget=forms.TextInput(attrs={'placeholder': 'до 50 000 ₽'}))
    needs_installation = forms.BooleanField(label='Нужен монтаж', required=False)
    timeline = forms.CharField(label='Когда планируется покупка', max_length=100, required=False,
                               widget=forms.TextInput(attrs={'placeholder': 'В течение месяца'}))
    comment = forms.CharField(label='Комментарий', required=False,
                              widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Дополнительные пожелания...'}))


class InstallationRequestForm(forms.Form):
    name = forms.CharField(label='Ваше имя', max_length=150,
                           widget=forms.TextInput(attrs={'placeholder': 'Иван Иванов'}))
    phone = forms.CharField(label='Телефон', max_length=30,
                            widget=forms.TextInput(attrs={'placeholder': '+7 999 123-45-67'}))
    address = forms.CharField(label='Адрес объекта',
                              widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Москва, ул. Примерная, 1, кв. 5'}))
    equipment_type = forms.CharField(label='Тип оборудования', max_length=150, required=False,
                                     widget=forms.TextInput(attrs={'placeholder': 'Сплит-система 12000 BTU'}))
    has_equipment = forms.BooleanField(label='Кондиционер уже куплен', required=False)
    floor = forms.IntegerField(label='Этаж', required=False,
                               widget=forms.NumberInput(attrs={'placeholder': '5', 'min': 1}))
    wall_type = forms.CharField(label='Тип стены', max_length=100, required=False,
                                widget=forms.TextInput(attrs={'placeholder': 'Кирпич, бетон, газоблок...'}))
    needs_channel = forms.BooleanField(label='Нужна закладка трассы', required=False)
    comment = forms.CharField(label='Комментарий', required=False,
                              widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Дополнительная информация...'}))
