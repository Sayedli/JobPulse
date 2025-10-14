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
]
