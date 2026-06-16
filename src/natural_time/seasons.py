"""Season helpers backed by Cosine Kitty Astronomy Engine."""

from __future__ import annotations

from datetime import UTC, datetime

import astronomy


def _time_to_datetime(time: astronomy.Time) -> datetime:
    """Convert an Astronomy Engine `Time` to an aware UTC datetime."""

    return time.Utc().replace(tzinfo=UTC)


def season_datetime(year: int, season: str) -> datetime:
    """Return the UTC datetime of an equinox or solstice."""

    seasons = astronomy.Seasons(year)
    match season:
        case "mar":
            return _time_to_datetime(seasons.mar_equinox)
        case "jun":
            return _time_to_datetime(seasons.jun_solstice)
        case "sep":
            return _time_to_datetime(seasons.sep_equinox)
        case "dec":
            return _time_to_datetime(seasons.dec_solstice)
        case _:
            raise ValueError(f"Unknown season {season!r}")


def december_solstice(year: int) -> datetime:
    """Return the UTC datetime of the December solstice."""

    return season_datetime(year, "dec")


def june_solstice(year: int) -> datetime:
    """Return the UTC datetime of the June solstice."""

    return season_datetime(year, "jun")
