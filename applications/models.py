from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Common timestamp fields for auditing."""

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class JobSource(TimeStampedModel):
    name = models.CharField(max_length=128)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    homepage_url = models.URLField(blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    is_enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class JobPosting(TimeStampedModel):
    class Seniority(models.TextChoices):
        NEW_GRAD = "new_grad", "New Grad"
        INTERN = "intern", "Intern"
        OTHER = "other", "Other"

    source = models.ForeignKey(JobSource, on_delete=models.CASCADE, related_name="postings")
    external_id = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=255)
    company = models.CharField(max_length=255)
    locations = models.CharField(max_length=512, blank=True)
    is_remote = models.BooleanField(default=False)
    seniority = models.CharField(
        max_length=32, choices=Seniority.choices, default=Seniority.NEW_GRAD
    )
    application_url = models.URLField(blank=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    posted_at = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["company", "title"]
        unique_together = ("source", "external_id")

    def __str__(self) -> str:
        return f"{self.company} – {self.title}"


class ResumeVariant(TimeStampedModel):
    job_posting = models.ForeignKey(
        JobPosting, on_delete=models.CASCADE, related_name="resume_variants"
    )
    headline = models.CharField(max_length=255, blank=True)
    summary = models.TextField(blank=True)
    file_path = models.CharField(max_length=512, blank=True)

    def __str__(self) -> str:
        return f"Resume for {self.job_posting}"


class Application(TimeStampedModel):
    class Status(models.TextChoices):
        TODO = "todo", "To Do"
        IN_PROGRESS = "in_progress", "In Progress"
        SUBMITTED = "submitted", "Submitted"
        INTERVIEW = "interview", "Interview"
        REJECTED = "rejected", "Rejected"

    job_posting = models.OneToOneField(
        JobPosting, on_delete=models.CASCADE, related_name="application"
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.TODO)
    applied_on = models.DateField(null=True, blank=True)
    cover_letter = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    auto_applied = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Application for {self.job_posting}"


class ApplicationChecklistItem(TimeStampedModel):
    application = models.ForeignKey(
        Application, on_delete=models.CASCADE, related_name="checklist_items"
    )
    label = models.CharField(max_length=255)
    is_completed = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "label"]

    def __str__(self) -> str:
        return f"{self.label} ({'done' if self.is_completed else 'todo'})"

# Create your models here.
