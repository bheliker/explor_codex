from __future__ import annotations

from app.extensions import db
from app.geometry import point_coordinates
from app.models import Group, GroupDues, GroupExternalUrl, Membership, Route, User


def create_group(
    *,
    name: str,
    shortname: str,
    invite_only: bool = False,
    private: bool = False,
    home_town: str | None = None,
    home_state: str | None = None,
    home_country: str | None = None,
    home_latlng: str | None = None,
    home_add: str | None = None,
    full_address: str | None = None,
    geoll: str | None = None,
) -> Group:
    if geoll is not None and home_latlng is None:
        coordinates = point_coordinates(geoll)
        if coordinates is not None:
            lon, lat = coordinates
            home_latlng = f"{lat},{lon}"

    group = Group(
        name=name,
        shortname=shortname,
        invite_only=invite_only,
        private=private,
        home_town=home_town,
        home_state=home_state,
        home_country=home_country,
        home_latlng=home_latlng,
        home_add=home_add,
        full_address=full_address,
        geoll=geoll,
    )
    db.session.add(group)
    db.session.commit()
    return group


def ensure_group_membership(
    group: Group,
    user: User,
    *,
    role_name: str | None = None,
) -> Membership:
    membership = (
        group.ensure_membership(user, role_name=role_name)
        if role_name is not None
        else _join_group(group, user)
    )
    db.session.add(membership)
    db.session.commit()
    return membership


def add_group_link(
    group: Group,
    *,
    name: str,
    url: str,
    link_type: str = "website",
) -> GroupExternalUrl:
    link = GroupExternalUrl(group=group, name=name, type=link_type, url=url)
    db.session.add(link)
    db.session.commit()
    return link


def add_route_link(
    route: Route,
    *,
    name: str,
    url: str,
    link_type: str = "website",
) -> GroupExternalUrl:
    link = GroupExternalUrl(route=route, name=name, type=link_type, url=url)
    db.session.add(link)
    db.session.commit()
    return link


def add_group_dues(
    group: Group,
    *,
    name: str,
    fee: float,
    duration: int,
    description: str | None = None,
) -> GroupDues:
    dues = GroupDues(
        group=group,
        name=name,
        description=description,
        fee=fee,
        duration=duration,
    )
    db.session.add(dues)
    db.session.commit()
    return dues


def attach_route_to_group(group: Group, route: Route) -> Group:
    if route not in group.routes:
        group.routes.append(route)
        db.session.commit()
    return group


def _join_group(group: Group, user: User) -> Membership:
    group.join(user)
    db.session.flush()
    membership = group.get_membership(user)
    if membership is None:
        raise RuntimeError("group join did not create a membership")
    return membership
