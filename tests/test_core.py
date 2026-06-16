from datetime import UTC, datetime
import unittest

from natural_time import (
    NaturalDate,
    build_snapshot,
    natural_moon_events,
    natural_moon_position,
    natural_sun_events,
    natural_sun_position,
)


class NaturalDateTest(unittest.TestCase):
    def test_time_follows_longitude(self) -> None:
        date = datetime(2023, 1, 1, 12, tzinfo=UTC)
        self.assertAlmostEqual(NaturalDate(date, 0).time, 180, delta=1)
        self.assertAlmostEqual(NaturalDate(date, 90).time, 270, delta=1)
        self.assertAlmostEqual(NaturalDate(date, -90).time, 90, delta=1)

    def test_precision_truncates_longitude(self) -> None:
        date = NaturalDate(datetime(2023, 1, 1, 12, tzinfo=UTC), 2.3522, 1)
        self.assertEqual(date.effective_longitude, 2.3)
        self.assertEqual(date.to_longitude_string(), "NT+2.3")

    def test_string_formatting(self) -> None:
        date = NaturalDate(datetime(2023, 1, 1, 12, tzinfo=UTC), 0)
        self.assertIn("NTZ", date.to_string())
        self.assertRegex(date.to_time_string(), r"^\d{3}°\d{2}$")


class AstronomyTest(unittest.TestCase):
    def test_sun_position_has_signed_elevation(self) -> None:
        night = NaturalDate(datetime(2024, 6, 1, 0, tzinfo=UTC), 2.3522, float("inf"))
        sun = natural_sun_position(night, 48.8566)
        self.assertGreaterEqual(sun.azimuth, 0)
        self.assertLessEqual(sun.azimuth, 360)
        self.assertLess(sun.elevation, 0)
        self.assertEqual(sun.altitude, 0)
        self.assertFalse(sun.is_above_horizon)

    def test_snapshot_contains_home_assistant_values(self) -> None:
        snapshot = build_snapshot(
            datetime(2024, 6, 1, 12, tzinfo=UTC),
            latitude=48.8566,
            longitude=2.3522,
            precision=float("inf"),
        )
        self.assertGreater(snapshot.natural_date.time, 0)
        self.assertIn(snapshot.light_phase, {"night", "dawn", "golden_morning", "day", "golden_evening", "dusk"})
        self.assertGreaterEqual(snapshot.day_progress, 0)
        self.assertLessEqual(snapshot.day_progress, 100)

    def test_matches_js_golden_vector(self) -> None:
        date = NaturalDate(16739988775343, -180)
        sun_position = natural_sun_position(date, 45)
        sun_events = natural_sun_events(date, 45)
        moon_position = natural_moon_position(date, 45)
        moon_events = natural_moon_events(date, 45)

        self.assertEqual(date.year, 488)
        self.assertEqual(date.moon, 7)
        self.assertEqual(date.day_of_year, 180)
        self.assertAlmostEqual(date.time, 133.23059583333333, places=7)
        self.assertAlmostEqual(sun_events.sunrise, 63.67619583333334, places=3)
        self.assertAlmostEqual(sun_events.sunset, 297.7636375, places=3)
        self.assertAlmostEqual(sun_position.altitude, 45.9806939375366, places=6)
        self.assertAlmostEqual(moon_position.phase, 280.3970779296969, places=6)
        self.assertAlmostEqual(moon_events.moonrise, 6.635120833333334, places=3)


if __name__ == "__main__":
    unittest.main()
