"""
Who may see or change a rack, and everything that hangs off it (patches, runs, exports).

Users own their racks. A rack is readable by its owner, by admin read roles, or by
anyone when it is public; only the owner may change it. A rack the caller cannot read
answers 404 so its existence is not revealed; a readable rack the caller does not own
answers 403 on a write.
"""

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Query, Session

from admin.dependencies import READ_ROLES
from community.models import User

from .models import Rack


def can_read(rack: Rack, user: Optional[User]) -> bool:
    if rack.is_public:
        return True
    return user is not None and (user.id == rack.user_id or user.role in READ_ROLES)


def can_write(rack: Rack, user: Optional[User]) -> bool:
    return user is not None and user.id == rack.user_id


def readable_rack(db: Session, rack_id: int, user: Optional[User], *, label: str = "Rack") -> Rack:
    rack = db.query(Rack).filter(Rack.id == rack_id).first()
    if rack is None or not can_read(rack, user):
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return rack


def owned_rack(db: Session, rack_id: int, user: Optional[User], *, label: str = "Rack") -> Rack:
    rack = readable_rack(db, rack_id, user, label=label)
    if not can_write(rack, user):
        raise HTTPException(status_code=403, detail=f"Only the owner can change this {label.lower()}")
    return rack


def private_rack(db: Session, rack_id: int, user: Optional[User], *, label: str = "Rack") -> Rack:
    """Evidence (photos, candidates, inventory) is private even on a public rack: only
    the owner and admin read roles may see it."""
    rack = db.query(Rack).filter(Rack.id == rack_id).first()
    if rack is None or user is None or not (user.id == rack.user_id or user.role in READ_ROLES):
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return rack


def owned_private_rack(db: Session, rack_id: int, user: Optional[User], *, label: str = "Rack") -> Rack:
    """Only the owner may add, confirm, resolve or delete a rack's evidence."""
    rack = private_rack(db, rack_id, user, label=label)
    if not can_write(rack, user):
        raise HTTPException(status_code=403, detail=f"Only the owner can change this {label.lower()}")
    return rack


def readable_racks(query: Query, user: Optional[User]) -> Query:
    """Restrict a query over Rack to the racks the caller may read."""
    if user is not None and user.role in READ_ROLES:
        return query
    if user is None:
        return query.filter(Rack.is_public.is_(True))
    return query.filter(or_(Rack.is_public.is_(True), Rack.user_id == user.id))


def readable_patch(db: Session, patch_id: int, user: Optional[User]):
    """A patch is readable when it is public or its rack is readable."""
    from patches.models import Patch

    patch = db.query(Patch).filter(Patch.id == patch_id).first()
    rack = db.query(Rack).filter(Rack.id == patch.rack_id).first() if patch else None
    if patch is None or rack is None or not (patch.is_public or can_read(rack, user)):
        raise HTTPException(status_code=404, detail="Patch not found")
    return patch


def owned_patch(db: Session, patch_id: int, user: Optional[User]):
    """Only the owner of a patch's rack may change the patch."""
    patch = readable_patch(db, patch_id, user)
    rack = db.query(Rack).filter(Rack.id == patch.rack_id).first()
    if not can_write(rack, user):
        raise HTTPException(status_code=403, detail="Only the owner can change this patch")
    return patch


def readable_patches(query: Query, user: Optional[User]) -> Query:
    """Restrict a query over Patch to public patches and patches on readable racks."""
    from patches.models import Patch

    if user is not None and user.role in READ_ROLES:
        return query
    visible_racks = readable_racks(Query(Rack.id), user).subquery()
    return query.filter(or_(Patch.is_public.is_(True), Patch.rack_id.in_(visible_racks.select())))
