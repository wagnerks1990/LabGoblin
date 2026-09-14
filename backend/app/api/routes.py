from fastapi import APIRouter

from app.api.routers.console import router as console_router
from app.api.routers.sessions import router as sessions_router
from app.api.routers.console_ws import router as console_ws_router
from app.api.routers.admin_telemetry import router as telemetry_router
from app.api.routers.admin_events import router as admin_events_router
from app.api.routers.pools import router as pools_router
from app.api.routers.admin_troubleshooting import router as troubleshooting_router
from app.api.routers.admin_operations import router as operations_router
from app.api.routers.workers import router as workers_router
from app.api.routers.vms import router as vms_router
from app.api.routers.audit import router as audit_router
from app.api.routers.templates import router as templates_router
from app.api.routers.health import router as health_router
from app.api.routers.auth import router as auth_router
from app.api.routers.admin_validation import router as validation_router
from app.api.routers.admin_runtime import router as runtime_router
from app.api.routers.admin_reconciliation import router as reconciliation_router
from app.api.routers.admin_analytics import router as analytics_router
from app.api.routers.admin_proxmox_setup import router as proxmox_setup_router
from app.api.routers.admin_users import router as admin_users_router
from app.api.routers.admin_groups import router as admin_groups_router
from app.api.routers.admin_dashboard import router as admin_dashboard_router
from app.api.routers.proxmox_assets import router as proxmox_assets_router
from app.api.routers.classes_labs import router as classes_labs_router
from app.api.routers.admin_organizations import router as admin_organizations_router
from app.api.routers.admin_updates import router as admin_updates_router
from app.api.routers.organizations import router as organizations_router
from app.api.routers.classroom import router as classroom_router

from app.api.routers.lab_setup import router as lab_setup_router

router = APIRouter(prefix="/api")
router.include_router(lab_setup_router)

router.include_router(auth_router)
router.include_router(health_router)
router.include_router(templates_router)
router.include_router(audit_router)
router.include_router(vms_router)
router.include_router(console_router)
router.include_router(sessions_router)
router.include_router(console_ws_router)
router.include_router(telemetry_router)
router.include_router(admin_events_router)
router.include_router(pools_router)
router.include_router(workers_router)
router.include_router(operations_router)
router.include_router(troubleshooting_router)
router.include_router(runtime_router)
router.include_router(validation_router)
router.include_router(reconciliation_router)

router.include_router(analytics_router)
router.include_router(proxmox_setup_router)
router.include_router(admin_users_router)
router.include_router(admin_groups_router)
router.include_router(admin_dashboard_router)
router.include_router(proxmox_assets_router)
router.include_router(classes_labs_router)
router.include_router(admin_organizations_router)
router.include_router(admin_updates_router)
router.include_router(organizations_router)
router.include_router(classroom_router)
