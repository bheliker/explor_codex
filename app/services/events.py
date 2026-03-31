from __future__ import annotations

from app.extensions import db
from app.geometry import point_coordinates
from app.models import Activity, Calendar, Event, EventFee, EventInvitation, Route, User


def create_event(
    *,
    name: str,
    owner: User | None = None,
    route: Route | None = None,
    activity: Activity | None = None,
    private: bool = False,
    description: str | None = None,
    url: str | None = None,
    reg_url: str | None = None,
    photo_url: str | None = None,
    logo: str | None = None,
    profile_photo: str | None = None,
    notes: str | None = None,
    tags: list[str] | None = None,
    lat: float | None = None,
    lon: float | None = None,
    town: str | None = None,
    state: str | None = None,
    country: str | None = None,
    latlng: str | None = None,
    geoll: str | None = None,
) -> Event:
    if geoll is None and lat is not None and lon is not None:
        geoll = f'{{"type":"Point","coordinates":[{lon},{lat}]}}'
    if geoll is not None:
        coordinates = point_coordinates(geoll)
        if coordinates is not None:
            lon, lat = coordinates
            if latlng is None:
                latlng = f"{lat},{lon}"

    event = Event(
        name=name,
        owner_id=owner.id if owner is not None else None,
        route=route,
        activity=activity,
        private=private,
        description=description,
        url=url,
        reg_url=reg_url,
        photo_url=photo_url,
        logo=logo,
        profile_photo=profile_photo,
        notes=notes,
        tags=tags,
        lat=lat,
        lon=lon,
        town=town,
        state=state,
        country=country,
        latlng=latlng,
        geoll=geoll,
    )
    db.session.add(event)
    db.session.commit()
    return event


def update_event(
    event: Event,
    *,
    name: str,
    route: Route | None = None,
    activity: Activity | None = None,
    private: bool = False,
    description: str | None = None,
    url: str | None = None,
    reg_url: str | None = None,
    photo_url: str | None = None,
    logo: str | None = None,
    profile_photo: str | None = None,
    notes: str | None = None,
    tags: list[str] | None = None,
    lat: float | None = None,
    lon: float | None = None,
    town: str | None = None,
    state: str | None = None,
    country: str | None = None,
    latlng: str | None = None,
    geoll: str | None = None,
    primary_activity: str | None = None,
    event_type: str | None = None,
    subtype: str | None = None,
) -> Event:
    if geoll is None and lat is not None and lon is not None:
        geoll = f'{{"type":"Point","coordinates":[{lon},{lat}]}}'
    if geoll is not None:
        coordinates = point_coordinates(geoll)
        if coordinates is not None:
            lon, lat = coordinates
            if latlng is None:
                latlng = f"{lat},{lon}"

    event.name = name
    event.route = route
    event.activity = activity
    event.private = private
    event.description = description
    event.url = url
    event.reg_url = reg_url
    event.photo_url = photo_url
    event.logo = logo
    event.profile_photo = profile_photo
    event.notes = notes
    event.tags = tags
    event.lat = lat
    event.lon = lon
    event.town = town
    event.state = state
    event.country = country
    event.latlng = latlng
    event.geoll = geoll
    event.primary_activity = primary_activity
    event.type = event_type
    event.subtype = subtype
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
    tags: list[str] | None = None,
) -> EventFee:
    event_fee = EventFee(
        event=event,
        name=name,
        description=description,
        fee=fee,
        duration=duration,
        tags=tags,
    )
    db.session.add(event_fee)
    db.session.commit()
    return event_fee


def update_event_fee(
    event_fee: EventFee,
    *,
    event: Event | None = None,
    name: str | None = None,
    fee: float | None = None,
    duration: int | None = None,
    description: str | None = None,
    tags: list[str] | None = None,
) -> EventFee:
    event_fee.event = event
    event_fee.name = name
    event_fee.fee = fee
    event_fee.duration = duration
    event_fee.description = description
    event_fee.tags = tags
    db.session.commit()
    return event_fee
