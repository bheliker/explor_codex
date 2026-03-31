from __future__ import annotations

from sqlalchemy import Select, select

from app.extensions import db
from app.models import Activity, Event, Group, Image, PointOfInterest, Segment, User


def create_image(
    *,
    photographer: User | None = None,
    group: Group | None = None,
    segment: Segment | None = None,
    activity: Activity | None = None,
    img_small: str | None = None,
    img_medium: str | None = None,
    img_large: str | None = None,
    img_thumb: str | None = None,
    alt_txt: str | None = None,
    title: str | None = None,
    caption: str | None = None,
    latlng: str | None = None,
    geoll: str | None = None,
    tags: list[str] | None = None,
    url: str | None = None,
) -> Image:
    image = Image(
        photographer=photographer,
        group=group,
        segment=segment,
        activity=activity,
        img_small=img_small,
        img_medium=img_medium,
        img_large=img_large,
        img_thumb=img_thumb,
        alt_txt=alt_txt,
        title=title,
        caption=caption,
        latlng=latlng,
        geoll=geoll,
        tags=tags,
        url=url,
    )
    db.session.add(image)
    db.session.commit()
    return image


def list_images(
    *,
    photographer: User | None = None,
    group: Group | None = None,
    segment: Segment | None = None,
    activity: Activity | None = None,
) -> list[Image]:
    statement: Select[tuple[Image]] = select(Image).order_by(Image.id)
    if photographer is not None:
        statement = statement.where(Image.photographer_id == photographer.id)
    if group is not None:
        statement = statement.where(Image.group_id == group.id)
    if segment is not None:
        statement = statement.where(Image.segment_id == segment.id)
    if activity is not None:
        statement = statement.where(Image.activity_id == activity.id)
    return list(db.session.scalars(statement))


def update_image(
    image: Image,
    *,
    photographer: User | None = None,
    group: Group | None = None,
    segment: Segment | None = None,
    activity: Activity | None = None,
    img_small: str | None = None,
    img_medium: str | None = None,
    img_large: str | None = None,
    img_thumb: str | None = None,
    alt_txt: str | None = None,
    title: str | None = None,
    caption: str | None = None,
    latlng: str | None = None,
    geoll: str | None = None,
    tags: list[str] | None = None,
    url: str | None = None,
) -> Image:
    image.photographer = photographer
    image.group = group
    image.segment = segment
    image.activity = activity
    image.img_small = img_small
    image.img_medium = img_medium
    image.img_large = img_large
    image.img_thumb = img_thumb
    image.alt_txt = alt_txt
    image.title = title
    image.caption = caption
    image.latlng = latlng
    image.geoll = geoll
    image.tags = tags
    image.url = url
    db.session.commit()
    return image


def attach_image_to_event(event: Event, image: Image) -> Event:
    if image not in event.images:
        event.images.append(image)
        db.session.commit()
    return event


def attach_image_to_poi(point_of_interest: PointOfInterest, image: Image) -> PointOfInterest:
    if image not in point_of_interest.images:
        point_of_interest.images.append(image)
        db.session.commit()
    return point_of_interest
