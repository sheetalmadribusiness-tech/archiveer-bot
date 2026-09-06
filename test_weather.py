"""Tests voor de weerbot. Draaien zonder netwerk: python3 -m unittest -v"""

import unittest
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import weather
import weatherbot

DAY = date(2026, 4, 7)  # dinsdag


def location(code=2, tmax=17.4, tmin=8.6, rain=0.0, chance=10,
             wind=22.0, gust=41.0, degrees=225.0):
    """Antwoord van Open-Meteo voor één locatie, één dag."""
    return {
        "latitude": 52.37, "longitude": 4.89, "timezone": "Europe/Amsterdam",
        "daily": {
            "time": [DAY.isoformat()],
            "weather_code": [code],
            "temperature_2m_max": [tmax],
            "temperature_2m_min": [tmin],
            "precipitation_sum": [rain],
            "precipitation_probability_max": [chance],
            "wind_speed_10m_max": [wind],
            "wind_gusts_10m_max": [gust],
            "wind_direction_10m_dominant": [degrees],
            "sunrise": [f"{DAY.isoformat()}T06:52"],
            "sunset": [f"{DAY.isoformat()}T20:41"],
        },
    }


CITIES = weather.DEFAULT_CITIES
PAYLOAD = [location() for _ in CITIES]


class TestConversions(unittest.TestCase):
    def test_beaufort(self):
        for kmh, force in [(0, 0), (3, 1), (10, 2), (22, 4), (45, 6), (70, 8), (130, 12)]:
            self.assertEqual(weather.beaufort(kmh), force, kmh)

    def test_compass(self):
        for degrees, point in [(0, "N"), (90, "O"), (180, "Z"), (225, "ZW"),
                               (350, "N"), (360, "N"), (370, "N")]:
            self.assertEqual(weather.compass(degrees), point, degrees)

    def test_dutch_date_and_numbers(self):
        self.assertEqual(weather.dutch_date(DAY), "dinsdag 7 april")
        self.assertEqual(weather.number(17.4), "17")
        self.assertEqual(weather.number(0.8, 1), "0,8")
        self.assertEqual(weather.number(12.6), "13")


class TestParsing(unittest.TestCase):
    def test_parse_all_cities(self):
        forecasts = weather.parse_forecast(PAYLOAD, CITIES, DAY)
        self.assertEqual(len(forecasts), len(CITIES))
        first = forecasts[0]
        self.assertEqual(first.city, "Amsterdam")
        self.assertEqual(first.description, "half bewolkt")
        self.assertEqual(first.direction, "ZW")
        self.assertEqual(first.beaufort, 4)
        self.assertEqual(first.sunrise, "06:52")

    def test_single_location_object(self):
        forecasts = weather.parse_forecast(location(), [CITIES[0]], DAY)
        self.assertEqual(len(forecasts), 1)

    def test_missing_values_are_tolerated(self):
        payload = location()
        payload["daily"]["precipitation_probability_max"] = [None]
        payload["daily"]["wind_gusts_10m_max"] = [None]
        forecast = weather.parse_forecast(payload, [CITIES[0]], DAY)[0]
        self.assertIsNone(forecast.precipitation_chance)
        self.assertIsNone(forecast.gust_kmh)

    def test_wrong_day_raises(self):
        with self.assertRaises(weather.WeatherError):
            weather.parse_forecast(location(), [CITIES[0]], DAY + timedelta(days=3))

    def test_location_count_mismatch_raises(self):
        with self.assertRaises(weather.WeatherError):
            weather.parse_forecast([location()], CITIES, DAY)


