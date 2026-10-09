
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()


class ServiceDeskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            password="TestPassword123!",
        )

    def test_dashboard_redirects_anonymous_user_to_login(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_logged_in_user_can_open_dashboard(self):
        self.client.login(
            username="testuser",
            password="TestPassword123!",
        )

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Category, SLAConfig, ServiceRequest
from .services import change_status, calculate_sla_deadline


class BusinessLogicTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="requester",
            password="TestPassword123!",
        )

        self.category = Category.objects.create(
            name="Test Software",
            description="Test category",
        )

        self.sla = SLAConfig.objects.create(
            priority="low",
            resolution_hours=72,
            warning_percent=80,
            is_active=True,
        )

        self.ticket = ServiceRequest.objects.create(
            title="Test request",
            description="Testing business logic",
            category=self.category,
            sla=self.sla,
            requester=self.user,
        )

    def test_sla_deadline_uses_creation_time(self):
        expected = self.ticket.created_at + timedelta(hours=72)

        self.assertEqual(
            calculate_sla_deadline(self.ticket),
            expected,
        )

    def test_resolution_requires_details(self):
        self.ticket.status = "in_progress"
        self.ticket.save()

        with self.assertRaises(ValidationError):
            change_status(
                self.ticket,
                "resolved",
                self.user,
                "",
            )

    def test_reopening_clears_resolved_timestamp(self):
        self.ticket.status = "resolved"
        self.ticket.resolved_at = timezone.now()
        self.ticket.save()

        change_status(
            self.ticket,
            "in_progress",
            self.user,
        )

        self.ticket.refresh_from_db()

        self.assertEqual(self.ticket.status, "in_progress")
        self.assertIsNone(self.ticket.resolved_at)

    def test_invalid_transition_is_rejected(self):
        with self.assertRaises(ValidationError):
            change_status(
                self.ticket,
                "closed",
                self.user,
            )
