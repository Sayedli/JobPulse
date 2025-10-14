from __future__ import annotations

from typing import Iterable, Sequence

from applications.models import Application, ApplicationChecklistItem

DEFAULT_CHECKLIST = [
    "Review job description",
    "Tailor resume",
    "Draft cover letter",
    "Submit application",
    "Log follow-up date",
]


def ensure_default_checklist(application: Application) -> Sequence[ApplicationChecklistItem]:
    if application.checklist_items.exists():
        return list(application.checklist_items.all())

    items = [
        ApplicationChecklistItem(application=application, label=label, order=index)
        for index, label in enumerate(DEFAULT_CHECKLIST)
    ]
    ApplicationChecklistItem.objects.bulk_create(items)
    return list(application.checklist_items.all())


def toggle_checklist_item(item: ApplicationChecklistItem) -> ApplicationChecklistItem:
    item.is_completed = not item.is_completed
    item.save(update_fields=["is_completed"])
    return item
