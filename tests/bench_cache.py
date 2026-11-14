"""Cache benchmark: what each cache earns, and what the realistic clock loop costs.

Run from the repo: python tests/bench_cache.py (pytest does not collect it).
Cold = one call right after reset_caches(); warm = the same call again, repeated.
Both are medians. The sky functions are measured at one place, 2.3522° E 48.8566° N.
"""

import statistics
import sys
from pathlib import Path
from time import perf_counter_ns

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from natural_time import (  # noqa: E402
    NaturalDate,
    mustaches_range,
    natural_moon_events,
    natural_moon_position,
    natural_sun_events,
    natural_sun_position,
    reset_caches,
)
from natural_time import ephemeris  # noqa: E402
from natural_time import core  # noqa: E402

LAT, LON = 48.8566, 2.3522
INSTANT = 1_776_956_160_000  # 2026-04-23 14:56 UTC
COLD_ROUNDS = 300
WARM_BATCHES = 60
WARM_CALLS = 500

nd = NaturalDate(INSTANT, LON)
ROWS = [
    ("NaturalDate", lambda: NaturalDate(INSTANT, LON)),
    ("sun events", lambda: natural_sun_events(nd, LAT)),
    ("moon events", lambda: natural_moon_events(nd, LAT)),
    ("mustaches", lambda: mustaches_range(nd, LAT)),
    ("sun position (no cache)", lambda: natural_sun_position(nd, LAT)),
    ("moon position (no cache)", lambda: natural_moon_position(nd, LAT)),
]


def cold(fn) -> float:
    times = []
    for i in range(COLD_ROUNDS + 20):
        reset_caches()
        t0 = perf_counter_ns()
        fn()
        t1 = perf_counter_ns()
        if i >= 20:
            times.append(t1 - t0)
    return statistics.median(times) / 1000


def warm(fn) -> float:
    fn()
    times = []
    for b in range(WARM_BATCHES + 5):
        t0 = perf_counter_ns()
        for _ in range(WARM_CALLS):
            fn()
        t1 = perf_counter_ns()
        if b >= 5:
            times.append((t1 - t0) / WARM_CALLS)
    return statistics.median(times) / 1000


def misses() -> dict[str, int]:
    return {
        "NaturalDate year context": core._year_context.cache_info().misses,
        "sun events": ephemeris._sun_events.cache_info().misses,
        "moon events": ephemeris._moon_events.cache_info().misses,
        "mustaches": ephemeris._mustaches.cache_info().misses,
    }


def clock_loop(label: str, ticks: int, reset_every_tick: bool) -> float:
    reset_caches()
    start = NaturalDate(INSTANT, LON).nadir
    t0 = perf_counter_ns()
    for i in range(ticks):
        if reset_every_tick:
            reset_caches()
        d = NaturalDate(start + i * 1000, LON)
        natural_sun_events(d, LAT)
        natural_moon_events(d, LAT)
        mustaches_range(d, LAT)
        natural_sun_position(d, LAT)
        natural_moon_position(d, LAT)
    total = (perf_counter_ns() - t0) / 1e6
    per_tick = total * 1000 / ticks
    counted = ", ".join(f"{k} {v}" for k, v in misses().items())
    if reset_every_tick:
        counted = "one set per tick (counters reset with the caches)"
    print(f"\n{label}: {ticks} ticks, {total:.0f} ms total, {per_tick:.1f} µs per tick")
    print(f"  searches run (cache misses): {counted}; position searches (uncached): {ticks} sun + {ticks} moon")
    return per_tick


print(f"{'function':<26}{'cold µs':>10}{'warm µs':>10}{'speed-up':>10}")
for name, fn in ROWS:
    c, w = cold(fn), warm(fn)
    print(f"{name:<26}{c:>10.2f}{w:>10.3f}{c / w:>9.1f}x")

cached = clock_loop("clock loop, caches on", 86400, False)
bare = clock_loop("clock loop, caches reset every tick (sample)", 1000, True)
print(f"  caches save {(bare - cached) / bare * 100:.0f}% of a tick ({bare:.1f} -> {cached:.1f} µs)")

# Entries pile up until the lru_cache bound: a longitude slider, then a year of daily polls.
reset_caches()
for i in range(5000):
    d = NaturalDate(INSTANT, -180 + 360 * i / 5000, float("inf"))
    natural_sun_events(d, LAT)
    natural_moon_events(d, LAT)
sizes = {
    "year context": core._year_context.cache_info(),
    "sun events": ephemeris._sun_events.cache_info(),
    "moon events": ephemeris._moon_events.cache_info(),
    "mustaches": ephemeris._mustaches.cache_info(),
}
print("\nlongitude slider, 5000 exact longitudes:")
for name, info in sizes.items():
    print(f"  {name:<14} {info.currsize} entries kept (bound {info.maxsize})")

# Two places read in turn: does one evict the other?
reset_caches()
a, b = NaturalDate(INSTANT, 2.35), NaturalDate(INSTANT, -73.57)
natural_sun_events(a, LAT)
natural_sun_events(b, LAT)
hits = ephemeris._sun_events.cache_info().hits
natural_sun_events(a, LAT)
print(f"\nsun events of place A still cached after place B: {ephemeris._sun_events.cache_info().hits == hits + 1}")
