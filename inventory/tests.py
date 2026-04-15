from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .ppe_pdf_validation import validate_ppe_pdf_upload


class SuperuserAccessControlTests(TestCase):
    """Regression: staff must not reach admin-only user management or destructive APIs."""

    @classmethod
    def setUpTestData(cls):
        cls._password = 'Str0ng!Pass#word'
        cls.victim = User.objects.create_user(
            'victim_user', 'victim@test.local', cls._password,
        )
        cls.staff = User.objects.create_user(
            'staff_only', 'staff@test.local', cls._password, is_staff=True,
        )
        cls.superuser = User.objects.create_user(
            'super_u', 'super@test.local', cls._password,
            is_staff=True, is_superuser=True,
        )

    def test_anonymous_user_edit_redirects_to_login(self):
        url = reverse('user_edit', kwargs={'user_id': self.victim.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.url)

    def test_staff_get_user_edit_forbidden(self):
        self.client.login(username='staff_only', password=self._password)
        url = reverse('user_edit', kwargs={'user_id': self.victim.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_superuser_admin_api_ok(self):
        self.client.login(username='super_u', password=self._password)
        response = self.client.get(reverse('category_list'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get('success'))

    def test_staff_category_delete_permanently_forbidden(self):
        self.client.login(username='staff_only', password=self._password)
        url = reverse('category_delete_permanently', kwargs={'category_id': 99999})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

    def test_staff_supply_list_allowed(self):
        self.client.login(username='staff_only', password=self._password)
        url = reverse('supply_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)


class PpePdfUploadValidationTests(TestCase):
    def test_accepts_minimal_pdf_header(self):
        f = SimpleUploadedFile(
            'doc.pdf',
            b'%PDF-1.4\n%EOF',
            content_type='application/pdf',
        )
        self.assertIsNone(validate_ppe_pdf_upload(f))
        self.assertEqual(f.tell(), 0)

    def test_rejects_wrong_extension(self):
        f = SimpleUploadedFile(
            'x.html',
            b'%PDF-1.4\n',
            content_type='text/html',
        )
        self.assertIsNotNone(validate_ppe_pdf_upload(f))

    def test_rejects_spoofed_extension(self):
        f = SimpleUploadedFile(
            'mal.pdf',
            b'<html><script>alert(1)</script>',
            content_type='application/pdf',
        )
        self.assertIsNotNone(validate_ppe_pdf_upload(f))
