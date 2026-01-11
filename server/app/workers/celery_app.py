"""Celery application configuration."""

from celery import Celery

from app.config import settings

# Create Celery app
celery_app = Celery(
    "trustmodel",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.workers.evaluation_tasks",
        "app.workers.trace_tasks",
    ],
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3300,  # Soft limit 55 minutes
    worker_prefetch_multiplier=1,  # Process one task at a time
    result_expires=86400,  # Results expire after 24 hours
    task_routes={
        "app.workers.evaluation_tasks.*": {"queue": "evaluations"},
        "app.workers.trace_tasks.*": {"queue": "traces"},
    },
    task_default_queue="default",
    task_queues={
        "default": {},
        "evaluations": {},
        "traces": {},
    },
)

# Configure beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "cleanup-expired-certificates": {
        "task": "app.workers.evaluation_tasks.cleanup_expired_certificates",
        "schedule": 86400.0,  # Every 24 hours
    },
    "aggregate-trace-metrics": {
        "task": "app.workers.trace_tasks.aggregate_trace_metrics",
        "schedule": 3600.0,  # Every hour
    },
}
