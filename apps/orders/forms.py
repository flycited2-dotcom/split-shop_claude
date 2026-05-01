from django import forms


class CheckoutForm(forms.Form):
    delivery_address = forms.CharField(
        label='Адрес доставки',
        widget=forms.Textarea(attrs={'rows': 3})
    )
    comment = forms.CharField(
        label='Комментарий к заказу',
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False
    )
