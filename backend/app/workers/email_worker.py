from app.db.session import SessionLocal
from app.services.email_notifications import queue_notices
from app.services.email_service import expire_content, get_settings, process_queue
from app.services.worker_run_service import WorkerRunService
from app.workers.locks import acquire_worker_lock, release_worker_lock


def run_once():
    if not acquire_worker_lock("email"):
        return
    db = SessionLocal()
    try:
        config = get_settings(db)
        if not config.enabled:
            expire_content(db)
            return
        service = WorkerRunService(db)
        run_id = service.start("email").id
        try:
            queue_notices(db, config)
            summary = process_queue(db)
            service.finish(run_id, "success", summary)
        except Exception:
            db.rollback()
            service.finish(
                run_id,
                "failed",
                error="Email processing failed; inspect email delivery status.",
            )
    finally:
        db.close()
        release_worker_lock("email")
