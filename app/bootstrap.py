from __future__ import annotations

from app.extensions import db
from app.models import (
    EVENT_INVITATION_STATUS_NAMES,
    GROUP_ROLE_NAMES,
    EventInvitationStatus,
    GroupRole,
    missing_event_invitation_status_names,
    missing_group_role_names,
)


def ensure_canonical_lookup_rows() -> dict[str, list[str]]:
    existing_status_names = [row[0] for row in db.session.query(EventInvitationStatus.name).all()]
    existing_role_names = [row[0] for row in db.session.query(GroupRole.name).all()]

    missing_statuses = missing_event_invitation_status_names(existing_status_names)
    missing_roles = missing_group_role_names(existing_role_names)

    if missing_statuses:
        db.session.add_all(EventInvitationStatus(name=name) for name in missing_statuses)
    if missing_roles:
        db.session.add_all(GroupRole(name=name) for name in missing_roles)

    if missing_statuses or missing_roles:
        db.session.commit()

    return {
        "event_invitation_statuses": list(EVENT_INVITATION_STATUS_NAMES),
        "group_roles": list(GROUP_ROLE_NAMES),
    }
