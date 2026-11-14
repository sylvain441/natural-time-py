"""The Natural Time calendar: an instant, a longitude, and nothing else.

Every instant is an integer of Unix milliseconds, as in natural-time-js. The
arithmetic below repeats the JavaScript reference operation for operation, so
both give the same answer down to the last bit of a float.
"""

from __future__ import annotations

import math
import time as clock
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from numbers import Real

import astronomy

MILLISECONDS_PER_DAY = 86_400_000
# 2012-12-21T12:00:00Z, the noon that closed artificial time. Year 001 opens
# here at longitude 180, and half a day later at the meridian.
END_OF_ARTIFICIAL_TIME = 1_356_091_200_000

# Floats cannot hold 73.57: times 100 it is 7356.999999999999, and a plain cut would
# move the observer to 73.56. One part in a million million, added before the cut,
# puts it back. Same hair as JS.
_HAIR = 1.000000000001

_J2000 = 946_728_000_000  # 2000-01-01T12:00:00Z, where the engine counts from
_JS_DATE_LIMIT = 8_640_000_000_000_000  # what a JS Date can hold, either side of 1970
_UNIX_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)

Moment = datetime | int | float | str


def astro_time(unix_ms: int) -> astronomy.Time:
    return astronomy.Time((unix_ms - _J2000) / MILLISECONDS_PER_DAY)


def unix_ms_of(time: astronomy.Time) -> int:
    # Truncated toward zero, as JS `new Date(number)` does
    return math.trunc(_J2000 + time.ut * MILLISECONDS_PER_DAY)


def december_solstice(year: int) -> int:
    return unix_ms_of(astronomy.Seasons(year).dec_solstice)


def june_solstice(year: int) -> int:
    return unix_ms_of(astronomy.Seasons(year).jun_solstice)


