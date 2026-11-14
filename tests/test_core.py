"""What the golden vectors cannot say: inputs, validation, labels, caches and what Home Assistant reads."""

import dataclasses
import math
import os
import time as clock
from datetime import UTC, datetime, timedelta, timezone
from fractions import Fraction

import astronomy
import pytest

from natural_time import (
    NaturalDate,
    SunEvents,
    build_snapshot,
    mustaches_range,
    natural_light_phase,
    natural_moon_events,
    natural_moon_position,
    natural_sun_events,
    natural_sun_position,
    reset_caches,
)
from natural_time import ephemeris
from natural_time.core import MILLISECONDS_PER_DAY as DAY
from natural_time.core import unix_ms

PARIS = {"latitude": 48.8566, "longitude": 2.3522}
APRIL_23 = 1_776_956_160_000  # 2026-04-23T14:56:00Z
SKY_FUNCTIONS = [natural_sun_position, natural_sun_events, natural_moon_position, natural_moon_events, mustaches_range]


@pytest.fixture(autouse=True)
def fresh_caches():
    reset_caches()


def at_degrees(degrees: float, longitude: float = 0, precision: float = 0) -> NaturalDate:
    """The instant a given angle of the same natural day as APRIL_23 (whole milliseconds only)."""
    nadir = NaturalDate(APRIL_23, longitude, precision).nadir
    return NaturalDate(nadir + round(degrees * DAY / 360), longitude, precision)


# --- Input coercion -----------------------------------------------------------------------------

@pytest.mark.parametrize("moment, expected", [
    (0, 0),
    (0.0, 0),
    (APRIL_23, APRIL_23),
    (1.9, 1),
    (-1.9, -1),
    (Fraction(7, 2), 3),
    (datetime(1970, 1, 1, tzinfo=UTC), 0),
    (datetime(2026, 4, 23, 14, 56), APRIL_23),  # naive: UTC, whatever the machine's zone
    (datetime(2026, 4, 23, 14, 56, tzinfo=UTC), APRIL_23),
    (datetime(2026, 4, 23, 16, 56, tzinfo=timezone(timedelta(hours=2))), APRIL_23),
    (datetime(1970, 1, 1, 0, 0, 0, 1999, tzinfo=UTC), 1),
    (datetime(1969, 12, 31, 23, 59, 59, 998001, tzinfo=UTC), -1),  # toward zero, like a JS Date
    ("2026-04-23T14:56:00Z", APRIL_23),
    ("2026-04-23T14:56:00+00:00", APRIL_23),
    ("2026-04-23T16:56:00+02:00", APRIL_23),
    ("2026-04-23T14:56:00", APRIL_23),  # no offset: UTC (JS would say local time)
    ("2026-04-23", 1_776_902_400_000),
])
def test_unix_ms(moment, expected):
    assert unix_ms(moment) == expected
    assert type(unix_ms(moment)) is int
    assert NaturalDate(moment).unix_time == expected


def test_a_number_is_milliseconds_never_seconds():
    assert NaturalDate(1_776_956_160).unix_time == 1_776_956_160
    assert NaturalDate(1_776_956_160).to_date_string() == "-042)02)02"  # 20 days after the epoch, not in 2026


def test_zero_is_the_epoch_not_now():
    nd = NaturalDate(0)
    assert nd.unix_time == 0
    assert nd.as_datetime() == datetime(1970, 1, 1, tzinfo=UTC)


def test_none_is_now():
    before = clock.time_ns() // 1_000_000
    now = NaturalDate(None).unix_time
    assert before <= now <= clock.time_ns() // 1_000_000
    assert before <= NaturalDate().unix_time <= clock.time_ns() // 1_000_000


@pytest.mark.skipif(not hasattr(clock, "tzset"), reason="needs tzset")
def test_machine_time_zone_changes_nothing(monkeypatch):
    zone_free = NaturalDate(datetime(2026, 12, 31, 23, 30), 0).to_string()
    monkeypatch.setenv("TZ", "Pacific/Auckland")
    clock.tzset()
    try:
        assert NaturalDate(datetime(2026, 12, 31, 23, 30), 0).to_string() == zone_free
        assert NaturalDate("2026-12-31T23:30:00", 0).to_string() == zone_free
    finally:
        monkeypatch.undo()
        clock.tzset()


