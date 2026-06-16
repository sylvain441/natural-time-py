"""Natural Time Python API."""

from .astronomy import (
    MoonEvents,
    MoonPosition,
    MustachesRange,
    NaturalTimeSnapshot,
    SunEvents,
    SunPosition,
    build_snapshot,
    mustaches_range,
    natural_light_phase,
    natural_moon_events,
    natural_moon_position,
    natural_sun_events,
    natural_sun_position,
)
from .core import NaturalDate

NaturalSunPosition = natural_sun_position
NaturalSunEvents = natural_sun_events
NaturalMoonPosition = natural_moon_position
NaturalMoonEvents = natural_moon_events
MustachesRange = mustaches_range

__all__ = [
    "MoonEvents",
    "MoonPosition",
    "MustachesRange",
    "MustachesRange",
    "NaturalDate",
    "NaturalMoonEvents",
    "NaturalMoonPosition",
    "NaturalSunEvents",
    "NaturalSunPosition",
    "NaturalTimeSnapshot",
    "SunEvents",
    "SunPosition",
    "build_snapshot",
    "mustaches_range",
    "natural_light_phase",
    "natural_moon_events",
    "natural_moon_position",
    "natural_sun_events",
    "natural_sun_position",
]
