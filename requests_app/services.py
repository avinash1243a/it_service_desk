
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import RequestHistory, ServiceRequest


ALLOWED_TRANSITIONS = {
    "open": ["assigned", "in_progress"],
    "assigned": ["in_progress"],
    "in_progress": ["resolved"],
    "resolved": ["in_progress", "closed"],
    "closed": ["in_progress"],
}



def record_event(ticket, actor, action, details=""):
    """Record an event in the request history."""
    return RequestHistory.objects.create(
        service_request=ticket,
        performed_by=actor,
        action=action,
        details=details,
    )


@transaction.atomic
def assign_request(ticket, assignee, actor):
    """Assign a request to an active staff member."""
    if ticket.status == "closed":
        raise ValidationError("A closed request cannot be reassigned.")

    old_assignee = (
        ticket.assigned_to.username
        if ticket.assigned_to
        else "Unassigned"
    )

    old_status = ticket.status
    ticket.assigned_to = assignee

    if ticket.status == "open":
        ticket.status = "assigned"

    ticket.save(update_fields=["assigned_to", "status", "updated_at"])

    new_assignee = assignee.username if assignee else "Unassigned"

    record_event(
        ticket,
        actor,
        "assignment_changed",
        f"Assignment changed from {old_assignee} to {new_assignee}.",
    )

    if old_status != ticket.status:
        record_event(
            ticket,
            actor,
            "status_changed",
            f"Status changed from {old_status} to {ticket.status}.",
        )

    return ticket


@transaction.atomic
def change_status(ticket, new_status, actor, details=""):
    """Validate and apply a request status transition."""
    
    if ticket.status == "closed":
        if not actor.is_superuser:
            raise ValueError(
                "Only the admin can reopen a closed request."
            )

        if new_status != "in_progress":
            raise ValueError(
                "A closed request can only be reopened as In Progress."
            )

    if new_status not in dict(ServiceRequest.STATUS_CHOICES):
        raise ValidationError("Invalid request status.")

    if new_status not in ALLOWED_TRANSITIONS.get(ticket.status, set()):
        raise ValidationError(
            f"Status cannot change from '{ticket.status}' to '{new_status}'."
        )

    if new_status == "resolved" and not details.strip():
        raise ValidationError("Resolution details are required.")

    old_status = ticket.status
    ticket.status = new_status

    update_fields = ["status", "updated_at"]

    if new_status == "resolved":
        ticket.resolved_at = timezone.now()
        update_fields.append("resolved_at")

    elif new_status == "closed":
        ticket.closed_at = timezone.now()
        update_fields.append("closed_at")

    elif old_status == "resolved" and new_status == "in_progress":
        ticket.resolved_at = None
        update_fields.append("resolved_at")

    ticket.save(update_fields=update_fields)

    record_event(
        ticket,
        actor,
        "status_changed",
        f"Status changed from {old_status} to {new_status}."
        + (f" Resolution details: {details.strip()}" if details.strip() else ""),
    )

    return ticket


def calculate_sla_deadline(ticket, priority=None):
    """Calculate a deadline from the request's original creation time."""
    if ticket.created_at is None:
        raise ValidationError(
            "Save the request before calculating its SLA deadline."
        )

    sla = ticket.sla

    if priority:
        from .models import SLAConfig

        try:
            sla = SLAConfig.objects.get(
                priority=priority,
                is_active=True,
            )
        except SLAConfig.DoesNotExist:
            raise ValidationError(
                "No active SLA configuration exists for that priority."
            )

    return ticket.created_at + timedelta(hours=sla.resolution_hours)

@transaction.atomic
def change_priority(ticket, new_priority, actor):
    """Change priority and recalculate the SLA deadline from creation time."""
    from .models import SLAConfig

    try:
        new_sla = SLAConfig.objects.get(
            priority=new_priority,
            is_active=True,
        )
    except SLAConfig.DoesNotExist:
        raise ValidationError(
            "No active SLA configuration exists for that priority."
        )

    if ticket.created_at is None:
        raise ValidationError(
            "The request must be saved before changing its priority."
        )

    old_priority = ticket.sla.priority
    old_deadline = ticket.sla_due_at

    ticket.sla = new_sla
    ticket.sla_due_at = ticket.created_at + timedelta(
        hours=new_sla.resolution_hours
    )
    ticket.save(update_fields=["sla", "sla_due_at", "updated_at"])

    record_event(
        ticket,
        actor,
        "priority_changed",
        (
            f"Priority changed from {old_priority} to {new_priority}. "
            f"Previous deadline: {old_deadline}; "
            f"new deadline: {ticket.sla_due_at}."
        ),
    )

    return ticket

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

@transaction.atomic
def create_follow_up_request(original_ticket, actor):
    """Create a new request linked to a closed original request."""

    if not actor.is_superuser:
        raise PermissionDenied("Only the admin can reopen a closed request.")

    if original_ticket.status != "closed":
        raise ValueError("Only closed requests can be reopened as new tickets.")

    new_ticket = ServiceRequest.objects.create(
        title=original_ticket.title,
        description=original_ticket.description,
        category=original_ticket.category,
        sla=original_ticket.sla,
        requester=original_ticket.requester,
        status="open",
        reopened_from=original_ticket,
    )

    # Calculate a fresh SLA deadline for the new request.
    if new_ticket.sla:
        new_ticket.sla_due_at = (
            new_ticket.created_at
            + timezone.timedelta(hours=new_ticket.sla.resolution_hours)
        )
        new_ticket.save(update_fields=["sla_due_at"])

    record_event(
        original_ticket,
        actor,
        "follow_up_created",
        f"Follow-up request #{new_ticket.pk} created.",
    )
    record_event(
        new_ticket,
        actor,
        "created_from_closed_request",
        f"Created from closed request #{original_ticket.pk}.",
    )

    return new_ticket
