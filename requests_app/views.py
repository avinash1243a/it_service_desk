
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404

from .forms import ServiceRequestForm, AssignmentForm, CommentForm
from .models import ServiceRequest, RequestHistory
from .services import (
    assign_request,
    change_status,
    change_priority,
    create_follow_up_request,
)

User = get_user_model()


@login_required
def dashboard(request):
    if request.user.is_staff:
        service_requests = ServiceRequest.objects.select_related(
            "category", "sla", "requester", "assigned_to"
        ).all()
    else:
        service_requests = ServiceRequest.objects.select_related(
            "category", "sla", "requester", "assigned_to"
        ).filter(requester=request.user)

    context = {
        "service_requests": service_requests,
        "total_requests": service_requests.count(),
        "open_requests": service_requests.filter(
            status__in=["open", "assigned", "in_progress"]
        ).count(),
        "resolved_requests": service_requests.filter(
            status="resolved"
        ).count(),
        "overdue_requests": [
            item for item in service_requests
            if item.sla_state == "overdue"
        ],
    }
    return render(request, "dashboard.html", context)


@login_required
def create_request(request):
    if request.method == "POST":
        form = ServiceRequestForm(request.POST)

        if form.is_valid():
            service_request = form.save(commit=False)
            service_request.requester = request.user
            service_request.save()

            RequestHistory.objects.create(
                service_request=service_request,
                performed_by=request.user,
                action="created",
                details="Service request created",
            )

            messages.success(
                request,
                f"Service request SR-{service_request.pk} created successfully.",
            )
            return redirect("dashboard")
    else:
        form = ServiceRequestForm()

    return render(request, "create_request.html", {"form": form})


@login_required
def request_detail(request, pk):
    service_request = get_object_or_404(
        ServiceRequest.objects.select_related(
            "category", "sla", "requester", "assigned_to"
        ).prefetch_related("comments", "history"),
        pk=pk,
    )

    if (
        not request.user.is_staff
        and service_request.requester != request.user
        and service_request.assigned_to != request.user
    ):
        messages.error(
            request,
            "You do not have permission to view this request.",
        )
        return redirect("dashboard")

    assignment_form = AssignmentForm()
    comment_form = CommentForm()

    return render(
        request,
        "request_detail.html",
        {
            "service_request": service_request,
            "assignment_form": assignment_form,
            "comment_form": comment_form,
        },
    )


@login_required
def assign_request_view(request, pk):
    if not request.user.is_staff:
        messages.error(request, "Only IT staff can assign requests.")
        return redirect("dashboard")

    service_request = get_object_or_404(ServiceRequest, pk=pk)

    if request.method == "POST":
        form = AssignmentForm(request.POST)

        if form.is_valid():
            try:
                assign_request(
                    service_request,
                    form.cleaned_data["assignee"],
                    request.user,
                )
                messages.success(request, "Request assigned successfully.")
            except ValidationError as error:
                messages.error(request, " ".join(error.messages))
        else:
            messages.error(request, "Please select a valid IT team member.")

    return redirect("request_detail", pk=pk)


@login_required
def change_request_status(request, pk):
    service_request = get_object_or_404(ServiceRequest, pk=pk)

    if not request.user.is_staff:
        messages.error(request, "Only IT staff can change request status.")
        return redirect("dashboard")

    if request.method == "POST":
        new_status = request.POST.get("status", "")
        details = request.POST.get("details", "")

        try:
            change_status(
                service_request,
                new_status,
                request.user,
                details,
            )
            messages.success(request, "Request status updated successfully.")
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))

    return redirect("request_detail", pk=pk)


@login_required
def add_comment(request, pk):
    service_request = get_object_or_404(ServiceRequest, pk=pk)

    if (
        not request.user.is_staff
        and service_request.requester != request.user
        and service_request.assigned_to != request.user
    ):
        messages.error(request, "You cannot comment on this request.")
        return redirect("dashboard")

    if request.method == "POST":
        form = CommentForm(request.POST)

        if form.is_valid():
            comment = form.save(commit=False)
            comment.service_request = service_request
            comment.author = request.user
            comment.save()

            RequestHistory.objects.create(
                service_request=service_request,
                performed_by=request.user,
                action="comment_added",
                details="A comment was added.",
            )

            messages.success(request, "Comment added successfully.")

    return redirect("request_detail", pk=pk)

@login_required
def change_request_priority(request, pk):
    if not request.user.is_staff:
        messages.error(request, "Only IT staff can change request priority.")
        return redirect("dashboard")

    service_request = get_object_or_404(ServiceRequest, pk=pk)

    if request.method == "POST":
        new_priority = request.POST.get("priority", "")

        try:
            change_priority(service_request, new_priority, request.user)
            messages.success(
                request,
                "Request priority and SLA deadline updated successfully.",
            )
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))

    return redirect("request_detail", pk=pk)

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect

@login_required
def reopen_as_new_ticket(request, pk):
    if request.method != "POST":
        return redirect("dashboard")

    if not request.user.is_superuser:
        raise PermissionDenied("Only the admin can reopen a closed request.")

    original_ticket = get_object_or_404(
        ServiceRequest,
        pk=pk,
        status="closed",
    )

    new_ticket = create_follow_up_request(
        original_ticket,
        request.user,
    )

    messages.success(
        request,
        f"New ticket #{new_ticket.pk} created from closed ticket #{original_ticket.pk}.",
    )

    return redirect("request_detail", pk=new_ticket.pk)
