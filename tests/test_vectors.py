"""Every field of every golden case, as natural-time-js answered it (see the generator for the call behind each field)."""

import hashlib
import json
import math
from pathlib import Path

import pytest

from natural_time import (
    NaturalDate,
    mustaches_range,
    natural_moon_events,
    natural_moon_position,
    natural_sun_events,
    natural_sun_position,
    reset_caches,
)

VECTORS = Path(__file__).parent / "data" / "natural-time-vectors.jsonl"
# Copied from natural-time-js/vectors/: refresh both with `npm run vectors` there, then cp here and update this hash.
VECTORS_SHA256 = "ed9f1ca9ed0ce8fae42267193fa5c8a4a461e93ac4afeeb7bcee7c0a7da665b7"


def _load():
    lines = VECTORS.read_text(encoding="utf-8").splitlines()
    return json.loads(lines[0])["meta"], [(n, json.loads(line)) for n, line in enumerate(lines[1:], start=2)]


# A missing file must fail (test_vectors_file_is_there), not silently collect nothing
META, CASES = _load() if VECTORS.is_file() else ({"tolerances": {}, "event_deg": [], "angle_deg": []}, [])
TOLERANCES = META["tolerances"]
EVENT_DEG, ANGLE_DEG = set(META["event_deg"]), set(META["angle_deg"])

CALENDAR_INTS = ["year", "moon", "week", "week_of_moon", "day", "day_of_year", "day_of_moon", "day_of_week",
                 "year_start", "year_duration", "nadir"]


def _calendar(nd):
    fields = {name: getattr(nd, name) for name in CALENDAR_INTS}
    fields.update(
        is_rainbow_day=nd.is_rainbow_day,
        time_deg=nd.time,
        effective_longitude=nd.effective_longitude,
        date_string=nd.to_date_string(),
        time_string=nd.to_time_string(),
        time_string_whole=nd.to_time_string(0),
        longitude_string=nd.to_longitude_string(),
        longitude_string_2=nd.to_longitude_string(2),
        string=nd.to_string(),
    )
    return fields


def _sky(nd, latitude):
    sp, se = natural_sun_position(nd, latitude), natural_sun_events(nd, latitude)
    mp, me = natural_moon_position(nd, latitude), natural_moon_events(nd, latitude)
    mu = mustaches_range(nd, latitude)
    return {
        "sun_azimuth": sp.azimuth, "sun_elevation": sp.elevation, "sun_altitude": sp.altitude,
        "sun_highest_altitude": sp.highest_altitude, "sun_is_above_horizon": sp.is_above_horizon,
        "sunrise_deg": se.sunrise, "sunset_deg": se.sunset, "night_start_deg": se.night_start,
        "night_end_deg": se.night_end, "morning_golden_deg": se.morning_golden_hour,
        "evening_golden_deg": se.evening_golden_hour,
        "moon_altitude": mp.altitude, "moon_phase_deg": mp.phase,
        "moonrise_deg": me.moonrise, "moonset_deg": me.moonset, "moon_highest_altitude": me.highest_altitude,
        "mustache_winter_sunrise_deg": mu.winter_sunrise, "mustache_winter_sunset_deg": mu.winter_sunset,
        "mustache_summer_sunrise_deg": mu.summer_sunrise, "mustache_summer_sunset_deg": mu.summer_sunset,
        "mustache_angle_deg": mu.average_mustache_angle,
    }


def _group(field):
    if field in EVENT_DEG:
        return "event_deg"
    if field in ANGLE_DEG:
        return "angle_deg"
    return "time_deg" if field == "time_deg" else "effective_longitude"


def test_vectors_file_is_there():
    assert VECTORS.is_file(), f"Golden vectors missing: {VECTORS}"


def test_the_vectors_cover_the_sky_before_1970():
    assert any(case["unix_ms"] <= 0 and case["sun_elevation"] is not None for _, case in CASES)


def test_case_count():
    assert len(CASES) == META.get("cases")


@pytest.mark.parametrize("line, case", CASES, ids=[f"line{n}" for n, _ in CASES])
def test_case(line, case, deltas):
    reset_caches()  # as the generator does: each case answers for itself
    precision = math.inf if case["precision"] == "exact" else case["precision"]
    nd = NaturalDate(case["unix_ms"], case["longitude"], precision)
    received = _calendar(nd)

    latitude = case["latitude"]  # every case has one: KeyError or None is a broken file
    assert latitude is not None, f"vectors line {line} has no latitude"
    received.update(_sky(nd, latitude))

    failures = []
    for field, got in received.items():
        want = case[field]
        if field in ("time_deg", "effective_longitude") or field in EVENT_DEG or field in ANGLE_DEG:
            group = _group(field)
            delta = abs(want - got)
            if delta > deltas.get(group, (-1, ""))[0]:
                deltas[group] = (delta, f"line {line} {field}")
            ok = delta <= TOLERANCES[group]
        else:
            ok = want == got and type(want) is type(got)
        if not ok:
            failures.append(f"  {field}: expected {want!r}, received {got!r}")
    expected_fields = {k for k in case if k not in ("unix_ms", "longitude", "precision", "latitude")}
    missing = expected_fields - received.keys()
    if missing:
        failures.append(f"  fields never compared: {sorted(missing)}")
    assert not failures, f"vectors line {line} ({case['unix_ms']}, lon {case['longitude']}, precision {case['precision']}, lat {latitude}):\n" + "\n".join(failures)


def test_vectors_are_the_ones_from_natural_time_js():
    assert hashlib.sha256(VECTORS.read_bytes()).hexdigest() == VECTORS_SHA256
