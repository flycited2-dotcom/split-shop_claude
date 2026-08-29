from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse

from apps.leads.models import ServiceRequest


@override_settings(SECURE_SSL_REDIRECT=False)
class ServiceRequestViewTest(TestCase):
    def test_short_vk_service_link_redirects_with_attribution(self):
        response = self.client.get('/go/svc14')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response['Location'],
            '/service/?utm_source=vk&utm_medium=organic_social&'
            'utm_campaign=content_factory&utm_content=vkp_14',
        )

    def test_unknown_short_link_is_not_an_open_redirect(self):
        self.assertEqual(self.client.get('/go/https://evil.example').status_code, 404)

    def test_page_keeps_utm_in_form(self):
        response = self.client.get(reverse('service'), {
            'utm_source': 'vk',
            'utm_campaign': 'content_factory',
            'utm_content': 'svc_vkp_14',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="utm_source" value="vk"')
        self.assertContains(response, 'name="utm_content" value="svc_vkp_14"')

    def test_valid_request_is_saved_and_sent_to_telegram(self):
        with patch('apps.leads.views.enqueue_manager_notifications') as telegram:
            response = self.client.post(reverse('service_submit'), {
                'name': 'Алексей',
                'phone': '+79780000000',
                'locality': 'Симферополь',
                'equipment_type': 'air_conditioner',
                'service_type': 'maintenance',
                'equipment_model': 'Daikin FTXP',
                'comment': 'Нужно очистить фильтры',
                'preferred_time': 'после 16:00',
                'privacy_accepted': 'on',
                'utm_source': 'vk',
                'utm_campaign': 'content_factory',
                'utm_content': 'svc_vkp_14',
            })

        self.assertRedirects(response, f"{reverse('service')}?sent=1")
        lead = ServiceRequest.objects.get()
        self.assertTrue(lead.privacy_accepted)
        self.assertEqual(lead.utm_content, 'svc_vkp_14')
        telegram.assert_called_once()
        message = telegram.call_args.kwargs['telegram_text']
        self.assertIn('Заявка на сервисное обслуживание', message)
        self.assertIn('svc_vkp_14', message)

    def test_form_works_without_htmx(self):
        response = self.client.get(reverse('service'))
        self.assertContains(response, 'method="post"')
        self.assertContains(response, f'action="{reverse("service_submit")}"')

    def test_htmx_submit_keeps_modal_response(self):
        with patch('apps.leads.views.enqueue_manager_notifications'):
            response = self.client.post(reverse('service_submit'), {
                'name': 'Алексей',
                'phone': '+79780000000',
                'equipment_type': 'air_conditioner',
                'service_type': 'maintenance',
                'privacy_accepted': 'on',
            }, HTTP_HX_REQUEST='true')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Заявка принята!')
        self.assertNotContains(response, '<html')

    def test_non_htmx_invalid_submit_renders_full_page(self):
        response = self.client.post(reverse('service_submit'), {
            'name': 'Алексей',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Поможем технике работать исправно')
        self.assertContains(response, 'Обязательное поле.')

    def test_consent_is_required(self):
        with patch('apps.leads.views.enqueue_manager_notifications') as telegram:
            response = self.client.post(reverse('service_submit'), {
                'name': 'Алексей',
                'phone': '+79780000000',
                'equipment_type': 'air_conditioner',
                'service_type': 'maintenance',
            })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ServiceRequest.objects.exists())
        telegram.assert_not_called()

    def test_user_html_is_escaped_in_telegram_message(self):
        with patch('apps.leads.views.enqueue_manager_notifications') as telegram:
            self.client.post(reverse('service_submit'), {
                'name': '<b>Чужой тег</b>',
                'phone': '+79780000000',
                'equipment_type': 'other',
                'service_type': 'diagnostics',
                'privacy_accepted': 'on',
            })
        message = telegram.call_args.kwargs['telegram_text']
        self.assertNotIn('<b>Чужой тег</b>', message)
        self.assertIn('&lt;b&gt;Чужой тег&lt;/b&gt;', message)

    def test_submit_get_is_not_allowed(self):
        self.assertEqual(self.client.get(reverse('service_submit')).status_code, 405)
