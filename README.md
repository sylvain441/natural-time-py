# natural-time-py

Python port of the Natural Time paradigm, prepared for Home Assistant.

## Status

This repository is a Python port of [`natural-time-js`](https://github.com/sylvain441/natural-time-js). The JavaScript library is the reference implementation. This port is intended to follow it closely, especially for the Natural Time calendar model and the Astronomy Engine based solar/lunar calculations.

The port has initial tests and golden-vector spot checks, but it has not yet received a deep independent review. Treat it as an early implementation until the full JavaScript golden vector suite is automated in CI.

## Astronomy Reference

The package uses [Cosine Kitty Astronomy Engine](https://github.com/cosinekitty/astronomy/tree/master/source/python), matching the astronomical engine used by `natural-time-js`. It provides:

- `NaturalDate`: natural year, moon, day, rainbow day, nadir, and degree time.
- `natural_sun_position`: solar azimuth and signed elevation.
- `natural_sun_events`: sunrise, sunset, night, and golden-hour thresholds in natural degrees.
- `natural_moon_position`: approximate moon altitude and phase.
- `build_snapshot`: one object gathering the values a Home Assistant coordinator needs.

The calendar core follows the JavaScript implementation closely, including longitude precision modes.

## Example

```python
from datetime import datetime, timezone

from natural_time import NaturalDate, natural_sun_position

nd = NaturalDate(datetime.now(timezone.utc), longitude=2.3522, precision=float("inf"))
sun = natural_sun_position(nd, latitude=48.8566)

print(nd.to_string())
print(sun.azimuth, sun.elevation)
```

## Tests

```bash
python -m unittest
```
