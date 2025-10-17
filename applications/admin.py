from django.contrib import admin

from .models import (
    Application,
    ApplicationChecklistItem,
    AutoApplyAttempt,
    CoverLetterVariant,
    JobDescriptionSnapshot,
    JobPosting,
    JobSource,
    ResumeVariant,
    UserProfile,
)


@admin.register(JobSource)
class JobSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_enabled", "last_synced_at", "updated_at")
    list_filter = ("is_enabled",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(JobPosting)
class JobPostingAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "company",
        "seniority",
        "is_remote",
        "application_url",
        "source",
        "is_active",
    )
    list_filter = ("seniority", "is_remote", "is_active", "source")
    search_fields = ("title", "company", "locations")


class ApplicationChecklistItemInline(admin.TabularInline):
    model = ApplicationChecklistItem
    extra = 0


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("job_posting", "user", "status", "applied_on", "auto_applied", "created_at")
    list_filter = ("status", "auto_applied", "user")
    search_fields = ("job_posting__title", "job_posting__company", "user__username")
    inlines = [ApplicationChecklistItemInline]


@admin.register(ResumeVariant)
class ResumeVariantAdmin(admin.ModelAdmin):
    list_display = ("job_posting", "user", "headline", "created_at")
    list_filter = ("user",)


@admin.register(CoverLetterVariant)
class CoverLetterVariantAdmin(admin.ModelAdmin):
    list_display = ("application", "user", "created_at")
    list_filter = ("user",)


@admin.register(AutoApplyAttempt)
class AutoApplyAttemptAdmin(admin.ModelAdmin):
    list_display = ("application", "status", "safeguard_acknowledged", "started_at", "completed_at")
    list_filter = ("status", "safeguard_acknowledged")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "display_name", "updated_at")


@admin.register(JobDescriptionSnapshot)
class JobDescriptionSnapshotAdmin(admin.ModelAdmin):
    list_display = ("job_posting", "fetched_at")
    search_fields = ("job_posting__title", "job_posting__company")

# Register your models here.