class TestPost(unittest.TestCase):
    def setUp(self):
        self.forecasts = weather.parse_forecast(PAYLOAD, CITIES, DAY)

    def test_title(self):
        title = weather.build_title(
            self.forecasts, weatherbot.DEFAULTS["WEATHER_TITLE_TEMPLATE"])
        self.assertIn("dinsdag 7 april", title)
        self.assertIn("9° tot 17°", title)
        self.assertIn("half bewolkt", title)

    def test_footer_credits_knmi(self):
        self.assertIn("KNMI-model", weather.build_body(self.forecasts))

    def test_body_has_a_row_per_city(self):
        body = weather.build_body(self.forecasts)
        for name, _, _ in CITIES:
            self.assertIn(f"| {name} |", body)
        self.assertIn("| Plaats | Weer | Max | Min | Neerslag | Wind |", body)
        self.assertIn("Zon op **06:52** · onder **20:41** (Utrecht)", body)
        self.assertIn("uit het zuidwesten (ZW), 4 Bft", body)

    def test_storm_warning_only_when_it_blows(self):
        self.assertNotIn("⚠️", weather.build_body(self.forecasts))
        stormy = weather.parse_forecast(
            [location(gust=96.0) for _ in CITIES], CITIES, DAY)
        self.assertIn("⚠️ Zware windstoten tot 96 km/u.", weather.build_body(stormy))

    def test_rain_line_counts_wet_cities(self):
        mixed = weather.parse_forecast(
            [location(rain=3.2 if i < 4 else 0.0) for i in range(len(CITIES))],
            CITIES, DAY)
        self.assertIn("Kans op neerslag in 4 van de 11 plaatsen", weather.build_body(mixed))

    def test_average_wind_direction_wraps_around_north(self):
        payload = [location(degrees=350.0), location(degrees=10.0)]
        forecasts = weather.parse_forecast(payload, CITIES[:2], DAY)
        self.assertEqual(weather.summarize(forecasts)["direction"], "N")


class TestFetching(unittest.TestCase):
    """fetch_forecast met een nagebootste API, dus zonder netwerk."""

    def setUp(self):
        self.requests = []

    def fake_request(self, responses):
        def _request(cities, day, variables, model, timeout, api_url):
            self.requests.append({"variables": variables, "model": model})
            return responses[len(self.requests) - 1]
        return _request

    def run_fetch(self, responses, **kwargs):
        original = weather._request
        weather._request = self.fake_request(responses)
        try:
            return weather.fetch_forecast(cities=CITIES, day=DAY, **kwargs)
        finally:
            weather._request = original

    def test_knmi_is_the_default_model(self):
        self.run_fetch([PAYLOAD])
        self.assertEqual(self.requests[0]["model"], "knmi_seamless")
        self.assertEqual(len(self.requests), 1, "geen tweede aanvraag nodig")

    def test_probability_is_fetched_separately_when_knmi_omits_it(self):
        without = [location(chance=None) for _ in CITIES]
        extra = [location(chance=65) for _ in CITIES]
        forecasts = self.run_fetch([without, extra])

        self.assertEqual(len(self.requests), 2)
        self.assertEqual(self.requests[1]["variables"], ["precipitation_probability_max"])
        self.assertIsNone(self.requests[1]["model"], "terugval gebruikt de standaardmix")
        self.assertTrue(all(f.precipitation_chance == 65 for f in forecasts))
        # De rest van de waarden blijft van het KNMI-model.
        self.assertEqual(forecasts[0].temp_max, 17.4)

    def test_post_still_works_when_the_fallback_fails(self):
        def failing(cities, day, variables, model, timeout, api_url):
            self.requests.append({"variables": variables, "model": model})
            if len(self.requests) == 1:
                return [location(chance=None) for _ in CITIES]
            raise weather.WeatherError("tweede aanvraag mislukt")

        original = weather._request
        weather._request = failing
        try:
            forecasts = weather.fetch_forecast(cities=CITIES, day=DAY)
        finally:
            weather._request = original

        self.assertTrue(all(f.precipitation_chance is None for f in forecasts))
        self.assertIn("| 1,4 mm |", weather.build_body(
            weather.parse_forecast([location(chance=None, rain=1.4)], CITIES[:1], DAY)))

    def test_no_fallback_without_a_pinned_model(self):
        self.run_fetch([[location(chance=None) for _ in CITIES]], model=None)
        self.assertEqual(len(self.requests), 1)

    def test_probabilities_tolerate_a_missing_column(self):
        payload = location()
        del payload["daily"]["precipitation_probability_max"]
        self.assertEqual(weather.probabilities([payload], CITIES[:1], DAY), [None])


class FakeModerator(str):
    """Gedraagt zich als een moderatornaam met rechten eraan."""
    def __new__(cls, name, permissions):
        self = super().__new__(cls, name)
        self.mod_permissions = permissions
        return self


class FakeReddit:
    def __init__(self, me="weerbot", moderators=(), fail_login=False):
        self.user = type("U", (), {"me": lambda _: (_ for _ in ()).throw(
            RuntimeError("401 ongeldige inloggegevens")) if fail_login else me})()
        self._moderators = moderators

    def subreddit(self, name):
        moderators = self._moderators
        return type("S", (), {
            "display_name": name,
            "moderator": lambda _: list(moderators),
        })()


