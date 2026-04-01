from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Select, func, or_, select

from app.extensions import db
from app.models import User


def create_user(
    *,
    username: str,
    email: str,
    password: str,
    firstname: str | None = None,
    lastname: str | None = None,
    account_type: str | None = None,
    preference_tags: list[str] | None = None,
    tags: list[str] | None = None,
    home_town: str | None = None,
    home_state: str | None = None,
    home_country: str | None = None,
    home_gym: str | None = None,
    home_latlng: str | None = None,
    geoll: str | None = None,
    active: bool = True,
    site_admin: bool | None = None,
) -> User:
    normalized_username = _normalize_username(username)
    normalized_email = _normalize_email(email)
    _validate_unique_username_email(normalized_username, normalized_email)

    effective_site_admin = site_admin if site_admin is not None else not _has_active_site_admin()

    user = User(
        username=normalized_username,
        email=normalized_email,
        firstname=_normalize_optional(firstname),
        lastname=_normalize_optional(lastname),
        account_type=_normalize_optional(account_type),
        preference_tags=preference_tags,
        tags=tags,
        home_town=_normalize_optional(home_town),
        home_state=_normalize_optional(home_state),
        home_country=_normalize_optional(home_country),
        home_gym=_normalize_optional(home_gym),
        home_latlng=_normalize_optional(home_latlng),
        geoll=_normalize_optional(geoll),
        active=active,
        site_admin=effective_site_admin,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


def update_user(
    user: User,
    *,
    username: str,
    email: str,
    password: str | None = None,
    firstname: str | None = None,
    lastname: str | None = None,
    account_type: str | None = None,
    preference_tags: list[str] | None = None,
    tags: list[str] | None = None,
    home_town: str | None = None,
    home_state: str | None = None,
    home_country: str | None = None,
    home_gym: str | None = None,
    home_latlng: str | None = None,
    geoll: str | None = None,
    active: bool = True,
    site_admin: bool = False,
) -> User:
    normalized_username = _normalize_username(username)
    normalized_email = _normalize_email(email)
    _validate_unique_username_email(normalized_username, normalized_email, exclude_user=user)
    _validate_admin_invariants(user, active=active, site_admin=site_admin)

    user.username = normalized_username
    user.email = normalized_email
    user.firstname = _normalize_optional(firstname)
    user.lastname = _normalize_optional(lastname)
    user.account_type = _normalize_optional(account_type)
    user.preference_tags = preference_tags
    user.tags = tags
    user.home_town = _normalize_optional(home_town)
    user.home_state = _normalize_optional(home_state)
    user.home_country = _normalize_optional(home_country)
    user.home_gym = _normalize_optional(home_gym)
    user.home_latlng = _normalize_optional(home_latlng)
    user.geoll = _normalize_optional(geoll)
    user.active = active
    user.site_admin = site_admin
    if password:
        user.set_password(password)
    db.session.commit()
    return user


def authenticate_user(*, identity: str, password: str) -> User | None:
    normalized_identity = identity.strip().lower()
    if not normalized_identity:
        return None

    statement: Select[tuple[User]] = select(User).where(
        or_(
            func.lower(User.username) == normalized_identity,
            func.lower(User.email) == normalized_identity,
        )
    )
    user = db.session.scalar(statement)
    if user is None or not user.active or not user.check_password(password):
        return None
    return user


def record_login(user: User) -> User:
    user.last_login_at = datetime.now(UTC)
    db.session.commit()
    return user


def list_users() -> list[User]:
    statement: Select[tuple[User]] = select(User).order_by(User.id)
    return list(db.session.scalars(statement))


def _normalize_username(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("Username is required.")
    return normalized


def _normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("Email is required.")
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise ValueError("Email must look like an email address.")
    return normalized


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _validate_unique_username_email(
    username: str,
    email: str,
    *,
    exclude_user: User | None = None,
) -> None:
    statement: Select[tuple[User]] = select(User).where(
        or_(func.lower(User.username) == username, func.lower(User.email) == email)
    )
    for existing in db.session.scalars(statement):
        if exclude_user is not None and existing.id == exclude_user.id:
            continue
        if existing.username == username:
            raise ValueError("Username is already in use.")
        if existing.email == email:
            raise ValueError("Email is already in use.")


def _has_active_site_admin(*, exclude_user_id: int | None = None) -> bool:
    statement: Select[tuple[User]] = select(User).where(
        User.site_admin.is_(True),
        User.active.is_(True),
    )
    if exclude_user_id is not None:
        statement = statement.where(User.id != exclude_user_id)
    return db.session.scalar(statement.limit(1)) is not None


def _validate_admin_invariants(user: User, *, active: bool, site_admin: bool) -> None:
    removing_admin_access = user.active and user.site_admin and not (active and site_admin)
    if removing_admin_access and not _has_active_site_admin(exclude_user_id=user.id):
        raise ValueError("At least one active site admin must remain.")
