from django import forms

from applications.models import Application


class ApplicationStatusForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ["status", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Add notes or follow-up reminders..."}),
        }


class ResumeTailorForm(forms.Form):
    base_resume_text = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 6}),
        required=False,
        label="Base Resume Text",
        help_text="Optional override. Leave empty to use the default resume template.",
    )


class CoverLetterForm(forms.Form):
    applicant_name = forms.CharField(max_length=128)
    strengths = forms.CharField(
        help_text="Comma separated strengths or experiences to highlight.",
    )
    tone = forms.ChoiceField(
        choices=[("enthusiastic", "Enthusiastic"), ("formal", "Formal")],
        initial="enthusiastic",
    )
    extra_notes = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3}), label="Extra Notes"
    )
