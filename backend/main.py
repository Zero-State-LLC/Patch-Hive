"""
PatchHive Backend API
Main FastAPI application entry point.
"""

from contextlib import asynccontextmanager

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from account.models import CreditLedgerEntry, ExportRecord  # noqa: F401
from admin.models import AdminAuditLog, PendingFunction  # noqa: F401
from cases.models import Case  # noqa: F401
from canon.models import (  # noqa: F401
    ArtifactManifestRecord,
    CanonicalAdminAuditEventRecord,
    CanonicalCreditLedgerEntryRecord,
    CanonicalExportRecord,
    GeneratedPatchRecord,
    GenerationJobRecord,
    GenerationRunRecord,
    ModuleRevisionRecord,
    PatchLibraryRecord,
    RigRevisionRecord,
    StageReceiptRecord,
    StripeEventRecordModel,
    UserPatchAnnotationRecord,
)
from community.models import Comment, User, Vote  # noqa: F401
from core import get_db, init_db, settings
from gallery.models import GalleryRevision  # noqa: F401
from intelligence.models import DecisionReceiptRecord  # noqa: F401
from modules.catalog import ModuleCatalog  # noqa: F401

# Import all models to register them with SQLAlchemy before init_db()
from modules.models import Module  # noqa: F401
from monetization.models import CreditsLedger, Export, License, Referral  # noqa: F401
from patches.models import Patch  # noqa: F401
from publishing.models import Publication, PublicationReport  # noqa: F401
from racks.models import Rack, RackModule  # noqa: F401
from runs.models import Run  # noqa: F401
from registry.models import (  # noqa: F401
    Capability,
    Control,
    DeviceFamily,
    DeviceModel,
    DeviceRevision,
    Manufacturer,
    Port,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    from canon.routes import validate_payment_startup_policy

    validate_payment_startup_policy(settings)
    print(f"Starting {settings.app_name} v{settings.app_version}")
    print(f"ABX-Core version: {settings.abx_core_version}")
    # Schema: alembic upgrade head (entrypoint / release job). create_all only if explicitly allowed.
    if settings.allow_create_all:
        print("ALLOW_CREATE_ALL=true — calling init_db() (dev/test escape hatch only)")
        init_db()
    yield
    # Shutdown
    print(f"Shutting down {settings.app_name}")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Eurorack system design and patch exploration platform",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoints
@app.get("/health")
async def health_check():
    """Liveness: process is up (no dependency probe)."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "abx_core_version": settings.abx_core_version,
    }


@app.get("/health/ready")
async def health_ready(db: Annotated[Session, Depends(get_db)]):
    """Readiness: process + database connectivity (uses get_db for test overrides)."""
    payload = {
        "status": "healthy",
        "app": settings.app_name,
        "version": settings.app_version,
        "abx_core_version": settings.abx_core_version,
        "database": "ok",
    }
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 — surface any DB connectivity failure
        payload["status"] = "unavailable"
        payload["database"] = "error"
        payload["detail"] = type(exc).__name__
        return JSONResponse(status_code=503, content=payload)
    return payload


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "description": "Eurorack system design and patch exploration platform",
        "docs_url": "/docs",
        "abx_core_version": settings.abx_core_version,
        "seed_enforcement": settings.enforce_seed_traceability,
    }


from account.routes import router as account_router  # noqa: E402
from admin.routes import router as admin_router  # noqa: E402
from cases.catalog_routes import router as case_catalog_router  # noqa: E402
from cases.routes import router as cases_router  # noqa: E402
from export.routes import router as export_router  # noqa: E402
from integrations.router import (  # noqa: E402
    router as integrations_router,
    synth_catalog_router,
)
from modules.catalog_routes import router as catalog_router  # noqa: E402

# Import and register routers  # noqa: E402
from modules.routes import router as modules_router  # noqa: E402
from monetization.routes import router as monetization_router  # noqa: E402
from patches.routes import router as patches_router  # noqa: E402
from racks.routes import router as racks_router  # noqa: E402
from racks.recommendation.routes import router as rack_recommendation_router  # noqa: E402
from runs.routes import router as runs_router  # noqa: E402

from canon.routes import router as canon_router  # noqa: E402
from community.auth_routes import router as auth_router  # noqa: E402
from evidence.routes import router as evidence_router  # noqa: E402
from registry.routes import router as registry_router  # noqa: E402

app.include_router(catalog_router, prefix="/api/modules", tags=["catalog"])
app.include_router(modules_router, prefix="/api/modules", tags=["modules"])
# Catalog static paths (/catalog, /catalog/stats, …) before legacy /{case_id}.
app.include_router(case_catalog_router, prefix="/api/cases")
app.include_router(cases_router, prefix="/api/cases", tags=["cases"])
app.include_router(racks_router, prefix="/api/racks", tags=["racks"])
app.include_router(rack_recommendation_router, prefix="/api/racks", tags=["racks"])
app.include_router(patches_router, prefix="/api/patches", tags=["patches"])
app.include_router(runs_router, prefix="/api/runs", tags=["runs"])
app.include_router(export_router, prefix="/api/export", tags=["export"])
app.include_router(canon_router, prefix="/api/canon", tags=["canon"])
app.include_router(evidence_router, prefix="/api", tags=["evidence"])
app.include_router(registry_router, prefix="/api/registry", tags=["registry"])
app.include_router(integrations_router, prefix="/api", tags=["integrations"])
app.include_router(synth_catalog_router, prefix="/api", tags=["synth-catalog"])
app.include_router(monetization_router, prefix="/api/monetization", tags=["monetization"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
app.include_router(account_router, prefix="/api/me", tags=["account"])
# Auth stays available regardless of legacy-social flags.
app.include_router(auth_router, prefix="/api/community", tags=["auth"])

if settings.enable_legacy_social:
    from community.routes import router as community_router

    app.include_router(community_router, prefix="/api/community", tags=["legacy-social"])

if settings.enable_legacy_publishing:
    from publishing.routes import router as publishing_router

    app.include_router(publishing_router, prefix="/api", tags=["legacy-publishing"])

if settings.enable_legacy_leaderboards:
    from leaderboards.routes import router as leaderboards_router

    app.include_router(
        leaderboards_router, prefix="/api/leaderboards", tags=["legacy-leaderboards"]
    )
