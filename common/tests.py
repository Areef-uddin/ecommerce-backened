from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from .models import Notification


class CustomerNotificationApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = get_user_model().objects.create_user(
            email='notifications@example.com',
            password='test-password-123',
        )
        self.client.force_authenticate(user=self.customer)

    def test_unread_count_and_personal_mark_as_read(self):
        personal = Notification.objects.create(
            user=self.customer,
            title='Order update',
            message='Your order was packed.',
            category='orders',
        )
        global_notice = Notification.objects.create(
            title='Store update',
            message='New collection is available.',
            category='updates',
        )

        count_response = self.client.get('/api/common/notifications/unread_count/')
        self.assertEqual(count_response.status_code, status.HTTP_200_OK)
        self.assertEqual(count_response.data['count'], 1)

        list_response = self.client.get('/api/common/notifications/')
        notices = {item['id']: item for item in list_response.data}
        self.assertTrue(notices[personal.id]['can_mark_read'])
        self.assertFalse(notices[global_notice.id]['can_mark_read'])

        read_response = self.client.post(
            f'/api/common/notifications/{personal.id}/mark_as_read/',
        )
        self.assertEqual(read_response.status_code, status.HTTP_200_OK)
        personal.refresh_from_db()
        self.assertTrue(personal.is_read)

        global_read_response = self.client.post(
            f'/api/common/notifications/{global_notice.id}/mark_as_read/',
        )
        self.assertEqual(global_read_response.status_code, status.HTTP_403_FORBIDDEN)
