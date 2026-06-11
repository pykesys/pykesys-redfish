import logging
import os

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class SchedulerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "scheduler"

    def ready(self):
        from django.conf import settings

        if not getattr(settings, "SCHEDULER_AUTOSTART", True):
            return

        # In Django's dev server, ready() is called twice; only start in the reloader process.
        if settings.DEBUG and os.environ.get("RUN_MAIN") != "true":
            return

        try:
            from apscheduler.schedulers.background import BackgroundScheduler
            from apscheduler.triggers.interval import IntervalTrigger
            from django_apscheduler.jobstores import DjangoJobStore

            scheduler = BackgroundScheduler()
            scheduler.add_jobstore(DjangoJobStore(), "default")
            scheduler.add_job(
                "scheduler.jobs:run_poll_cycle",
                trigger=IntervalTrigger(seconds=30),
                id="poll_fleet",
                name="Poll Redfish Fleet",
                replace_existing=True,
                misfire_grace_time=25,
            )
            scheduler.start()
            logger.info("APScheduler started — polling fleet every 30s")
        except Exception as exc:
            logger.error("Failed to start scheduler: %s", exc)
