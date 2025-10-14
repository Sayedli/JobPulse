from django.contrib import admin

from .models import (
    Application,
    ApplicationChecklistItem,
    JobPosting,
    JobSource,
    ResumeVariant,
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
    list_display = ("job_posting", "status", "applied_on", "auto_applied", "created_at")
    list_filter = ("status", "auto_applied")
    inlines = [ApplicationChecklistItemInline]


@admin.register(ResumeVariant)
class ResumeVariantAdmin(admin.ModelAdmin):
    list_display = ("job_posting", "headline", "created_at")

# Register your models here.