def utc_year(unix_ms: int) -> int:
    # UTC year: the sky does not care which time zone the machine was sold in.
    # Hinnant's civil-from-days, cut down to the year: integers only, any century.
    era, day_of_era = divmod(unix_ms // MILLISECONDS_PER_DAY + 719_468, 146_097)
    year_of_era = (day_of_era - day_of_era // 1460 + day_of_era // 36_524 - day_of_era // 146_096) // 365
    day_of_year = day_of_era - (365 * year_of_era + year_of_era // 4 - year_of_era // 100)
    return era * 400 + year_of_era + ((5 * day_of_year + 2) // 153 >= 10)


def _new_year_noon(solstice: int) -> int:
    day, rest = divmod(solstice, MILLISECONDS_PER_DAY)
    return (day + (rest >= MILLISECONDS_PER_DAY // 2)) * MILLISECONDS_PER_DAY + MILLISECONDS_PER_DAY // 2


@lru_cache(maxsize=1024)
def _year_context(artificial_year: int, longitude: float) -> tuple[int, int]:
    start = _new_year_noon(december_solstice(artificial_year))
    end = _new_year_noon(december_solstice(artificial_year + 1))
    return math.trunc(start + (-longitude + 180) * MILLISECONDS_PER_DAY / 360), (end - start) // MILLISECONDS_PER_DAY


def is_real(value: object) -> bool:
    return isinstance(value, Real) and not isinstance(value, bool)


def unix_ms(moment: Moment | None) -> int:
    """Unix milliseconds of a moment. A number is always milliseconds; None is now."""
    if moment is None:
        return clock.time_ns() // 1_000_000
    if isinstance(moment, str):
        moment = datetime.fromisoformat(moment)
    if isinstance(moment, datetime):
        # A naive datetime is read as UTC: no time zones here, a longitude is enough
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        micro = (moment - _UNIX_EPOCH) // timedelta(microseconds=1)
        # Toward zero, like a JS Date, even before 1970
        return micro // 1000 if micro >= 0 else -(-micro // 1000)
    if not is_real(moment):
        raise TypeError(f"Expected a datetime, Unix milliseconds, an ISO string or None, got {moment!r}")
    if not -_JS_DATE_LIMIT <= moment <= _JS_DATE_LIMIT:
        raise ValueError(f"Invalid Unix milliseconds: {moment!r}")
    return math.trunc(moment)


def time_of_event(nadir: int, event: int) -> float | None:
    if not nadir <= event <= nadir + MILLISECONDS_PER_DAY:
        return None
    return (event - nadir) * (360 / MILLISECONDS_PER_DAY)


@dataclass(frozen=True, init=False, order=True)
class NaturalDate:
    """An instant read at a longitude: 13 moons of 28 days, and the sun at 360° a day.

    `precision` is the number of longitude decimals the clock runs on (0: one zone
    per degree), or `math.inf` for the exact longitude. Instances order by instant.
    """

    unix_time: int
    longitude: float
    precision: int | float
    effective_longitude: float
    year: int
    moon: int
    week: int
    week_of_moon: int
    day: int
    day_of_year: int
    day_of_moon: int
    day_of_week: int
    is_rainbow_day: bool
    time: float
    year_start: int
    year_duration: int
    nadir: int

    def __init__(self, date: Moment | None = None, longitude: float | None = None, precision: int | float = 0) -> None:
        if longitude is None:
            longitude = 0.0
        if not (is_real(longitude) and -180 <= longitude <= 180):
            raise ValueError(f"Longitude must be between -180 and +180, got {longitude!r}")
        if not (is_real(precision) and precision >= 0 and (precision == math.inf or float(precision).is_integer())):
            raise ValueError(f"Precision must be a non-negative integer or math.inf, got {precision!r}")

        unix_time = unix_ms(date)
        longitude = float(longitude or 0)  # -0.0 too: the meridian has one side
        if precision != math.inf:
            precision = int(precision)
            effective = math.trunc(longitude * 10**precision * _HAIR) / 10**precision
        else:
            effective = longitude

        year_start, year_duration = _year_context(utc_year(unix_time) - 1, effective)
        if unix_time - year_start >= year_duration * MILLISECONDS_PER_DAY:
            year_start, year_duration = _year_context(utc_year(unix_time), effective)

        days = (unix_time - year_start) / MILLISECONDS_PER_DAY
        day_of_year = math.floor(days) + 1
        nadir = year_start + math.floor(days) * MILLISECONDS_PER_DAY

        # Frozen to the world: the constructor is the only hand that writes
        vars(self).update(
            unix_time=unix_time,
            longitude=longitude,
            precision=precision,
            effective_longitude=effective,
            year=utc_year(year_start) - utc_year(END_OF_ARTIFICIAL_TIME) + 1,
            moon=math.floor(days / 28) + 1,
            week=math.floor(days / 7) + 1,
            week_of_moon=math.floor(days / 7) % 4 + 1,
            day=math.floor(
                (unix_time - (END_OF_ARTIFICIAL_TIME + (-effective + 180) * MILLISECONDS_PER_DAY / 360))
                / MILLISECONDS_PER_DAY
            ),
            day_of_year=day_of_year,
            day_of_moon=math.floor(days) % 28 + 1,
            day_of_week=math.floor(days) % 7 + 1,
            is_rainbow_day=day_of_year > 13 * 28,
            time=(unix_time - nadir) * 360 / MILLISECONDS_PER_DAY,
            year_start=year_start,
            year_duration=year_duration,
            nadir=nadir,
        )

    def as_datetime(self) -> datetime:
        """The same instant in artificial time, for whoever still needs it (years 1 to 9999 only)."""
        return _UNIX_EPOCH + timedelta(milliseconds=self.unix_time)

    def get_time_of_event(self, event: Moment) -> float | None:
        """Degrees of an instant within this natural day, or None when it falls outside."""
        return time_of_event(self.nadir, unix_ms(event))

    def to_year_string(self) -> str:
        return f"{'-' if self.year < 0 else ''}{abs(self.year):03d}"

    def to_moon_string(self) -> str:
        return f"{self.moon:02d}"

    def to_day_of_moon_string(self) -> str:
        return f"{self.day_of_moon:02d}"

    def to_date_string(self, separator: str = ")") -> str:
        if self.is_rainbow_day:
            return f"{self.to_year_string()}{separator}RAINBOW{'+' if self.day_of_year == 366 else ''}"
        return f"{self.to_year_string()}{separator}{self.to_moon_string()}{separator}{self.to_day_of_moon_string()}"

    def to_time_string(self, decimals: int = 2) -> str:
        """`202°63`: cut to `decimals`, never rounded: it is 202° until the sun reaches 203°."""
        decimals = max(0, math.trunc(decimals))
        scale = 10**decimals
        # The hair added before the cut repairs floats (20263.999999999996 is 20264);
        # it is far thinner than a millisecond of sun
        total = math.floor(self.time * scale + 1e-6)
        whole, fraction = total // scale % 360, total % scale
        return f"{whole:03d}°" + (f"{fraction:0{decimals}d}" if decimals else "")

    def to_longitude_string(self, decimals: int | None = None) -> str:
        """`NT+2.3`: the longitude as given, cut (never rounded) to `decimals`, `precision` by default.

        NTZ is NT+0, and only that: what is left once the decimals are cut is zero.
        """
        if decimals is None:
            decimals = self.precision if self.precision != math.inf else 0
        decimals = max(0, math.trunc(decimals))
        scale = 10**decimals
        scaled = math.trunc(abs(self.longitude) * scale * _HAIR)
        if scaled == 0:
            return "NTZ"
        sign = "+" if self.longitude >= 0 else "-"
        return f"NT{sign}{math.floor(scaled / scale)}" + (f".{scaled % scale:0{decimals}d}" if decimals else "")

    def to_string(self) -> str:
        return f"{self.to_date_string()} {self.to_time_string()} {self.to_longitude_string()}"
