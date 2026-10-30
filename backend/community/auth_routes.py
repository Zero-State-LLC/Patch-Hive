"""Always-on authentication and profile routes.

Legacy social surfaces (votes, comments, feed) stay behind ENABLE_LEGACY_SOCIAL.
Login, registration, and profile remain available in the default MVP surface.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from account.models import Referral
from account.services import ensure_referral_code
from core import get_db, get_password_hash, settings
from core.security import burn_password_check, verify_and_update_password
from monetization.referrals import create_referral, generate_referral_code

from . import login_guard, sessions
from .auth import require_auth
from .models import User
from .schemas import (
    LoginRequest,
    TokenResponse,
    UserCreate,
    PublicUserResponse,
    UserResponse,
    UserUpdate,
)

router = APIRouter()


@router.post("/users", response_model=UserResponse, status_code=201)
def register_user(user: UserCreate, http_request: Request, db: Session = Depends(get_db)):
    """Register a new user."""
    if not login_guard.allow_registration(login_guard.client_address(http_request)):
        raise HTTPException(status_code=429, detail="TOO_MANY_SIGNUPS")
    # One reply for a taken username or email, so sign-up does not reveal which emails
    # have accounts.
    taken = (
        db.query(User)
        .filter((User.username == user.username) | (User.email == user.email))
        .first()
    )
    if taken:
        raise HTTPException(status_code=400, detail="USERNAME_OR_EMAIL_TAKEN")

    referrer = None
    if settings.enable_referrals and user.referral_code:
        referrer = db.query(User).filter(User.referral_code == user.referral_code).first()
        if not referrer:
            raise HTTPException(status_code=400, detail="Invalid referral code")

    db_user = User(
        username=user.username,
        email=user.email,
        password_hash=get_password_hash(user.password),
        display_name=user.display_name or user.username,
        role="User",
        referral_code=generate_referral_code(db),
        referred_by=referrer.id if referrer else None,
        avatar_url=user.avatar_url,
        allow_public_avatar=user.allow_public_avatar,
        bio=user.bio,
    )
    db.add(db_user)
    db.flush()
    if referrer:
        try:
            create_referral(db, referrer=referrer, referred=db_user)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    db.refresh(db_user)

    ensure_referral_code(db, db_user)

    if settings.enable_referrals and user.referral_code:
        referrer = db.query(User).filter(User.referral_code == user.referral_code).first()
        if referrer and referrer.id != db_user.id:
            existing_referral = (
                db.query(Referral).filter(Referral.referred_user_id == db_user.id).first()
            )
            if not existing_referral:
                referral = Referral(
                    referrer_user_id=referrer.id,
                    referred_user_id=db_user.id,
                    status="pending",
                )
                db.add(referral)
                db.commit()

    return db_user


@router.post("/auth/login", response_model=TokenResponse)
def login(
    request: LoginRequest,
    http_request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Login and get access token.

    Every failure, whether an unknown name, a wrong password or a locked account,
    answers the same 401 after the same work, so none reveals that an account exists.
    """
    if not login_guard.allow_attempt(login_guard.client_address(http_request)):
        raise HTTPException(status_code=429, detail="Too many sign-in attempts; try again shortly")
    invalid = HTTPException(status_code=401, detail="Invalid credentials")
    user = db.query(User).filter(User.username == request.username).first()
    if user is None:
        burn_password_check(request.password)
        raise invalid
    if login_guard.is_locked(user):
        burn_password_check(request.password)
        raise invalid
    valid, new_hash = verify_and_update_password(request.password, user.password_hash)
    if not valid:
        login_guard.record_failure(db, user)
        db.commit()
        raise invalid
    login_guard.record_success(user)
    if new_hash:
        user.password_hash = new_hash  # upgrade a bcrypt or pbkdf2 hash to Argon2id
    # A short access token in the body, and a rotating refresh token in an HttpOnly cookie.
    token = sessions.start_session(db, user, response)
    db.commit()
    return TokenResponse(access_token=token, user=user)


@router.post("/auth/refresh", response_model=TokenResponse)
def refresh(http_request: Request, response: Response, db: Session = Depends(get_db)):
    """Exchange the refresh cookie for a new access token (and a new refresh cookie)."""
    sessions.require_same_site(http_request)
    user, token = sessions.rotate(db, http_request, response)
    return TokenResponse(access_token=token, user=user)


@router.post("/auth/logout", status_code=204)
def logout(http_request: Request, response: Response, db: Session = Depends(get_db)):
    """Sign out this browser: revoke its refresh family and clear the cookie."""
    sessions.require_same_site(http_request)
    sessions.end_session(db, http_request, response)
    response.status_code = 204
    return response


@router.post("/auth/logout-all", status_code=204)
def logout_all(
    http_request: Request,
    response: Response,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Sign out everywhere: every access and refresh token of this user stops working."""
    sessions.revoke_user(db, current_user)
    db.commit()
    sessions.clear_cookie(response)
    response.status_code = 204
    return response


@router.get("/users/me", response_model=UserResponse)
def get_current_profile(current_user: User = Depends(require_auth)):
    """Get current user's profile."""
    return current_user


@router.get("/users/{user_id}", response_model=PublicUserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get user profile."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/users/username/{username}", response_model=PublicUserResponse)
def get_user_by_username(username: str, db: Session = Depends(get_db)):
    """Get user profile by username."""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/users/me", response_model=UserResponse)
def update_profile(
    user_update: UserUpdate,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Update current user's profile."""
    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)
    return current_user
