from django import forms
from django.contrib.auth import get_user_model

from .models import (
    Category,
    SLAConfig,
    ServiceRequest,
    RequestComment,
)

User = get_user_model()


class ServiceRequestForm(forms.ModelForm):
    priority = forms.ChoiceField(
        choices=SLAConfig.PRIORITIES,
        label="Priority",
    )

    class Meta:
        model = ServiceRequest
        fields = [
            "title",
            "description",
            "category",
            "priority",
        ]
        widgets = {
            "description": forms.Textarea(
                attrs={"rows": 4}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = Category.objects.filter(
            is_active=True
        )

    def save(self, commit=True):
        instance = super().save(commit=False)
        priority = self.cleaned_data["priority"]

        instance.sla = SLAConfig.objects.get(
            priority=priority,
            is_active=True,
        )

        if commit:
            instance.save()

        return instance


class AssignmentForm(forms.Form):
    assignee = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by("username"),
        label="IT team member",
    )


class CommentForm(forms.ModelForm):
    class Meta:
        model = RequestComment
        fields = ["message"]
        widgets = {
            "message": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Add an update...",
                }
            )
        }