from __future__ import annotations

import logging
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Optional

from django.conf import settings
from django.utils import timezone

from applications.models import Application, AutoApplyAttempt

logger = logging.getLogger(__name__)


class AutoApplySafetyError(RuntimeError):
    """Raised when automation is blocked by safeguards."""


@dataclass(slots=True)
class AutoApplyResult:
    attempt: AutoApplyAttempt
    success: bool
    notes: str


def run_auto_apply(
    application: Application,
    *,
    acknowledge_risk: bool,
    headless: bool = True,
) -> AutoApplyResult:
    attempt = AutoApplyAttempt.objects.create(
        application=application,
        safeguard_acknowledged=acknowledge_risk,
    )

    if not acknowledge_risk:
        attempt.status = AutoApplyAttempt.Status.SKIPPED
        attempt.details = "User did not acknowledge automation safeguards."
        attempt.completed_at = timezone.now()
        attempt.save(update_fields=["status", "details", "completed_at"])
        raise AutoApplySafetyError(attempt.details)

    if not settings.AUTO_APPLY_ENABLED:
        attempt.status = AutoApplyAttempt.Status.SKIPPED
        attempt.details = "AUTO_APPLY_ENABLED is false. Enable in environment to proceed."
        attempt.completed_at = timezone.now()
        attempt.save(update_fields=["status", "details", "completed_at"])
        raise AutoApplySafetyError(attempt.details)

    if not application.job_posting.application_url:
        attempt.status = AutoApplyAttempt.Status.SKIPPED
        attempt.details = "Job posting missing application URL."
        attempt.completed_at = timezone.now()
        attempt.save(update_fields=["status", "details", "completed_at"])
        raise AutoApplySafetyError(attempt.details)

    attempt.status = AutoApplyAttempt.Status.RUNNING
    attempt.started_at = timezone.now()
    attempt.save(update_fields=["status", "started_at"])

    notes = ""
    try:
        with _webdriver(headless=headless) as driver:
            driver.get(application.job_posting.application_url)
            notes = (
                "Opened application portal in automated browser session. "
                "Further scripted steps should be implemented per company workflow."
            )

        attempt.status = AutoApplyAttempt.Status.SUCCESS
        attempt.details = notes
        attempt.completed_at = timezone.now()
        attempt.save(update_fields=["status", "details", "completed_at"])

        application.auto_applied = True
        application.save(update_fields=["auto_applied"])
        return AutoApplyResult(attempt=attempt, success=True, notes=notes)
    except Exception as exc:  # pragma: no cover - requires Selenium runtime
        logger.exception("Auto-apply failed for application_id=%s", application.id)
        attempt.status = AutoApplyAttempt.Status.FAILED
        attempt.details = str(exc)
        attempt.completed_at = timezone.now()
        attempt.save(update_fields=["status", "details", "completed_at"])
        raise


@contextmanager
def _webdriver(*, headless: bool) -> Iterator["webdriver.Remote"]:
    """
    Create a webdriver session using either a remote endpoint or webdriver-manager.
    """
    from selenium import webdriver

    driver: Optional["webdriver.Remote"] = None
    try:
        if settings.WEBDRIVER_REMOTE_URL:
            options = _build_chrome_options(headless=headless)
            driver = webdriver.Remote(
                command_executor=settings.WEBDRIVER_REMOTE_URL,
                options=options,
            )
        else:
            driver = _build_local_driver(headless=headless)
        yield driver
    finally:
        if driver:
            driver.quit()


def _build_chrome_options(*, headless: bool):
    from selenium.webdriver import ChromeOptions

    options = ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    options.add_argument("--window-size=1280,720")
    return options


def _build_local_driver(*, headless: bool):
    from selenium import webdriver

    driver_choice = settings.AUTO_APPLY_DRIVER.lower()
    if driver_choice not in {"chromium", "chrome", "firefox"}:
        logger.warning("Unsupported AUTO_APPLY_DRIVER=%s; defaulting to chromium.", driver_choice)
        driver_choice = "chromium"

    if driver_choice in {"chromium", "chrome"}:
        from selenium.webdriver.chrome.service import Service
        from webdriver_manager.chrome import ChromeDriverManager

        options = _build_chrome_options(headless=headless)
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=options)

    from selenium.webdriver.firefox.options import Options as FirefoxOptions
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from webdriver_manager.firefox import GeckoDriverManager

    options = FirefoxOptions()
    if headless:
        options.add_argument("--headless")
    service = FirefoxService(GeckoDriverManager().install())
    return webdriver.Firefox(service=service, options=options)
