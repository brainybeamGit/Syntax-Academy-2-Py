from django.test import TestCase
from django.urls import reverse

from .models import Course, Lessons, Payment, Registration


class AppViewTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(
            name="Python Foundations",
            description="Learn Python from scratch.",
            level="beginner",
            duration_weeks=4,
            price=999,
            is_featured=True,
            thumbnail="courses/Picsart_26-03-31_16-17-15-176.png",
        )
        self.user = Registration.objects.create(
            name="Demo Learner",
            email="demo@example.com",
            mobile=9876543210,
            password="admin123!",
            level="beginner",
        )
        self.lesson = Lessons.objects.create(
            name="Introduction",
            course=self.course,
            video="videos/python1.mp4",
        )

    def test_index_page_loads(self):
        response = self.client.get(reverse("index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Python Foundations")

    def test_login_sets_session_metadata(self):
        response = self.client.post(
            reverse("login"),
            {"email": self.user.email, "password": self.user.password},
        )

        self.assertRedirects(response, reverse("index"))
        self.assertEqual(self.client.session["login"], self.user.email)
        self.assertEqual(self.client.session["user_name"], self.user.name)
        self.assertEqual(self.client.session["user_id"], self.user.id)

    def test_mark_lesson_complete_requires_login(self):
        response = self.client.post(reverse("mark_lesson_complete", args=[self.lesson.id]))

        self.assertEqual(response.status_code, 401)

    def test_submit_quiz_rejects_get_requests(self):
        response = self.client.get(reverse("submit_quiz", args=[self.course.id]))

        self.assertEqual(response.status_code, 405)

    def test_download_receipt_requires_authenticated_owner(self):
        payment = Payment.objects.create(
            user=self.user,
            course=self.course,
            amount=self.course.price,
            razorpay_payment_id="pay_demo",
            razorpay_order_id="order_demo",
        )

        response = self.client.get(reverse("download_receipt", args=[payment.id]))

        self.assertRedirects(response, reverse("login"))

    def test_download_receipt_is_limited_to_payment_owner(self):
        other_user = Registration.objects.create(
            name="Other Learner",
            email="other@example.com",
            mobile=9123456780,
            password="admin123!",
            level="beginner",
        )
        payment = Payment.objects.create(
            user=self.user,
            course=self.course,
            amount=self.course.price,
            razorpay_payment_id="pay_demo_2",
            razorpay_order_id="order_demo_2",
        )

        session = self.client.session
        session["login"] = other_user.email
        session["user_id"] = other_user.id
        session.save()

        response = self.client.get(reverse("download_receipt", args=[payment.id]))

        self.assertEqual(response.status_code, 404)
