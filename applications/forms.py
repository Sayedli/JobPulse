from django import forms

from applications.models import Application, UserProfile


class ApplicationStatusForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = ["status", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Add notes or follow-up reminders..."}),
        }


class ResumeTailorForm(forms.Form):
    resume_pdf = forms.FileField(
        label="Resume PDF",
        help_text="Upload a PDF version of your resume (max 5 MB).",
        widget=forms.ClearableFileInput(attrs={"accept": "application/pdf"}),
    )

    def clean_resume_pdf(self):
        file = self.cleaned_data["resume_pdf"]
        valid_types = {"application/pdf", "application/x-pdf"}
        if file.content_type not in valid_types and not file.name.lower().endswith(".pdf"):
            raise forms.ValidationError("Please upload a valid PDF file.")
        if file.size > 5 * 1024 * 1024:
            raise forms.ValidationError("PDF file must be smaller than 5 MB.")
        return file


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


class AutoApplyConsentForm(forms.Form):
    acknowledge_risk = forms.BooleanField(
        label="I understand that automated applications may violate terms of service.",
        help_text="Ensure you review the application portal after automation runs.",
    )


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["display_name", "resume_base_text", "cover_letter_signature"]
        widgets = {
            "resume_base_text": forms.Textarea(attrs={"rows": 8}),
            "cover_letter_signature": forms.TextInput(attrs={"placeholder": "Your Name"}),
        }
        labels = {
            "display_name": "Display name",
            "resume_base_text": "Fallback resume text (optional)",
            "cover_letter_signature": "Cover letter signature",
        }
        help_texts = {
            "resume_base_text": "Used only if no PDF is provided during tailoring.",
        }
