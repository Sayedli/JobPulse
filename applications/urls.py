from django.urls import path

from applications import views

app_name = "applications"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("jobs/<int:pk>/apply/", views.create_application, name="create_application"),
    path(
        "applications/<int:pk>/status/",
        views.update_application_status,
        name="update_application_status",
    ),
    path(
        "applications/<int:pk>/tailor-resume/",
        views.tailor_resume_view,
        name="tailor_resume",
    ),
    path(
        "applications/<int:pk>/cover-letter/",
        views.generate_cover_letter_view,
        name="generate_cover_letter",
    ),
    path(
        "checklist/<int:pk>/toggle/",
        views.toggle_checklist_view,
        name="toggle_checklist_item",
    ),
    path(
        "applications/<int:pk>/auto-apply/",
        views.auto_apply_view,
        name="auto_apply",
    ),
    path("profile/", views.profile_settings, name="profile"),
    path(
        "resume-variants/<int:pk>/download/",
        views.download_resume_variant,
        name="download_resume_variant",
    ),
    path(
        "cover-letter-variants/<int:pk>/download/",
        views.download_cover_letter_variant,
        name="download_cover_letter_variant",
    ),
    path(
        "jobs/<int:pk>/description/",
        views.job_description_detail,
        name="job_description",
    ),
]
