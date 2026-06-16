# natural-time-py

Python port of the Natural Time paradigm, prepared for Home Assistant.

## Status

This repository is a Python port of [`natural-time-js`](https://github.com/sylvain441/natural-time-js). The JavaScript library is the reference implementation. This port is intended to follow it closely, especially for the Natural Time calendar model and the Astronomy Engine based solar/lunar calculations.

The port has initial tests, a golden-vector spot check, and has been compared locally against the JavaScript reference across a broader set of calendar, solar, lunar, longitude precision, and polar-latitude cases. It has not yet received a deep independent review or CI-backed parity suite, so treat it as an early implementation.

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
PYTHONPATH=src python -m unittest discover -s tests
```
