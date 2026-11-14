"""The sky over a NaturalDate: sun, moon and mustaches, in natural degrees.

Astronomy Engine does the heavy lifting, the same engine natural-time-js uses.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import astronomy

from .core import (
    Moment,
    NaturalDate,
    _year_context,
    astro_time,
    december_solstice,
    is_real,
    june_solstice,
    time_of_event,
    unix_ms_of,
    utc_year,
)

NIGHT_ALTITUDE = -12.0
GOLDEN_HOUR_ALTITUDE = 6.0
SUMMER_START_DAY = 91
SUMMER_END_DAY = 273

_SUN = astronomy.Body.Sun
_MOON = astronomy.Body.Moon
_RISE = astronomy.Direction.Rise
_SET = astronomy.Direction.Set


@dataclass(frozen=True)
class SunPosition:
    azimuth: float
    elevation: float
    altitude: float
    highest_altitude: float
    is_above_horizon: bool


@dataclass(frozen=True)
class SunEvents:
    sunrise: float
    sunset: float
    night_start: float
    night_end: float
    morning_golden_hour: float
    evening_golden_hour: float


@dataclass(frozen=True)
class MoonPosition:
    altitude: float
    phase: float


@dataclass(frozen=True)
class MoonEvents:
    moonrise: float
    moonset: float
    highest_altitude: float


@dataclass(frozen=True)
class MustachesRange:
    winter_sunrise: float
    winter_sunset: float
    summer_sunrise: float
    summer_sunset: float
    average_mustache_angle: float


@dataclass(frozen=True)
class NaturalTimeSnapshot:
    natural_date: NaturalDate
    sun_position: SunPosition
    sun_events: SunEvents
    moon_position: MoonPosition
    moon_events: MoonEvents
    light_phase: str
    day_progress: float


def _check(natural_date: NaturalDate, latitude: float) -> None:
    if not (is_real(latitude) and -90 <= latitude <= 90):
        raise ValueError(f"Latitude must be between -90 and +90, got {latitude!r}")


def _observer(latitude: float, longitude: float) -> astronomy.Observer:
    return astronomy.Observer(latitude, longitude, 0)


def _horizon(body: astronomy.Body, natural_date: NaturalDate, observer: astronomy.Observer) -> astronomy.HorizontalCoordinates:
    time = astro_time(natural_date.unix_time)
    equator = astronomy.Equator(body, time, observer, True, False)
    return astronomy.Horizon(time, observer, equator.ra, equator.dec, astronomy.Refraction.Airless)


def _degree(nadir: int, event: astronomy.Time) -> float:
    # As in JS `getTimeOfEvent(...) || 0`: an event outside the natural day reads 0
    return time_of_event(nadir, unix_ms_of(event)) or 0.0


def natural_sun_position(natural_date: NaturalDate, latitude: float) -> SunPosition:
    _check(natural_date, latitude)
    observer = _observer(latitude, natural_date.longitude)
    horizon = _horizon(_SUN, natural_date, observer)
    highest = astronomy.SearchHourAngle(_SUN, observer, 0, astro_time(natural_date.nadir))
    return SunPosition(
        azimuth=horizon.azimuth,
        elevation=horizon.altitude,
        altitude=max(horizon.altitude, 0.0),
        highest_altitude=highest.hor.altitude,
        is_above_horizon=horizon.altitude >= 0,
    )


def natural_sun_events(natural_date: NaturalDate, latitude: float) -> SunEvents:
    """Sunrise, sunset, night (-12°) and golden hours (6°) within the natural day, in degrees.

    When the sun never crosses a line, the polar day reads 0 and 360, the polar night 180.
    """
    _check(natural_date, latitude)
    return _sun_events(natural_date.nadir, natural_date.day_of_year, float(latitude), natural_date.longitude)


@lru_cache(maxsize=256)
def _sun_events(nadir: int, day_of_year: int, latitude: float, longitude: float) -> SunEvents:
    observer = _observer(latitude, longitude)
    start = astro_time(nadir)
    if latitude >= 0:
        summer = SUMMER_START_DAY <= day_of_year <= SUMMER_END_DAY
    else:
        summer = day_of_year <= SUMMER_START_DAY or day_of_year >= SUMMER_END_DAY

    def degree(event: astronomy.Time | None, summer_default: float) -> float:
        if event is None:
            return summer_default if summer else 180.0
        return _degree(nadir, event)

    def altitude(direction: astronomy.Direction, value: float) -> astronomy.Time | None:
        return astronomy.SearchAltitude(_SUN, observer, direction, start, 2, value)

    return SunEvents(
        sunrise=degree(astronomy.SearchRiseSet(_SUN, observer, _RISE, start, 1), 0.0),
        sunset=degree(astronomy.SearchRiseSet(_SUN, observer, _SET, start, 1), 360.0),
        night_start=degree(altitude(_SET, NIGHT_ALTITUDE), 360.0),
        night_end=degree(altitude(_RISE, NIGHT_ALTITUDE), 0.0),
        morning_golden_hour=degree(altitude(_RISE, GOLDEN_HOUR_ALTITUDE), 0.0),
        evening_golden_hour=degree(altitude(_SET, GOLDEN_HOUR_ALTITUDE), 360.0),
    )


def natural_moon_position(natural_date: NaturalDate, latitude: float) -> MoonPosition:
    _check(natural_date, latitude)
    horizon = _horizon(_MOON, natural_date, _observer(latitude, natural_date.longitude))
    return MoonPosition(altitude=max(horizon.altitude, 0.0), phase=astronomy.MoonPhase(astro_time(natural_date.unix_time)))


def natural_moon_events(natural_date: NaturalDate, latitude: float) -> MoonEvents:
    """Moonrise and moonset within the natural day, in degrees; 0 when the moon skips the day."""
    _check(natural_date, latitude)
    return _moon_events(natural_date.nadir, float(latitude), natural_date.longitude)


@lru_cache(maxsize=256)
def _moon_events(nadir: int, latitude: float, longitude: float) -> MoonEvents:
    observer = _observer(latitude, longitude)
    start = astro_time(nadir)

    def degree(event: astronomy.Time | None) -> float:
        return 0.0 if event is None else _degree(nadir, event)

    return MoonEvents(
        moonrise=degree(astronomy.SearchRiseSet(_MOON, observer, _RISE, start, 1)),
        moonset=degree(astronomy.SearchRiseSet(_MOON, observer, _SET, start, 1)),
        highest_altitude=astronomy.SearchHourAngle(_MOON, observer, 0, start).hor.altitude,
    )


def mustaches_range(natural_date: NaturalDate, latitude: float) -> MustachesRange:
    """Sunrise and sunset at both solstices of the UTC year, seen from the meridian.

    The angle averages the four gaps to the equinox line, held within [0, 90].
    natural-time-js swallows any error here and answers five zeros; this raises
    instead, because zeros would pass for a real sky. After the checks above,
    the JS catch has nothing left to catch.
    """
    _check(natural_date, latitude)
    return _mustaches(utc_year(natural_date.unix_time), float(latitude))


@lru_cache(maxsize=64)
def _mustaches(year: int, latitude: float) -> MustachesRange:
    winter = natural_sun_events(NaturalDate(december_solstice(year), 0), latitude)
    summer = natural_sun_events(NaturalDate(june_solstice(year), 0), latitude)
    if latitude >= 0:
        average = (winter.sunrise - summer.sunrise + summer.sunset - winter.sunset) / 4
    else:
        average = (summer.sunrise - winter.sunrise + winter.sunset - summer.sunset) / 4
    return MustachesRange(
        winter_sunrise=winter.sunrise,
        winter_sunset=winter.sunset,
        summer_sunrise=summer.sunrise,
        summer_sunset=summer.sunset,
        average_mustache_angle=min(max(average, 0), 90),
    )


def _between(value: float, start: float, end: float) -> bool:
    if start <= end:
        return start <= value < end
    return value >= start or value < end


def natural_light_phase(natural_date: NaturalDate, sun_events: SunEvents | None = None) -> str:
    """night, dawn, golden_morning, day, golden_evening or dusk. Python only, not in natural-time-js.

    Without `sun_events`, the sun is read at the equator.
    """
    events = sun_events or natural_sun_events(natural_date, 0)
    time = natural_date.time
    # Polar night: the sun never comes back up to -12°, every event reads 180
    # and no interval is left to catch the night
    if events.night_start == events.night_end == events.sunrise == events.sunset:
        return "night"
    if _between(time, events.night_start, events.night_end):
        return "night"
    if _between(time, events.night_end, events.sunrise):
        return "dawn"
    if _between(time, events.sunrise, events.morning_golden_hour):
        return "golden_morning"
    if _between(time, events.evening_golden_hour, events.sunset):
        return "golden_evening"
    if _between(time, events.sunset, events.night_start):
        return "dusk"
    return "day"


def build_snapshot(
    date: Moment | None = None,
    *,
    latitude: float,
    longitude: float,
    precision: int | float = 0,
) -> NaturalTimeSnapshot:
    """Everything a home needs to know about the sky at one instant, computed once."""
    natural_date = NaturalDate(date, longitude, precision)
    sun_events = natural_sun_events(natural_date, latitude)
    return NaturalTimeSnapshot(
        natural_date=natural_date,
        sun_position=natural_sun_position(natural_date, latitude),
        sun_events=sun_events,
        moon_position=natural_moon_position(natural_date, latitude),
        moon_events=natural_moon_events(natural_date, latitude),
        light_phase=natural_light_phase(natural_date, sun_events),
        day_progress=natural_date.time / 360 * 100,
    )


def reset_caches() -> None:
    """Forget every year, day and mustache already computed."""
    _year_context.cache_clear()
    _sun_events.cache_clear()
    _moon_events.cache_clear()
    _mustaches.cache_clear()
