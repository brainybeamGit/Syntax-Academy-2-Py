from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AdminPanelTests(TestCase):
    def setUp(self):
        self.admin_user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@admin.com",
            password="admin",
        )

    def test_admin_login_page_loads(self):
        response = self.client.get(reverse("admin_login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Admin Login")

    def test_admin_login_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("admin_login"),
            {"username": "admin", "password": "admin"},
        )

        self.assertRedirects(response, reverse("dashboard_home"))
