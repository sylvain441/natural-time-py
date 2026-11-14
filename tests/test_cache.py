"""The caches must be invisible: a hit returns what a fresh computation would, and any
change of key misses. Speed is asserted only with a very wide margin."""

import math
import statistics
from time import perf_counter_ns

import pytest

from natural_time import (
    NaturalDate,
    mustaches_range,
    natural_moon_events,
    natural_sun_events,
    reset_caches,
)
from natural_time import ephemeris

T = 1_776_956_160_000  # 2026-04-23 14:56 UTC
DAY = 86_400_000
LAT, LON = 48.8566, 2.3522


def fresh(compute):
    reset_caches()
    return compute()


# `moves`: whether changing that one input of the key must change the answer.
# Mustaches are read from the meridian, for the UTC year: longitude, precision and day do not enter.
SKIES = {
    "sun events": (natural_sun_events, dict(latitude=True, longitude=True, precision=True, next_day=True)),
    "moon events": (natural_moon_events, dict(latitude=True, longitude=True, precision=True, next_day=True)),
    "mustaches": (mustaches_range, dict(latitude=True, longitude=False, precision=False, next_day=False)),
}

VARIANTS = {
    "latitude": lambda: (NaturalDate(T, LON, 0), LAT - 10),
    "longitude": lambda: (NaturalDate(T, LON + 30, 0), LAT),
    "precision": lambda: (NaturalDate(T, LON, math.inf), LAT),
    "next_day": lambda: (NaturalDate(T + DAY, LON, 0), LAT),
}


def base():
    return NaturalDate(T, LON, 0), LAT


@pytest.mark.parametrize("sky", SKIES)
def test_repeated_call_returns_the_stored_answer(sky):
    of, _ = SKIES[sky]
    reset_caches()
    date, latitude = base()
    assert of(date, latitude) is of(date, latitude)


@pytest.mark.parametrize("change", VARIANTS)
@pytest.mark.parametrize("sky", SKIES)
def test_changing_one_input_gives_the_fresh_answer(sky, change):
    of, moves = SKIES[sky]
    expected = fresh(lambda: of(*VARIANTS[change]()))

    reset_caches()
    first = of(*base())
    other = of(*VARIANTS[change]())

    assert other == expected
    assert (other != first) == moves[change]
    # Coming back to the first inputs gives the first answer again
    assert of(*base()) == first


@pytest.mark.parametrize(
    "make",
    [
        pytest.param(lambda: NaturalDate(T, LON + 30, 0), id="longitude"),
        pytest.param(lambda: NaturalDate(T, LON, math.inf), id="precision"),
        pytest.param(lambda: NaturalDate(1_811_000_000_000, LON, 0), id="year"),
    ],
)
def test_year_context_key(make):
    expected = fresh(make)

    reset_caches()
    first = NaturalDate(T, LON, 0)
    assert make() == expected
    assert make() != first
    assert NaturalDate(T, LON, 0) == first


def test_lru_bound_evicts_without_changing_answers():
    reset_caches()
    date = NaturalDate(T, 0.5, math.inf)
    first = natural_sun_events(date, LAT)
    bound = ephemeris._sun_events.cache_info().maxsize
    for i in range(1, bound + 20):
        natural_sun_events(NaturalDate(T, 0.5 + i / 1000, math.inf), LAT)

    assert ephemeris._sun_events.cache_info().currsize == bound
    assert natural_sun_events(date, LAT) == first


# Measured: a hit is thousands of times faster. 5x leaves room for any shared runner.
def test_warm_sun_events_is_at_least_5x_faster_than_cold():
    date = NaturalDate(T, LON)
    cold = []
    for _ in range(15):
        reset_caches()
        t0 = perf_counter_ns()
        natural_sun_events(date, LAT)
        cold.append(perf_counter_ns() - t0)

    natural_sun_events(date, LAT)
    warm = []
    for _ in range(15):
        t0 = perf_counter_ns()
        for _ in range(200):
            natural_sun_events(date, LAT)
        warm.append((perf_counter_ns() - t0) / 200)

    assert statistics.median(warm) * 5 < statistics.median(cold)
