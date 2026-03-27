from __future__ import annotations

from app.extensions import db
from app.models import Activity, Calendar, Event, EventFee, EventInvitation, Route, User


def create_event(
    *,
    name: str,
    owner: User | None = None,
    route: Route | None = None,
    activity: Activity | None = None,
    private: bool = False,
    description: str | None = None,
    town: str | None = None,
    state: str | None = None,
) -> Event:
    event = Event(
        name=name,
        owner_id=owner.id if owner is not None else None,
        route=route,
        activity=activity,
        private=private,
        description=description,
        town=town,
        state=state,
    )
    db.session.add(event)
    db.session.commit()
    return event


def attach_calendar(event: Event, calendar: Calendar) -> Event:
    if calendar not in event.calendars:
        event.calendars.append(calendar)
        db.session.commit()
    return event


def set_rsvp(event: Event, user: User, *, status_name: str) -> EventInvitation:
    participation = event.ensure_participation(user, status_name=status_name)
    db.session.add(participation)
    db.session.commit()
    return participation


def add_event_fee(
    event: Event,
    *,
    name: str,
    fee: float,
    duration: int,
    description: str | None = None,
) -> EventFee:
    event_fee = EventFee(
        event=event,
        name=name,
        description=description,
        fee=fee,
        duration=duration,
    )
    db.session.add(event_fee)
    db.session.commit()
    return event_fee
