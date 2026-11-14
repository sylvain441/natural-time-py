"""Written from the specification (natural-time/README.md), not from the code."""

import calendar
import math
import re
from datetime import UTC, datetime

import pytest

from natural_time import NaturalDate

DAY = 86_400_000
YEAR_1 = 1_356_091_200_000  # "Year 1 beginning", as the specification gives it


def utc(*parts) -> int:
    return calendar.timegm(datetime(*parts, tzinfo=UTC).utctimetuple()) * 1000


def test_year_1_begins_at_the_antimeridian_midnight():
    first = NaturalDate(YEAR_1, 180)
    assert (first.year, first.moon, first.day_of_moon, first.day_of_year, first.time) == (1, 1, 1, 1, 0)
    assert first.to_string() == "001)01)01 000°00 NT+180"
    before = NaturalDate(YEAR_1 - 1, 180)
    assert before.year == 0 and before.time == pytest.approx(360, abs=1e-5)
    assert datetime.fromtimestamp(YEAR_1 / 1000, UTC) == datetime(2012, 12, 21, 12, tzinfo=UTC)


def test_year_1_begins_half_a_day_later_at_the_meridian():
    assert NaturalDate(YEAR_1 + DAY // 2 - 1, 0).year == 0
    assert NaturalDate(YEAR_1 + DAY // 2, 0).to_string() == "001)01)01 000°00 NTZ"


def test_the_year_starts_at_the_first_antimeridian_midnight_after_the_winter_solstice():
    # December solstices as published (UTC) -> the next 12:00 UTC is the antimeridian's midnight
    for solstice, year_start, year in [
        (utc(2020, 12, 21, 10, 2), utc(2020, 12, 21, 12), 9),
        (utc(2022, 12, 21, 21, 48), utc(2022, 12, 22, 12), 11),
        (utc(2023, 12, 22, 3, 27), utc(2023, 12, 22, 12), 12),
    ]:
        assert NaturalDate(year_start, 180).year == year and NaturalDate(year_start, 180).day_of_year == 1
        assert NaturalDate(year_start - 1, 180).year == year - 1
        assert 0 <= year_start - solstice < DAY


def test_a_year_is_365_or_366_days_and_years_follow_one_another():
    start, durations = YEAR_1, []
    for year in range(1, 41):
        nd = NaturalDate(start, 180)
        assert (nd.year, nd.day_of_year) == (year, 1)
        durations.append(nd.year_duration)
        start += nd.year_duration * DAY
    assert set(durations) == {365, 366}
    assert NaturalDate(start - 1, 180).year == 40 and NaturalDate(start, 180).year == 41


@pytest.mark.parametrize("probe", ["2026-06-01", "2017-06-01"])  # a 365-day year and a 366-day year
def test_13_moons_of_28_days_then_the_rainbow_days(probe):
    probe = NaturalDate(probe, 0)
    for k in range(probe.year_duration):
        nd = NaturalDate(probe.year_start + k * DAY + DAY // 2, 0)
        assert nd.day_of_year == k + 1
        if k < 13 * 28:
            assert (nd.moon, nd.day_of_moon, nd.is_rainbow_day) == (k // 28 + 1, k % 28 + 1, False)
            assert nd.to_date_string() == f"{nd.year:03d}){k // 28 + 1:02d}){k % 28 + 1:02d}"
        else:
            assert nd.is_rainbow_day
            assert nd.to_date_string() == f"{nd.year:03d})RAINBOW" + ("+" if k == 365 else "")
    assert probe.year_duration - 13 * 28 in (1, 2)  # the 365th day, and the 366th if it exists


def test_midnight_is_zero_and_midday_180_at_the_given_longitude():
    for longitude in (0, 2.3522, -73.57, 180, -180, 89.99):
        midnight = YEAR_1 + round((180 - longitude) * DAY / 360) + 10 * DAY
        nd = lambda ms: NaturalDate(ms, longitude, math.inf)
        assert nd(midnight).time == pytest.approx(0, abs=1e-5)
        assert nd(midnight + DAY // 4).time == pytest.approx(90, abs=1e-5)
        assert nd(midnight + DAY // 2).time == pytest.approx(180, abs=1e-5)


def test_a_day_is_one_turn():
    nadir = NaturalDate(utc(2026, 4, 23, 3), 10, math.inf).nadir
    times = [NaturalDate(nadir + k * DAY // 24, 10, math.inf).time for k in range(24)]
    assert times == pytest.approx([15 * k for k in range(24)], abs=1e-6)  # 15° an hour


def test_time_distance():
    # The table of the specification: when NTZ reads 120°, NT-30 reads 90° and NT+40 reads 160°.
    instant = NaturalDate(utc(2026, 4, 23, 12), 0, math.inf).nadir + DAY // 3
    assert NaturalDate(instant, 0, math.inf).time == pytest.approx(120, abs=1e-6)
    assert NaturalDate(instant, -30, math.inf).time == pytest.approx(90, abs=1e-6)
    assert NaturalDate(instant, 40, math.inf).time == pytest.approx(160, abs=1e-6)


@pytest.mark.parametrize("moment, year", [
    ("2012-06-01", 0),  # year 0: 2011/2012
    ("2011-06-01", -1),  # year -1: 2010/2011
    ("2010-06-01", -2),
    ("2013-06-01", 1),
    ("2020-03-01", 8),  # before the local year start: Gregorian - 2012
    ("2020-12-10", 8),
    ("2020-12-31", 9),  # after it: Gregorian + 1 - 2012
])
def test_year_0_and_negative_years_exist(moment, year):
    assert NaturalDate(moment, 0).year == year


def test_the_format():
    pattern = re.compile(r"^-?\d{3,}\)(\d{2}\)\d{2}|RAINBOW\+?) \d{3}°\d{2} NT([+-]\d+(\.\d+)?|Z)$")
    for moment in ("2026-04-23T14:56:00Z", "1999-12-31T23:59:59Z", "2011-06-01", "2100-01-01"):
        for longitude, precision in ((0, 0), (5.2, 1), (-68, 0), (52.441888, 6), (-180, 0)):
            assert pattern.match(NaturalDate(moment, longitude, precision).to_string())
    assert pattern.match(NaturalDate(YEAR_1 - 1, 0).to_string())  # a Rainbow day


def test_the_example_of_the_specification():
    # "010)05)22 202°63 NT+5.2": year 10, 5th moon, 22nd day, at 202.63° (48631200 ms into the day), longitude 5.2
    year_10_start = NaturalDate("2022-06-01", 5.2, 1).year_start
    nd = NaturalDate(year_10_start + (4 * 28 + 21) * DAY + 48_631_200, 5.2, 1)
    assert nd.to_string() == "010)05)22 202°63 NT+5.2"


def test_time_decimals_and_longitude_forms():
    nd = NaturalDate(utc(2026, 4, 23, 12), 0, 0)
    assert re.fullmatch(r"\d{3}°", nd.to_time_string(0))
    assert re.fullmatch(r"\d{3}°\d{5}", nd.to_time_string(5))
    assert NaturalDate(YEAR_1, 0).to_longitude_string() == "NTZ"
    assert NaturalDate(YEAR_1, -68).to_longitude_string() == "NT-68"
    assert NaturalDate(YEAR_1, 52.441888, 6).to_longitude_string() == "NT+52.441888"
