# natural-time-py

[Natural Time](https://naturaltime.app/) in Python: the time is the position of the sun seen from a longitude, 360° a day, 0° at true midnight and 180° at true noon. The year starts at the winter solstice and holds 13 moons of 28 days, plus one or two Rainbow days. No time zones, no daylight saving: a longitude is enough.

The specification lives in [`natural-time`](https://github.com/sylvain441/natural-time). The reference implementation is [`natural-time-js`](https://github.com/sylvain441/natural-time-js): this package repeats its arithmetic operation for operation and answers like it on every one of its golden vectors. Born for [Home Assistant](https://github.com/sylvain441/natural-time-ha).

## Install

```bash
pip install natural-time-py
```

Python 3.11 or later. The only dependency is [Astronomy Engine](https://github.com/cosinekitty/astronomy), the same engine natural-time-js uses, pinned to the same version (2.1.19).

## Use

```python
import math
from natural_time import NaturalDate, build_snapshot, natural_sun_events

paris = NaturalDate("2026-04-23T14:56:00Z", longitude=2.3522, precision=1)
paris.to_string()          # '014)05)10 226°30 NT+2.3'
paris.time                 # degrees since the natural midnight

natural_sun_events(paris, latitude=48.8566).sunrise  # 73.46...

snapshot = build_snapshot(latitude=48.8566, longitude=2.3522, precision=math.inf)
snapshot.light_phase       # 'night', 'dawn', 'golden_morning', 'day', 'golden_evening' or 'dusk'
```

### `NaturalDate(date=None, longitude=None, precision=0)`

- `date`: Unix **milliseconds** (always milliseconds, as in JavaScript; fractions are cut toward zero), a `datetime` (naive means UTC), an ISO 8601 string (without an offset it is UTC, unlike JavaScript which reads it as local time), or `None` for now. `0` is 1970-01-01T00:00:00Z. Booleans, NaN and infinities are refused.
- `longitude`: degrees in [-180, 180], `None` for 0.
- `precision`: how many longitude decimals the clock runs on. `0` gives one zone per degree (2.3522 runs as 2), `1` one per tenth (2.3), `math.inf` the exact longitude.

Fields: `unix_time`, `longitude`, `precision`, `effective_longitude` (the longitude cut to `precision`), `year`, `moon`, `week`, `week_of_moon`, `day` (days since 2012-12-21), `day_of_year`, `day_of_moon`, `day_of_week`, `is_rainbow_day`, `time` (degrees), `year_start`, `year_duration`, `nadir` (Unix milliseconds of the natural midnight).

A `NaturalDate` is immutable, hashable, and orders by instant.

| Method | Example | |
|---|---|---|
| `to_string()` | `014)05)10 226°30 NT+2.3` | |
| `to_date_string(separator=")")` | `014)05)10`, `014)RAINBOW`, `001)RAINBOW+` | |
| `to_time_string(decimals=2)` | `226°30` | cut to `decimals`, never rounded: `202.996` reads `202°99`, the last instant of the day `359°99` |
| `to_longitude_string(decimals=None)` | `NT+2.3`, `NT-0.7`, `NTZ` | the longitude as given, cut (never rounded) to `decimals`, `precision` by default (0 when exact); `NTZ` when nothing is left |
| `to_year_string()`, `to_moon_string()`, `to_day_of_moon_string()` | `014`, `05`, `10` | |
| `get_time_of_event(moment)` | `73.46` | degrees of an instant within this natural day, `None` outside it |
| `as_datetime()` | | back to artificial time, years 1 to 9999 |

### The sky

Each function takes a `NaturalDate` and a `latitude` in [-90, 90], observes from the date's longitude, and answers in natural degrees.

- `natural_sun_position` → `SunPosition(azimuth, elevation, altitude, highest_altitude, is_above_horizon)`. `elevation` is signed, `altitude` stops at the horizon.
- `natural_sun_events` → `SunEvents(sunrise, sunset, night_start, night_end, morning_golden_hour, evening_golden_hour)`. Night is the sun at -12°, golden hours at 6°. When the sun never crosses the line, the polar day reads 0 and 360, the polar night 180.
- `natural_moon_position` → `MoonPosition(altitude, phase)`.
- `natural_moon_events` → `MoonEvents(moonrise, moonset, highest_altitude)`; 0 when the moon skips the day.
- `mustaches_range` → `MustachesRange(winter_sunrise, winter_sunset, summer_sunrise, summer_sunset, average_mustache_angle)`: sunrise and sunset at both solstices of the UTC year. natural-time-js answers five zeros when something fails here; this package raises instead.
- `natural_light_phase(natural_date, sun_events=None)` and `build_snapshot(date=None, *, latitude, longitude, precision=0)` are Python only: the light phase, and everything a home needs in one `NaturalTimeSnapshot`.
- `reset_caches()` forgets the years, days and mustaches already computed.

## Precision

Every instant is an integer of Unix milliseconds, and every conversion truncates toward zero as a JavaScript `Date` does. Calendar fields, strings and `time` are identical to natural-time-js, bit for bit. Sun and moon events agree within a millisecond (4e-6°), positions within 1e-10°. The calendar runs as far as the engine finds solstices, from about 20 000 BCE to 12 000 CE; beyond, it raises, as natural-time-js throws.

## Golden vectors

`tests/data/natural-time-vectors.jsonl` is what natural-time-js answers on 1154 cases: year boundaries at both sides of the date line, one full turn of the dial, every longitude label, the sky from pole to pole, and dates far from now. Line 1 is `{"meta": ...}` with the tolerances, then one flat JSON object per case. The file is never edited here: it is a byte-identical copy of `natural-time-js/vectors/natural-time-vectors.jsonl`. To refresh it:

```bash
cd ../natural-time-js && npm run build && npm run vectors
cp vectors/natural-time-vectors.jsonl ../natural-time-py/tests/data/
```

## Tests

```bash
pip install -e '.[test]'
pytest
```

About 15 seconds. `tests/test_vectors.py` replays the 1154 golden vectors (and checks the file's sha256), `tests/test_core.py` covers inputs, validation, labels, caches and what Home Assistant reads, `tests/test_spec.py` is written from the specification alone. The run ends with the largest gap to natural-time-js per group of fields, so drift shows before it breaks. CI runs the same on Python 3.11, 3.12 and 3.13.
