from django.contrib import admin
from .models import (
    Category,
    SLAConfig,
    ServiceRequest,
    RequestComment,
    RequestHistory,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    search_fields = ("name",)
    list_filter = ("is_active",)


@admin.register(SLAConfig)
class SLAConfigAdmin(admin.ModelAdmin):
    list_display = (
        "priority",
        "resolution_hours",
        "warning_percent",
        "is_active",
    )
    list_filter = ("priority", "is_active")
    list_editable = ("resolution_hours", "warning_percent", "is_active")


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "category",
        "priority",
        "status",
        "requester",
        "assigned_to",
        "created_at",
    )
    list_filter = ("status", "category", "sla")
    search_fields = ("title", "description", "requester__username")
    readonly_fields = ("created_at", "updated_at", "resolved_at")


@admin.register(RequestComment)
class RequestCommentAdmin(admin.ModelAdmin):
    list_display = ("service_request", "author", "created_at")
    search_fields = ("message", "author__username")


@admin.register(RequestHistory)
class RequestHistoryAdmin(admin.ModelAdmin):
    list_display = ("service_request", "action", "performed_by", "created_at")
    list_filter = ("action",)
    search_fields = ("action", "details")