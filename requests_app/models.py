from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


class SLAConfig(models.Model):
    PRIORITIES = [
        ("critical", "Critical"),
        ("high", "High"),
        ("medium", "Medium"),
        ("low", "Low"),
    ]

    priority = models.CharField(
        max_length=10,
        choices=PRIORITIES,
        unique=True,
    )
    resolution_hours = models.PositiveIntegerField()
    warning_percent = models.PositiveSmallIntegerField(default=80)
    is_active = models.BooleanField(default=True)

    def clean(self):
        super().clean()

        if self.resolution_hours is not None and self.resolution_hours <= 0:
            raise ValidationError({
                "resolution_hours": "Resolution hours must be greater than zero."
            })

        if not 1 <= self.warning_percent <= 99:
            raise ValidationError({
                "warning_percent": "Warning percent must be between 1 and 99."
            })

    class Meta:
        ordering = ["resolution_hours"]
        verbose_name = "SLA Configuration"
        verbose_name_plural = "SLA Configurations"

    def __str__(self):
        return f"{self.get_priority_display()} - {self.resolution_hours} hours"


class ServiceRequest(models.Model):
    reopened_from = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="follow_up_requests",
    )

    STATUS_CHOICES = [
        ("open", "Open"),
        ("assigned", "Assigned"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
        ("closed", "Closed"),
    ]
    title = models.CharField(max_length=200)
    description = models.TextField()

    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="service_requests",
    )

    sla = models.ForeignKey(
        SLAConfig,
        on_delete=models.PROTECT,
        related_name="service_requests",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="open",
        db_index=True,
    )

    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="service_requests",
    )

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_requests",
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    sla_due_at = models.DateTimeField(null=True, blank=True, db_index=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    @property
    def priority(self):
        return self.sla.priority

    @property
    def resolution_target_hours(self):
        return self.sla.resolution_hours

    @property
    def sla_state(self):
        if self.status in ("resolved", "closed"):
            return "completed"

        if self.sla_due_at is None:
            return "not_configured"

        now = timezone.now()

        if now >= self.sla_due_at:
            return "overdue"

        total_seconds = (
            self.sla_due_at - self.created_at
        ).total_seconds()

        if total_seconds <= 0:
            return "overdue"

        elapsed_seconds = (
            now - self.created_at
        ).total_seconds()

        warning_threshold = (
            self.sla.warning_percent / 100
        )

        if elapsed_seconds / total_seconds >= warning_threshold:
            return "warning"

        return "on_track"

    def save(self, *args, **kwargs):
        if self.sla_due_at is None and self.sla_id:
            start_time = self.created_at or timezone.now()
            self.sla_due_at = start_time + timedelta(
                hours=self.sla.resolution_hours
            )

        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["assigned_to", "status"]),
            models.Index(fields=["requester", "created_at"]),
        ]

    def __str__(self):
        return f"SR-{self.pk}: {self.title}"


class RequestComment(models.Model):
    service_request = models.ForeignKey(
        ServiceRequest,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="request_comments",
    )
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment on SR-{self.service_request_id}"


class RequestHistory(models.Model):
    service_request = models.ForeignKey(
        ServiceRequest,
        on_delete=models.CASCADE,
        related_name="history",
    )
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="request_history",
    )
    action = models.CharField(max_length=100)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Request history"

    def __str__(self):
        return f"SR-{self.service_request_id}: {self.action}"