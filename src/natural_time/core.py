"""Core Natural Time calendar calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from math import isfinite, trunc
from typing import Any

from .seasons import december_solstice

MILLISECONDS_PER_DAY = 86_400_000
END_OF_ARTIFICIAL_TIME = int(datetime(2012, 12, 21, 12, tzinfo=UTC).timestamp() * 1000)


def _coerce_unix_ms(value: datetime | int | float | str | None) -> int:
    if value is None:
        return int(datetime.now(UTC).timestamp() * 1000)

    if isinstance(value, datetime):
        date = value if value.tzinfo else value.replace(tzinfo=UTC)
        return int(date.timestamp() * 1000)

    if isinstance(value, int | float):
        if not isfinite(value):
            raise ValueError("Invalid timestamp provided")
        return int(value if abs(value) >= 10_000_000_000 else value * 1000)

    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        date = datetime.fromisoformat(text)
        if date.tzinfo is None:
            date = date.replace(tzinfo=UTC)
        return int(date.timestamp() * 1000)

    raise TypeError("Argument must be a datetime, timestamp, ISO string, or None")


def _utc_datetime(unix_ms: int) -> datetime:
    return datetime.fromtimestamp(unix_ms / 1000, UTC)


def _truncate_longitude(longitude: float, precision: float) -> float:
    if precision == float("inf"):
        return longitude
    factor = 10 ** int(precision)
    return trunc(longitude * factor) / factor


def _new_year_noon(solstice: datetime) -> int:
    day = solstice.date()
    if solstice.hour >= 12:
        day = day + timedelta(days=1)
    return int(datetime(day.year, day.month, day.day, 12, tzinfo=UTC).timestamp() * 1000)


@lru_cache(maxsize=4096)
def _calculate_year_context(artificial_year: int, longitude: float) -> tuple[int, int]:
    start_new_year = _new_year_noon(december_solstice(artificial_year))
    end_new_year = _new_year_noon(december_solstice(artificial_year + 1))
    start = int(start_new_year + (-longitude + 180) * MILLISECONDS_PER_DAY / 360)
    duration = int((end_new_year - start_new_year) / MILLISECONDS_PER_DAY)
    return start, duration


@dataclass(frozen=True)
class NaturalDate:
    """Gregorian moment translated into the Natural Time calendar."""

    unix_time: int
    longitude: float = 0
    precision: float = 0
    effective_longitude: float = 0
    year: int = 0
    moon: int = 0
    week: int = 0
    week_of_moon: int = 0
    day: int = 0
    day_of_year: int = 0
    day_of_moon: int = 0
    day_of_week: int = 0
    is_rainbow_day: bool = False
    time: float = 0
    year_start: int = 0
    year_duration: int = 0
    nadir: int = 0

    MILLISECONDS_PER_DAY = MILLISECONDS_PER_DAY
    END_OF_ARTIFICIAL_TIME = END_OF_ARTIFICIAL_TIME

    def __init__(
        self,
        date: datetime | int | float | str | None = None,
        longitude: float | None = None,
        precision: float = 0,
    ) -> None:
        if longitude is not None and (not isinstance(longitude, int | float) or longitude < -180 or longitude > 180):
            raise ValueError("Longitude must be between -180 and +180")

        unix_time = _coerce_unix_ms(date)
        raw_longitude = float(longitude or 0)
        effective_longitude = _truncate_longitude(raw_longitude, precision)
        date_obj = _utc_datetime(unix_time)

        year_start, year_duration = _calculate_year_context(date_obj.year - 1, effective_longitude)
        if unix_time - year_start >= year_duration * MILLISECONDS_PER_DAY:
            year_start, year_duration = _calculate_year_context(date_obj.year, effective_longitude)

        time_since_local_year_start = (unix_time - year_start) / MILLISECONDS_PER_DAY
        end_year = _utc_datetime(END_OF_ARTIFICIAL_TIME).year
        year = _utc_datetime(year_start).year - end_year + 1
        day = trunc(
            (unix_time - (END_OF_ARTIFICIAL_TIME + (-effective_longitude + 180) * MILLISECONDS_PER_DAY / 360))
            / MILLISECONDS_PER_DAY
        )
        day_of_year = int(time_since_local_year_start // 1) + 1
        nadir = year_start + int(time_since_local_year_start // 1) * MILLISECONDS_PER_DAY

        object.__setattr__(self, "unix_time", unix_time)
        object.__setattr__(self, "longitude", raw_longitude)
        object.__setattr__(self, "precision", precision)
        object.__setattr__(self, "effective_longitude", effective_longitude)
        object.__setattr__(self, "year", year)
        object.__setattr__(self, "moon", int(time_since_local_year_start // 28) + 1)
        object.__setattr__(self, "week", int(time_since_local_year_start // 7) + 1)
        object.__setattr__(self, "week_of_moon", int(time_since_local_year_start // 7) % 4 + 1)
        object.__setattr__(self, "day", day)
        object.__setattr__(self, "day_of_year", day_of_year)
        object.__setattr__(self, "day_of_moon", int(time_since_local_year_start // 1) % 28 + 1)
        object.__setattr__(self, "day_of_week", int(time_since_local_year_start // 1) % 7 + 1)
        object.__setattr__(self, "is_rainbow_day", day_of_year > 13 * 28)
        object.__setattr__(self, "time", (unix_time - nadir) * 360 / MILLISECONDS_PER_DAY)
        object.__setattr__(self, "year_start", year_start)
        object.__setattr__(self, "year_duration", year_duration)
        object.__setattr__(self, "nadir", nadir)

    @property
    def unixTime(self) -> int:
        return self.unix_time

    @property
    def effectiveLongitude(self) -> float:
        return self.effective_longitude

    @property
    def weekOfMoon(self) -> int:
        return self.week_of_moon

    @property
    def dayOfYear(self) -> int:
        return self.day_of_year

    @property
    def dayOfMoon(self) -> int:
        return self.day_of_moon

    @property
    def dayOfWeek(self) -> int:
        return self.day_of_week

    @property
    def isRainbowDay(self) -> bool:
        return self.is_rainbow_day

    @property
    def yearStart(self) -> int:
        return self.year_start

    @property
    def yearDuration(self) -> int:
        return self.year_duration

    def as_datetime(self) -> datetime:
        return _utc_datetime(self.unix_time)

    def get_time_of_event(self, event: datetime | int | float | str) -> float | bool:
        event_time = _coerce_unix_ms(event)
        if event_time < self.nadir or event_time > self.nadir + MILLISECONDS_PER_DAY:
            return False
        return (event_time - self.nadir) * (360 / MILLISECONDS_PER_DAY)

    def getTimeOfEvent(self, event: datetime | int | float | str) -> float | bool:
        return self.get_time_of_event(event)

    def to_year_string(self) -> str:
        sign = "-" if self.year < 0 else ""
        return f"{sign}{abs(self.year):03d}"

    def to_moon_string(self) -> str:
        return f"{self.moon:02d}"

    def to_day_of_moon_string(self) -> str:
        return f"{self.day_of_moon:02d}"

    def to_date_string(self, separator: str = ")") -> str:
        if self.is_rainbow_day:
            suffix = "+" if self.day_of_year == 366 else ""
            return f"{self.to_year_string()}{separator}RAINBOW{suffix}"
        return f"{self.to_year_string()}{separator}{self.to_moon_string()}{separator}{self.to_day_of_moon_string()}"

    def to_time_string(self, decimals: int = 2, rounding: float = 0.01) -> str:
        natural_time = self.time
        if rounding > 0:
            natural_time = int(natural_time / rounding + 0.5) * rounding
            if natural_time >= 360:
                natural_time = 0
        integer_part = f"{int(natural_time):03d}"
        if decimals <= 0:
            return f"{integer_part}°"
        decimal_part = f"{natural_time % 1:.{decimals}f}".split(".", 1)[1].ljust(decimals, "0")
        return f"{integer_part}°{decimal_part}"

    def to_longitude_string(self, decimals: int | None = None) -> str:
        if decimals is None:
            decimals = int(self.precision) if self.precision != float("inf") else 0
        display_longitude = self.effective_longitude if self.precision != float("inf") else self.longitude
        if abs(display_longitude) < 1:
            return "NTZ"
        sign = "+" if display_longitude >= 0 else "-"
        abs_longitude = abs(display_longitude)
        integer_part = str(trunc(abs_longitude))
        if decimals <= 0:
            return f"NT{sign}{integer_part}"
        decimal_part = f"{abs_longitude % 1:.{decimals}f}".split(".", 1)[1]
        return f"NT{sign}{integer_part}.{decimal_part}"

    def to_string(self) -> str:
        return f"{self.to_date_string()} {self.to_time_string()} {self.to_longitude_string()}"

    def toDateString(self, separator: str = ")") -> str:
        return self.to_date_string(separator)

    def toTimeString(self, decimals: int = 2, rounding: float = 0.01) -> str:
        return self.to_time_string(decimals, rounding)

    def toLongitudeString(self, decimals: int | None = None) -> str:
        return self.to_longitude_string(decimals)

    def toYearString(self) -> str:
        return self.to_year_string()

    def toMoonString(self) -> str:
        return self.to_moon_string()

    def toDayOfMoonString(self) -> str:
        return self.to_day_of_moon_string()

    def toString(self) -> str:
        return self.to_string()

    def as_dict(self) -> dict[str, Any]:
        return {
            "unix_time": self.unix_time,
            "longitude": self.longitude,
            "precision": self.precision,
            "effective_longitude": self.effective_longitude,
            "year": self.year,
            "moon": self.moon,
            "week": self.week,
            "week_of_moon": self.week_of_moon,
            "day": self.day,
            "day_of_year": self.day_of_year,
            "day_of_moon": self.day_of_moon,
            "day_of_week": self.day_of_week,
            "is_rainbow_day": self.is_rainbow_day,
            "time": self.time,
            "year_start": self.year_start,
            "year_duration": self.year_duration,
            "nadir": self.nadir,
            "date_string": self.to_date_string(),
            "time_string": self.to_time_string(),
            "longitude_string": self.to_longitude_string(),
            "string": self.to_string(),
        }
