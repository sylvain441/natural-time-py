"""Astronomical helpers for Natural Time.

The heavy lifting is delegated to Cosine Kitty Astronomy Engine, the same
astronomical engine used by `natural-time-js`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import astronomy

from .core import NaturalDate
from .seasons import december_solstice, june_solstice

NIGHT_ALTITUDE = -12.0
GOLDEN_HOUR_ALTITUDE = 6.0


@dataclass(frozen=True)
class SunPosition:
    azimuth: float
    elevation: float
    altitude: float
    highest_altitude: float
    is_above_horizon: bool

    @property
    def highestAltitude(self) -> float:
        return self.highest_altitude

    @property
    def isAboveHorizon(self) -> bool:
        return self.is_above_horizon


@dataclass(frozen=True)
class SunEvents:
    sunrise: float
    sunset: float
    night_start: float
    night_end: float
    morning_golden_hour: float
    evening_golden_hour: float

    @property
    def nightStart(self) -> float:
        return self.night_start

    @property
    def nightEnd(self) -> float:
        return self.night_end

    @property
    def morningGoldenHour(self) -> float:
        return self.morning_golden_hour

    @property
    def eveningGoldenHour(self) -> float:
        return self.evening_golden_hour


@dataclass(frozen=True)
class MoonPosition:
    altitude: float
    phase: float


@dataclass(frozen=True)
class MoonEvents:
    moonrise: float
    moonset: float
    highest_altitude: float

    @property
    def highestAltitude(self) -> float:
        return self.highest_altitude


@dataclass(frozen=True)
class MustachesRange:
    winter_sunrise: float
    winter_sunset: float
    summer_sunrise: float
    summer_sunset: float
    average_mustache_angle: float

    @property
    def winterSunrise(self) -> float:
        return self.winter_sunrise

    @property
    def winterSunset(self) -> float:
        return self.winter_sunset

    @property
    def summerSunrise(self) -> float:
        return self.summer_sunrise

    @property
    def summerSunset(self) -> float:
        return self.summer_sunset

    @property
    def averageMustacheAngle(self) -> float:
        return self.average_mustache_angle


@dataclass(frozen=True)
class NaturalTimeSnapshot:
    natural_date: NaturalDate
    sun_position: SunPosition
    sun_events: SunEvents
    moon_position: MoonPosition
    moon_events: MoonEvents
    light_phase: str
    day_progress: float


def _datetime_to_astro_time(date: datetime) -> astronomy.Time:
    if date.tzinfo is None:
        date = date.replace(tzinfo=UTC)
    iso = date.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    return astronomy.Time(iso)


def _unix_ms_to_astro_time(unix_ms: int) -> astronomy.Time:
    return _datetime_to_astro_time(datetime.fromtimestamp(unix_ms / 1000, UTC))


def _astro_time_to_unix_ms(time: astronomy.Time) -> int:
    return int(time.Utc().replace(tzinfo=UTC).timestamp() * 1000)


def _observer(natural_date: NaturalDate, latitude: float) -> astronomy.Observer:
    return astronomy.Observer(latitude, natural_date.longitude, 0)


def _is_summer_season(day_of_year: int, latitude: float) -> bool:
    if latitude >= 0:
        return 91 <= day_of_year <= 273
    return day_of_year <= 91 or day_of_year >= 273


def _event_degree(
    natural_date: NaturalDate,
    event_time: astronomy.Time | None,
    *,
    is_summer_default: bool,
    latitude: float,
) -> float:
    if event_time is None:
        is_summer = _is_summer_season(natural_date.day_of_year, latitude)
        return 360 if is_summer and is_summer_default else 0 if is_summer else 180
    value = natural_date.get_time_of_event(_astro_time_to_unix_ms(event_time))
    return float(value or 0)


def natural_sun_position(natural_date: NaturalDate, latitude: float) -> SunPosition:
    """Calculate current solar azimuth and elevation."""

    observer = _observer(natural_date, latitude)
    time = _unix_ms_to_astro_time(natural_date.unix_time)
    sun = astronomy.Equator(astronomy.Body.Sun, time, observer, True, False)
    horizon = astronomy.Horizon(time, observer, sun.ra, sun.dec, astronomy.Refraction.Airless)
    highest = astronomy.SearchHourAngle(
        astronomy.Body.Sun,
        observer,
        0,
        _unix_ms_to_astro_time(natural_date.nadir),
    ).hor.altitude

    return SunPosition(
        azimuth=horizon.azimuth,
        elevation=horizon.altitude,
        altitude=max(horizon.altitude, 0),
        highest_altitude=highest,
        is_above_horizon=horizon.altitude >= 0,
    )


def natural_sun_events(natural_date: NaturalDate, latitude: float) -> SunEvents:
    """Calculate daily solar events in natural degrees."""

    observer = _observer(natural_date, latitude)
    nadir = _unix_ms_to_astro_time(natural_date.nadir)

    sunrise = astronomy.SearchRiseSet(astronomy.Body.Sun, observer, astronomy.Direction.Rise, nadir, 1)
    sunset = astronomy.SearchRiseSet(astronomy.Body.Sun, observer, astronomy.Direction.Set, nadir, 1)
    night_start = astronomy.SearchAltitude(
        astronomy.Body.Sun,
        observer,
        astronomy.Direction.Set,
        nadir,
        2,
        NIGHT_ALTITUDE,
    )
    night_end = astronomy.SearchAltitude(
        astronomy.Body.Sun,
        observer,
        astronomy.Direction.Rise,
        nadir,
        2,
        NIGHT_ALTITUDE,
    )
    morning_golden = astronomy.SearchAltitude(
        astronomy.Body.Sun,
        observer,
        astronomy.Direction.Rise,
        nadir,
        2,
        GOLDEN_HOUR_ALTITUDE,
    )
    evening_golden = astronomy.SearchAltitude(
        astronomy.Body.Sun,
        observer,
        astronomy.Direction.Set,
        nadir,
        2,
        GOLDEN_HOUR_ALTITUDE,
    )

    return SunEvents(
        sunrise=_event_degree(natural_date, sunrise, is_summer_default=False, latitude=latitude),
        sunset=_event_degree(natural_date, sunset, is_summer_default=True, latitude=latitude),
        night_start=_event_degree(natural_date, night_start, is_summer_default=True, latitude=latitude),
        night_end=_event_degree(natural_date, night_end, is_summer_default=False, latitude=latitude),
        morning_golden_hour=_event_degree(natural_date, morning_golden, is_summer_default=False, latitude=latitude),
        evening_golden_hour=_event_degree(natural_date, evening_golden, is_summer_default=True, latitude=latitude),
    )


def natural_moon_position(natural_date: NaturalDate, latitude: float) -> MoonPosition:
    """Calculate lunar altitude and phase."""

    observer = _observer(natural_date, latitude)
    time = _unix_ms_to_astro_time(natural_date.unix_time)
    moon = astronomy.Equator(astronomy.Body.Moon, time, observer, True, False)
    horizon = astronomy.Horizon(time, observer, moon.ra, moon.dec, astronomy.Refraction.Airless)

    return MoonPosition(
        altitude=max(horizon.altitude, 0),
        phase=astronomy.MoonPhase(time),
    )


def natural_moon_events(natural_date: NaturalDate, latitude: float) -> MoonEvents:
    """Calculate daily lunar events in natural degrees."""

    observer = _observer(natural_date, latitude)
    nadir = _unix_ms_to_astro_time(natural_date.nadir)
    moonrise = astronomy.SearchRiseSet(astronomy.Body.Moon, observer, astronomy.Direction.Rise, nadir, 1)
    moonset = astronomy.SearchRiseSet(astronomy.Body.Moon, observer, astronomy.Direction.Set, nadir, 1)
    highest = astronomy.SearchHourAngle(astronomy.Body.Moon, observer, 0, nadir).hor.altitude

    return MoonEvents(
        moonrise=float(natural_date.get_time_of_event(_astro_time_to_unix_ms(moonrise)) or 0) if moonrise else 0,
        moonset=float(natural_date.get_time_of_event(_astro_time_to_unix_ms(moonset)) or 0) if moonset else 0,
        highest_altitude=highest,
    )


def mustaches_range(natural_date: NaturalDate, latitude: float) -> MustachesRange:
    """Calculate the seasonal range of sunrise and sunset positions."""

    current_year = natural_date.as_datetime().year
    winter = natural_sun_events(NaturalDate(december_solstice(current_year), 0), latitude)
    summer = natural_sun_events(NaturalDate(june_solstice(current_year), 0), latitude)

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


def _between_circular(value: float, start: float, end: float) -> bool:
    if start <= end:
        return start <= value < end
    return value >= start or value < end


def natural_light_phase(natural_date: NaturalDate, sun_events: SunEvents | None = None) -> str:
    events = sun_events or natural_sun_events(natural_date, 0)
    value = natural_date.time
    if _between_circular(value, events.night_start, events.night_end):
        return "night"
    if _between_circular(value, events.night_end, events.sunrise):
        return "dawn"
    if _between_circular(value, events.sunrise, events.morning_golden_hour):
        return "golden_morning"
    if _between_circular(value, events.evening_golden_hour, events.sunset):
        return "golden_evening"
    if _between_circular(value, events.sunset, events.night_start):
        return "dusk"
    return "day"


def build_snapshot(
    date: datetime | int | float | str | None = None,
    *,
    latitude: float,
    longitude: float,
    precision: float = 0,
) -> NaturalTimeSnapshot:
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