@pytest.mark.parametrize("bad, error", [
    (True, TypeError),
    (False, TypeError),
    (b"0", TypeError),
    ([0], TypeError),
    (1j, TypeError),
    (float("nan"), ValueError),
    (float("inf"), ValueError),
    (-math.inf, ValueError),
    (8_640_000_000_000_001, ValueError),
    (-8_640_000_000_000_001, ValueError),
    ("garbage", ValueError),
    ("", ValueError),
])
def test_unix_ms_refuses(bad, error):
    with pytest.raises(error):
        unix_ms(bad)
    with pytest.raises(error):
        NaturalDate(bad)


def test_the_js_date_range_is_the_limit():
    assert unix_ms(8_640_000_000_000_000) == 8_640_000_000_000_000
    assert unix_ms(-8_640_000_000_000_000) == -8_640_000_000_000_000


def test_beyond_the_engine_it_raises():
    # Inside the JS Date range, but past the years where solstices can be found
    with pytest.raises(astronomy.Error):
        NaturalDate(8_640_000_000_000_000)


# --- Validation ---------------------------------------------------------------------------------

@pytest.mark.parametrize("longitude", [180.0001, -180.0001, 181, float("nan"), math.inf, True, "1", [1]])
def test_longitude_refused(longitude):
    with pytest.raises(ValueError):
        NaturalDate(APRIL_23, longitude)


@pytest.mark.parametrize("longitude", [-180, 180, 0, 179.9999])
def test_longitude_bounds_accepted(longitude):
    assert NaturalDate(APRIL_23, longitude).longitude == longitude


def test_longitude_defaults_to_the_meridian_and_has_no_negative_zero():
    for given in (None, 0, -0.0):
        nd = NaturalDate(APRIL_23, given)
        assert nd.longitude == 0 and math.copysign(1, nd.longitude) == 1
        assert nd.effective_longitude == 0 and math.copysign(1, nd.effective_longitude) == 1
    assert NaturalDate(APRIL_23, -0.4, 0).to_longitude_string() == "NTZ"


@pytest.mark.parametrize("precision", [-1, 1.5, float("nan"), -math.inf, True, "1", None])
def test_precision_refused(precision):
    with pytest.raises(ValueError):
        NaturalDate(APRIL_23, 2.3522, precision)


def test_precision_accepts_integral_floats_and_infinity():
    assert NaturalDate(APRIL_23, 2.3522, 2.0).precision == 2
    assert type(NaturalDate(APRIL_23, 2.3522, 2.0).precision) is int
    assert NaturalDate(APRIL_23, 2.3522, math.inf).effective_longitude == 2.3522


@pytest.mark.parametrize("latitude", [90.0001, -90.0001, float("nan"), math.inf, True, "45", None])
@pytest.mark.parametrize("sky", SKY_FUNCTIONS)
def test_latitude_refused(sky, latitude):
    with pytest.raises(ValueError):
        sky(NaturalDate(APRIL_23, 0), latitude)


@pytest.mark.parametrize("moment", [-1, 0, -86_400_000, -2_208_988_800_000, -30_610_224_000_000, -100_000_000_000_000])
@pytest.mark.parametrize("longitude", [0, -180, 180])
def test_the_sky_is_computed_before_1970(moment, longitude):
    nd = NaturalDate(moment, longitude)
    sun, events = natural_sun_position(nd, 45), natural_sun_events(nd, 45)
    assert -90 <= sun.elevation <= 90 and 0 <= sun.azimuth <= 360
    for angle in (events.sunrise, events.sunset, events.night_start, events.night_end,
                  events.morning_golden_hour, events.evening_golden_hour):
        assert 0 <= angle <= 360
    moon, moon_events = natural_moon_position(nd, 45), natural_moon_events(nd, 45)
    assert -90 <= moon.altitude <= 90 and 0 <= moon.phase <= 360
    for angle in (moon_events.moonrise, moon_events.moonset):
        assert angle is None or 0 <= angle <= 360
    mustaches = mustaches_range(nd, 45)
    assert 0 <= mustaches.winter_sunrise <= 360 and 0 <= mustaches.summer_sunset <= 360