class TestCheckSetup(unittest.TestCase):
    """--check, met een nagebootste Reddit-verbinding."""

    def settings(self, **overrides):
        base = dict(weatherbot.DEFAULTS)
        base.update({
            "WEATHER_SUBREDDIT": "testsub",
            "REDDIT_CLIENT_ID": "x", "REDDIT_CLIENT_SECRET": "x",
            "REDDIT_USERNAME": "weerbot", "REDDIT_PASSWORD": "x",
        })
        base.update(overrides)
        return base

    def check(self, settings, reddit):
        import contextlib, io
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = weatherbot.check_setup(settings, reddit=reddit)
        return code, out.getvalue()

    def test_reports_account_and_subreddit(self):
        code, out = self.check(self.settings(), FakeReddit())
        self.assertEqual(code, 0)
        self.assertIn("Ingelogd als u/weerbot", out)
        self.assertIn("Subreddit r/testsub gevonden", out)

    def test_bad_credentials_fail_clearly(self):
        code, out = self.check(self.settings(), FakeReddit(fail_login=True))
        self.assertEqual(code, 1)
        self.assertIn("Inloggen mislukt", out)
        self.assertIn("2FA", out)

    def test_warns_when_sticky_lacks_the_posts_permission(self):
        reddit = FakeReddit(moderators=[FakeModerator("weerbot", ["flair"])])
        _, out = self.check(self.settings(WEATHER_STICKY=True), reddit)
        self.assertIn("het recht 'posts' ontbreekt", out)

    def test_sticky_allowed_with_posts_permission(self):
        reddit = FakeReddit(moderators=[FakeModerator("weerbot", ["posts"])])
        _, out = self.check(self.settings(WEATHER_STICKY=True), reddit)
        self.assertIn("Vastzetten kan.", out)
        self.assertIn("Moderatorrechten: posts", out)

    def test_notices_when_the_bot_is_not_a_moderator(self):
        reddit = FakeReddit(moderators=[FakeModerator("iemandanders", ["all"])])
        _, out = self.check(self.settings(), reddit)
        self.assertIn("is geen moderator", out)

    def test_missing_credentials_stop_before_any_call(self):
        with self.assertRaises(SystemExit):
            weatherbot.check_setup(self.settings(REDDIT_PASSWORD=None),
                                   reddit=FakeReddit())


class TestScheduling(unittest.TestCase):
    tz = ZoneInfo("Europe/Amsterdam")

    def test_next_run_is_today_when_still_ahead(self):
        now = datetime(2026, 4, 7, 12, 0, tzinfo=self.tz)
        self.assertEqual(weatherbot.next_run(now, 19, 45),
                         datetime(2026, 4, 7, 19, 45, tzinfo=self.tz))

    def test_next_run_rolls_over_after_the_time(self):
        now = datetime(2026, 4, 7, 19, 46, tzinfo=self.tz)
        self.assertEqual(weatherbot.next_run(now, 19, 45),
                         datetime(2026, 4, 8, 19, 45, tzinfo=self.tz))

    def test_guard_window(self):
        self.assertTrue(weatherbot.within_window(
            "19:45", now=datetime(2026, 4, 7, 19, 50, tzinfo=self.tz)))
        self.assertFalse(weatherbot.within_window(
            "19:45", now=datetime(2026, 4, 7, 18, 45, tzinfo=self.tz)))

    def test_invalid_time_is_rejected(self):
        with self.assertRaises(SystemExit):
            weatherbot.parse_time("25:00")


class TestSettings(unittest.TestCase):
    def test_cities_from_env_string(self):
        cities = weatherbot._as_cities("Amsterdam:52.37:4.89, Groningen:53.22:6.57")
        self.assertEqual(cities, [("Amsterdam", 52.37, 4.89), ("Groningen", 53.22, 6.57)])

    def test_bad_city_string_is_rejected(self):
        with self.assertRaises(SystemExit):
            weatherbot._as_cities("Amsterdam:52.37")

    def test_booleans_from_env(self):
        self.assertTrue(weatherbot._as_bool("ja"))
        self.assertFalse(weatherbot._as_bool("false"))


if __name__ == "__main__":
    unittest.main()
