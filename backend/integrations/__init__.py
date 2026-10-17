"""External integrations for PatchHive.

Standalone integration CLIs can touch SQLAlchemy models that retain
string-based relationships across legacy and canonical domains. Register the
same model graph used by ``tests/conftest.py`` before an integration module
runs so mapper configuration is deterministic outside the FastAPI process.
"""

from account.models import CreditLedgerEntry, ExportRecord  # noqa: F401
from admin.models import AdminAuditLog, PendingFunction  # noqa: F401
from canon.models import (  # noqa: F401
    ArtifactManifestRecord,
    CanonicalAdminAuditEventRecord,
    CanonicalCreditLedgerEntryRecord,
    CanonicalExportRecord,
    ClassificationEvidenceRecord,
    GeneratedPatchRecord,
    GenerationJobRecord,
    GenerationRunRecord,
    ImageAssetRecord,
    ModuleRevisionRecord,
    PatchLibraryRecord,
    PatchUserOverlayRecord,
    RigRevisionRecord,
    StageReceiptRecord,
    StripeEventRecordModel,
    SystemInventoryRevisionRecord,
    UserPatchAnnotationRecord,
    UserStyleRecipeRecord,
)
from community.models import Comment, User, Vote  # noqa: F401
from gallery.models import GalleryRevision  # noqa: F401
from intelligence.models import DecisionReceiptRecord  # noqa: F401
from modules.models import Module  # noqa: F401
from monetization.models import CreditsLedger, Export, License, Referral  # noqa: F401
from patches.models import Patch  # noqa: F401
from publishing.models import Publication, PublicationReport  # noqa: F401
from racks.models import Rack, RackModule  # noqa: F401
from runs.models import Run  # noqa: F401

__all__: list[str] = []
