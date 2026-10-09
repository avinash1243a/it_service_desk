
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from requests_app import views


urlpatterns = [
    path("admin/", admin.site.urls),

    path("", views.dashboard, name="dashboard"),
    path("requests/new/", views.create_request, name="create_request"),
    path("requests/<int:pk>/", views.request_detail, name="request_detail"),

    path(
        "requests/<int:pk>/assign/",
        views.assign_request_view,
        name="assign_request",
    ),
    path(
        "requests/<int:pk>/status/",
        views.change_request_status,
        name="change_request_status",
    ),
    path(
        "requests/<int:pk>/comment/",
        views.add_comment,
        name="add_comment",
    ),

    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html"
        ),
        name="login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
    path(
    "requests/<int:pk>/priority/",
    views.change_request_priority,
    name="change_request_priority",
    ),
    path(
    "requests/<int:pk>/reopen/",
    views.reopen_as_new_ticket,
    name="reopen_as_new_ticket",
),
]