@pytest.mark.parametrize("sky", SKY_FUNCTIONS)
def test_the_sky_before_1970_validates_its_inputs(sky):
    with pytest.raises(ValueError):
        sky(NaturalDate(-1, 0), 91)
    with pytest.raises(ValueError):
        sky(NaturalDate(0, 0), float("nan"))


def test_build_snapshot_refuses_invalid_inputs():
    with pytest.raises(ValueError):
        build_snapshot(APRIL_23, latitude=91, longitude=0)
    with pytest.raises(ValueError):
        build_snapshot(APRIL_23, latitude=0, longitude=181)
    with pytest.raises(ValueError):
        build_snapshot(APRIL_23, latitude=0, longitude=0, precision=-1)
    with pytest.raises(ValueError):
        build_snapshot(-1, latitude=91, longitude=0)
    with pytest.raises(TypeError):
        build_snapshot(APRIL_23, 48.8, 2.3)  # latitude and longitude are keyword-only


def test_build_snapshot_before_1970():
    snapshot = build_snapshot(-1, latitude=0, longitude=0)
    assert snapshot.natural_date.unix_time == -1
    assert -90 <= snapshot.sun_position.elevation <= 90


# --- NaturalDate as a value ---------------------------------------------------------------------

def test_immutable():
    nd = NaturalDate(APRIL_23, 2.3522, 1)
    for name in ("year", "unix_time", "time", "brand_new"):
        with pytest.raises(dataclasses.FrozenInstanceError):
            setattr(nd, name, 1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        del nd.year


def test_equal_dates_hash_alike():
    a, b = NaturalDate(APRIL_23, 2.3522, 1), NaturalDate(str(datetime.fromtimestamp(APRIL_23 / 1000, UTC)), 2.3522, 1)
    assert a == b and hash(a) == hash(b) and len({a, b}) == 1
    assert a != NaturalDate(APRIL_23, 2.3522, 2)
    assert a != NaturalDate(APRIL_23 + 1, 2.3522, 1)


def test_orders_by_instant_first():
    early_east, late_west = NaturalDate(1_000, 170), NaturalDate(2_000, -170)
    assert early_east < late_west and late_west > early_east and early_east <= early_east
    shuffled = [NaturalDate(t, 0) for t in (5_000, 1_000, 3_000, 4_000, 2_000)]
    assert [d.unix_time for d in sorted(shuffled)] == [1_000, 2_000, 3_000, 4_000, 5_000]


def test_as_datetime_is_utc_and_exact():
    assert NaturalDate(APRIL_23, 100).as_datetime() == datetime(2026, 4, 23, 14, 56, tzinfo=UTC)
    assert NaturalDate(-1, 0).as_datetime() == datetime(1969, 12, 31, 23, 59, 59, 999000, tzinfo=UTC)


# --- get_time_of_event --------------------------------------------------------------------------

def test_time_of_event():
    nd = NaturalDate(APRIL_23, 2.3522, math.inf)
    assert nd.get_time_of_event(nd.nadir) == 0
    assert nd.get_time_of_event(nd.nadir + DAY) == 360  # both ends belong to the day
    assert nd.get_time_of_event(nd.nadir + DAY // 2) == 180
    assert nd.get_time_of_event(nd.nadir + DAY // 4) == 90
    assert nd.get_time_of_event(nd.nadir - 1) is None
    assert nd.get_time_of_event(nd.nadir + DAY + 1) is None
    assert nd.get_time_of_event(nd.unix_time) == nd.time


def test_time_of_event_takes_any_moment():
    nd = NaturalDate(APRIL_23, 0)
    noon = datetime.fromtimestamp((nd.nadir + DAY // 2) / 1000, UTC)
    assert nd.get_time_of_event(noon) == 180
    assert nd.get_time_of_event(noon.isoformat()) == 180
    assert nd.get_time_of_event(noon.replace(tzinfo=None)) == 180
    with pytest.raises(TypeError):
        nd.get_time_of_event(True)


# --- Labels -------------------------------------------------------------------------------------

@pytest.mark.parametrize("longitude, precision, decimals, expected", [
    (0, 0, None, "NTZ"),
    (0.5, 0, None, "NTZ"),  # cut to 0 decimals, nothing left
    (-0.5, 0, None, "NTZ"),
    (-0.5, 1, None, "NT-0.5"),
    (0.25, 1, None, "NT+0.2"),
    (0.04, 1, None, "NTZ"),
    (0.25, 2, None, "NT+0.25"),
    (-0.04, 2, 1, "NTZ"),
    (-0.25, 2, 0, "NTZ"),
    (0.75, 0, None, "NTZ"),  # cut, never rounded to NT+1
    (0.75, 0, 1, "NT+0.7"),
    (-2.75, 1, None, "NT-2.7"),
    (-2.75, math.inf, None, "NT-2"),
    (-2.75, math.inf, 2, "NT-2.75"),
    (2.5, 0, 3, "NT+2.500"),  # as many decimals as asked, zeros kept
    (180, 1, None, "NT+180.0"),
    (-180, 0, None, "NT-180"),
    (-180, 2, None, "NT-180.00"),
])
def test_longitude_string(longitude, precision, decimals, expected):
    assert NaturalDate(APRIL_23, longitude, precision).to_longitude_string(decimals) == expected


def test_effective_longitude_is_cut_toward_zero():
    assert NaturalDate(APRIL_23, 2.75, 1).effective_longitude == 2.7
    assert NaturalDate(APRIL_23, -2.75, 1).effective_longitude == -2.7
    assert NaturalDate(APRIL_23, -2.75, 0).effective_longitude == -2


@pytest.mark.parametrize("degrees, decimals, expected", [
    (0, 2, "000°00"),
    (202.996, 2, "202°99"),  # cut, never rounded
    (202.994, 2, "202°99"),
    (202.636, 2, "202°63"),
    (202.64, 2, "202°64"),
    (0.29, 2, "000°29"),  # time * 100 is 28.999999999999996: the float is repaired
    (202.996, 3, "202°996"),
    (202.996, 0, "202°"),
    (359.999, 2, "359°99"),  # never 360
    (359.999, 0, "359°"),
    (359.999, 3, "359°999"),
    (9.996, 0, "009°"),
    (5.5, 3, "005°500"),
    (5.5, 6, "005°500000"),
    (99.995, 2, "099°99"),  # no carry across the hundreds
])
def test_time_string(degrees, decimals, expected):
    assert at_degrees(degrees).to_time_string(decimals) == expected


def test_time_string_default_is_two_decimals():
    nd = at_degrees(202.996)
    assert nd.to_time_string() == nd.to_time_string(2) == "202°99"


def test_time_string_takes_decimals_only():
    with pytest.raises(TypeError):
        at_degrees(202.996).to_time_string(2, 1)


def test_time_string_never_reads_360_in_the_last_millisecond():
    last = NaturalDate(NaturalDate(APRIL_23, 0).nadir + DAY - 1, 0)
    assert last.time < 360
    assert last.to_time_string() == "359°99"
    assert last.to_time_string(0) == "359°"
    assert last.to_string().split()[1] == "359°99"


# --- Rainbow days and years ---------------------------------------------------------------------

def test_rainbow_day_strings():
    # 2017-06-01 sits in a 366-day year
    long_year = NaturalDate("2017-06-01", 0)
    assert long_year.year_duration == 366
    start = long_year.year_start
    last_moon_day = NaturalDate(start + 363 * DAY + 5, 0)
    assert (last_moon_day.to_date_string(), last_moon_day.is_rainbow_day) == ("005)13)28", False)
    first_rainbow = NaturalDate(start + 364 * DAY + 5, 0)
    assert (first_rainbow.to_date_string(), first_rainbow.is_rainbow_day) == ("005)RAINBOW", True)
    second_rainbow = NaturalDate(start + 365 * DAY + 5, 0)
    assert (second_rainbow.to_date_string(), second_rainbow.is_rainbow_day) == ("005)RAINBOW+", True)
    assert second_rainbow.to_date_string("/") == "005/RAINBOW+"
    assert NaturalDate(start + 366 * DAY + 5, 0).to_date_string() == "006)01)01"


def test_a_365_day_year_has_a_single_rainbow_day():
    short_year = NaturalDate("2026-06-01", 0)
    assert short_year.year_duration == 365
    start = short_year.year_start
    assert NaturalDate(start + 364 * DAY + 5, 0).to_date_string().endswith("RAINBOW")
    assert NaturalDate(start + 365 * DAY + 5, 0).to_date_string().endswith("01)01")


@pytest.mark.parametrize("moment, year_string, date_string", [
    ("2012-12-21T11:59:59.999Z", "000", "000)RAINBOW"),
    ("2012-12-21T12:00:00Z", "001", "001)01)01"),
    ("2011-06-01T00:00:00Z", "-001", "-001)06)21"),
    ("1970-01-01T00:00:00Z", "-042", "-042)01)10"),
])
def test_year_strings(moment, year_string, date_string):
    nd = NaturalDate(moment, 180)
    assert nd.to_year_string() == year_string
    assert nd.to_date_string() == date_string


def test_years_beyond_three_digits_and_far_negative_years():
    assert NaturalDate("5000-06-01", 0).to_year_string() == "2988"
    far_past = NaturalDate(-100_000_000_000_000, 0)  # year -3211: no padding, no breakage
    assert far_past.year == -3211
    assert far_past.to_string().startswith("-3211)")
    assert far_past.day_of_year >= 1 and 1 <= far_past.moon <= 14


def test_parts_strings():
    nd = NaturalDate("2026-04-23T14:56:00Z", 2.3522, 1)
    assert (nd.to_year_string(), nd.to_moon_string(), nd.to_day_of_moon_string()) == ("014", "05", "10")
    assert nd.to_date_string("-") == "014-05-10"
    assert nd.to_string() == "014)05)10 226°30 NT+2.3"


# --- Caches -------------------------------------------------------------------------------------

def test_precision_zero_and_exact_give_different_suns():
    zone = NaturalDate(APRIL_23, 2.3522, 0)
    exact = NaturalDate(APRIL_23, 2.3522, math.inf)
    for first, second in ((zone, exact), (exact, zone)):
        reset_caches()
        a, b = natural_sun_events(first, 46), natural_sun_events(second, 46)
        assert a != b
    assert natural_sun_events(zone, 46) != natural_sun_events(exact, 46)
    assert zone.nadir != exact.nadir


def test_answers_do_not_depend_on_what_was_asked_before():
    dates = [NaturalDate(APRIL_23 + k * DAY // 3, lon, p) for k in range(4) for lon in (2.3522, -122.4) for p in (0, math.inf)]

    def everything(order):
        reset_caches()
        out = {}
        for i in order:
            d = dates[i]
            out[i] = (d, natural_sun_events(d, 46), natural_sun_events(d, -33), natural_moon_events(d, 46), mustaches_range(d, 46))
        return out

    forward = everything(range(len(dates)))
    backward = everything(reversed(range(len(dates))))
    assert forward == backward


def test_reset_caches_empties_every_cache():
    nd = NaturalDate(APRIL_23, 2.3522)
    natural_sun_events(nd, 46), natural_moon_events(nd, 46), mustaches_range(nd, 46)
    caches = [ephemeris._sun_events, ephemeris._moon_events, ephemeris._mustaches, ephemeris._year_context]
    assert all(c.cache_info().currsize > 0 for c in caches)
    reset_caches()
    assert all(c.cache_info().currsize == 0 for c in caches)
    assert NaturalDate(APRIL_23, 2.3522) == nd  # same answers afterwards


# --- Home Assistant -----------------------------------------------------------------------------

@pytest.mark.parametrize("precision", [0, 1, math.inf])  # zone, decimal, analog
def test_snapshot_is_what_the_parts_say(precision):
    snapshot = build_snapshot(datetime(2026, 4, 23, 14, 56, tzinfo=UTC), precision=precision, **PARIS)
    nd = NaturalDate(APRIL_23, PARIS["longitude"], precision)
    assert snapshot.natural_date == nd
    assert snapshot.sun_position == natural_sun_position(nd, PARIS["latitude"])
    assert snapshot.sun_events == natural_sun_events(nd, PARIS["latitude"])
    assert snapshot.moon_position == natural_moon_position(nd, PARIS["latitude"])
    assert snapshot.moon_events == natural_moon_events(nd, PARIS["latitude"])
    assert snapshot.light_phase == natural_light_phase(nd, snapshot.sun_events)
    assert snapshot.day_progress == pytest.approx(nd.time / 3.6, abs=1e-12)


def test_snapshot_values_have_the_types_home_assistant_expects():
    s = build_snapshot(APRIL_23, precision=1, **PARIS)
    assert type(s.sun_position.is_above_horizon) is bool and type(s.natural_date.is_rainbow_day) is bool
    assert s.sun_position.is_above_horizon == (s.sun_position.elevation >= 0)
    assert s.sun_position.altitude == max(s.sun_position.elevation, 0)
    assert s.light_phase in {"night", "dawn", "golden_morning", "day", "golden_evening", "dusk"}
    assert 0 <= s.day_progress < 100
    for value in (s.natural_date.time, s.day_progress, s.sun_position.elevation, s.sun_position.azimuth,
                  s.sun_events.sunrise, s.sun_events.sunset, s.sun_events.night_start, s.sun_events.night_end,
                  s.moon_position.phase, s.moon_position.altitude):
        assert isinstance(value, float) and math.isfinite(round(value, 2))
    assert (s.natural_date.year, s.natural_date.moon, s.natural_date.day_of_moon) == (14, 5, 10)
    assert s.natural_date.to_string() == "014)05)10 226°30 NT+2.3"
    assert 0 <= s.moon_position.phase < 360


def test_snapshot_now_and_frozen():
    s = build_snapshot(latitude=0, longitude=0)
    assert abs(s.natural_date.unix_time - clock.time_ns() // 1_000_000) < 60_000
    with pytest.raises(dataclasses.FrozenInstanceError):
        s.light_phase = "day"


def test_rainbow_flag_reaches_the_snapshot():
    start = NaturalDate("2017-06-01", 0).year_start
    assert build_snapshot(start + 364 * DAY + 5, latitude=45, longitude=0).natural_date.is_rainbow_day
    assert not build_snapshot(start + 100 * DAY, latitude=45, longitude=0).natural_date.is_rainbow_day


PHASE_EVENTS = SunEvents(sunrise=90, sunset=270, night_start=300, night_end=60, morning_golden_hour=100, evening_golden_hour=250)


@pytest.mark.parametrize("degrees, phase", [
    (0, "night"),  # night runs across midnight
    (59.9, "night"),
    (60, "dawn"),  # every phase includes its start, excludes its end
    (89.9, "dawn"),
    (90, "golden_morning"),
    (99.9, "golden_morning"),
    (100, "day"),
    (180, "day"),
    (249.9, "day"),
    (250, "golden_evening"),
    (269.9, "golden_evening"),
    (270, "dusk"),
    (299.9, "dusk"),
    (300, "night"),
    (359.9, "night"),
])
def test_light_phase_boundaries(degrees, phase):
    assert natural_light_phase(at_degrees(degrees), PHASE_EVENTS) == phase


def test_light_phase_default_reads_the_sun_at_the_equator():
    nd = at_degrees(120)
    assert natural_light_phase(nd) == natural_light_phase(nd, natural_sun_events(nd, 0))


def test_light_phase_follows_the_sun_through_a_day():
    order = ["night", "dawn", "golden_morning", "day", "golden_evening", "dusk", "night"]
    seen, elevation_ranges = [], {
        "night": (-90, -11), "dawn": (-13, 1), "golden_morning": (-1, 7), "day": (5, 90),
        "golden_evening": (-1, 7), "dusk": (-13, 1),
    }
    for degrees in range(360):
        nd = at_degrees(degrees, PARIS["longitude"], math.inf)
        snap = build_snapshot(nd.unix_time, precision=math.inf, **PARIS)
        low, high = elevation_ranges[snap.light_phase]
        assert low <= snap.sun_position.elevation <= high, (snap.natural_date.time, snap.light_phase)
        if not seen or seen[-1] != snap.light_phase:
            seen.append(snap.light_phase)
    assert seen == order


@pytest.mark.parametrize("instant, expected", [
    ("2026-12-21T12:00:00Z", "night"),  # North Pole, sun 23 degrees below the horizon all day
    ("2026-06-21T12:00:00Z", "day"),
])
def test_polar_light_phase(instant, expected):
    assert build_snapshot(instant, latitude=90, longitude=0).light_phase == expected
