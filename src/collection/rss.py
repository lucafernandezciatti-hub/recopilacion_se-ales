"""Lectura de feeds RSS/Atom configurados en config/sources.yaml."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone

import feedparser

from src.collection.normalize import normalize_url
from src.config import sources_config

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FeedItem:
    url: str
    title: str | None
    published: date | None
    source_name: str
    source_owner: str | None
    steep_hint: str | None


def _entry_date(entry) -> date | None:
    for key in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, key, None)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc).date()
            except (TypeError, ValueError):
                continue
    return None


def read_feed(url: str, source: dict, limit: int = 40) -> list[FeedItem]:
    items: list[FeedItem] = []
    try:
        parsed = feedparser.parse(url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("feed ilegible %s: %s", url, exc)
        return items

    for entry in parsed.entries[:limit]:
        link = getattr(entry, "link", None)
        if not link:
            continue
        try:
            link = normalize_url(link)
        except ValueError:
            continue
        items.append(
            FeedItem(
                url=link,
                title=getattr(entry, "title", None),
                published=_entry_date(entry),
                source_name=source.get("name", ""),
                source_owner=source.get("owner"),
                steep_hint=source.get("steep_primary"),
            )
        )
    return items


def configured_feeds() -> list[dict]:
    return [s for s in sources_config().get("sources", []) if s.get("rss")]


def harvest_all(limit_per_feed: int = 40) -> list[FeedItem]:
    items: list[FeedItem] = []
    for source in configured_feeds():
        found = read_feed(source["rss"], source, limit=limit_per_feed)
        logger.info("%s: %d items", source["name"], len(found))
        items.extend(found)
    return items
