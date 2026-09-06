"""Ophalen en opmaken van de weersverwachting voor Nederland (Open-Meteo)."""

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta

API_URL = "https://api.open-meteo.com/v1/forecast"

# Standaardsteden: spreiding over alle windstreken/provincies.
DEFAULT_CITIES = [
    ("Amsterdam", 52.374, 4.890),
    ("Rotterdam", 51.922, 4.479),
    ("Den Haag", 52.078, 4.288),
    ("Utrecht", 52.091, 5.122),
    ("Eindhoven", 51.441, 5.478),
    ("Arnhem", 51.985, 5.899),
    ("Zwolle", 52.512, 6.094),
    ("Groningen", 53.219, 6.567),
    ("Leeuwarden", 53.201, 5.799),
    ("Maastricht", 50.851, 5.691),
    ("Middelburg", 51.499, 3.611),
]

DAILY_VARIABLES = [
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "precipitation_probability_max",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "wind_direction_10m_dominant",
    "sunrise",
    "sunset",
]

# WMO-weercodes -> (emoji, Nederlandse omschrijving)
WMO_CODES = {
    0: ("☀️", "onbewolkt"),
    1: ("\U0001f324️", "overwegend zonnig"),
    2: ("⛅", "half bewolkt"),
    3: ("☁️", "bewolkt"),
    45: ("\U0001f32b️", "mist"),
    48: ("\U0001f32b️", "aanvriezende mist"),
    51: ("\U0001f326️", "lichte motregen"),
    53: ("\U0001f326️", "motregen"),
    55: ("\U0001f327️", "zware motregen"),
    56: ("\U0001f9ca", "lichte onderkoelde motregen"),
    57: ("\U0001f9ca", "onderkoelde motregen (ijzel)"),
    61: ("\U0001f326️", "lichte regen"),
    63: ("\U0001f327️", "regen"),
    65: ("\U0001f327️", "zware regen"),
    66: ("\U0001f9ca", "lichte ijzel"),
    67: ("\U0001f9ca", "ijzel"),
    71: ("\U0001f328️", "lichte sneeuwval"),
    73: ("\U0001f328️", "sneeuwval"),
    75: ("❄️", "zware sneeuwval"),
    77: ("\U0001f328️", "sneeuwkorrels"),
    80: ("\U0001f326️", "enkele buien"),
    81: ("\U0001f327️", "buien"),
    82: ("⛈️", "zware buien"),
    85: ("\U0001f328️", "lichte sneeuwbuien"),
    86: ("❄️", "zware sneeuwbuien"),
    95: ("⛈️", "onweer"),
    96: ("⛈️", "onweer met hagel"),
    99: ("⛈️", "zwaar onweer met hagel"),
}

WEEKDAYS_NL = [
    "maandag", "dinsdag", "woensdag", "donderdag",
    "vrijdag", "zaterdag", "zondag",
]
MONTHS_NL = [
    "januari", "februari", "maart", "april", "mei", "juni",
    "juli", "augustus", "september", "oktober", "november", "december",
]
COMPASS_NL = [
    "N", "NNO", "NO", "ONO", "O", "OZO", "ZO", "ZZO",
    "Z", "ZZW", "ZW", "WZW", "W", "WNW", "NW", "NNW",
]
# Windrichting -> zoals je het uitspreekt in een weerbericht.
DIRECTION_WORDS_NL = {
    "N": "het noorden", "NNO": "het noordnoordoosten", "NO": "het noordoosten",
    "ONO": "het oostnoordoosten", "O": "het oosten", "OZO": "het oostzuidoosten",
    "ZO": "het zuidoosten", "ZZO": "het zuidzuidoosten", "Z": "het zuiden",
    "ZZW": "het zuidzuidwesten", "ZW": "het zuidwesten", "WZW": "het westzuidwesten",
    "W": "het westen", "WNW": "het westnoordwesten", "NW": "het noordwesten",
    "NNW": "het noordnoordwesten",
}

# Bovengrenzen van windkracht 0 t/m 11 in km/u; daarboven is het 12 Bft.
BEAUFORT_UPPER_KMH = [1, 5, 11, 19, 28, 38, 49, 61, 74, 88, 102, 117]


class WeatherError(RuntimeError):
    """De verwachting kon niet worden opgehaald of gelezen."""


@dataclass
class CityForecast:
    city: str
    day: date
    weather_code: int
    temp_max: float
    temp_min: float
    precipitation: float
    precipitation_chance: int | None
    wind_kmh: float
    gust_kmh: float | None
    wind_degrees: float
    sunrise: str | None
    sunset: str | None

    @property
    def emoji(self) -> str:
        return WMO_CODES.get(self.weather_code, ("\U0001f321️", "wisselvallig"))[0]

    @property
    def description(self) -> str:
        return WMO_CODES.get(self.weather_code, ("\U0001f321️", "wisselvallig"))[1]

    @property
    def beaufort(self) -> int:
        return beaufort(self.wind_kmh)

    @property
    def direction(self) -> str:
        return compass(self.wind_degrees)


def beaufort(kmh: float) -> int:
    """Zet windsnelheid in km/u om naar windkracht op de schaal van Beaufort."""
    for force, upper in enumerate(BEAUFORT_UPPER_KMH):
        if kmh < upper:
            return force
    return 12


def compass(degrees: float) -> str:
    """Windrichting in graden -> Nederlandse 16-punts afkorting (bijv. ZW)."""
    return COMPASS_NL[int((degrees % 360) / 22.5 + 0.5) % 16]


def dutch_date(day: date) -> str:
    return f"{WEEKDAYS_NL[day.weekday()]} {day.day} {MONTHS_NL[day.month - 1]}"


def number(value: float, decimals: int = 0) -> str:
    """Getal met Nederlandse decimale komma."""
    return f"{value:.{decimals}f}".replace(".", ",")


def _clock(timestamp: str | None) -> str | None:
    """'2026-04-07T06:52' -> '06:52'."""
    if not timestamp or "T" not in timestamp:
        return None
    return timestamp.split("T", 1)[1][:5]


def fetch_forecast(cities=None, day=None, timeout=30, model=None, api_url=API_URL):
    """Haal de dagverwachting voor `day` op voor alle steden.

    Eén request voor alle coordinaten samen, zodat we netjes binnen de
    fair-use limiet van Open-Meteo blijven.
    """
    cities = list(cities or DEFAULT_CITIES)
    if not cities:
        raise WeatherError("Er zijn geen steden geconfigureerd.")
    day = day or date.today() + timedelta(days=1)

    params = {
        "latitude": ",".join(str(lat) for _, lat, _ in cities),
        "longitude": ",".join(str(lon) for _, _, lon in cities),
        "daily": ",".join(DAILY_VARIABLES),
        "timezone": "Europe/Amsterdam",
        "start_date": day.isoformat(),
        "end_date": day.isoformat(),
    }
    if model:
        params["models"] = model

    url = f"{api_url}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.load(response)
    except Exception as exc:  # netwerkfout, time-out, ongeldige JSON
        raise WeatherError(f"Ophalen van de verwachting mislukt: {exc}") from exc

    return parse_forecast(payload, cities, day)


def parse_forecast(payload, cities, day):
    """Zet het Open-Meteo antwoord om in CityForecast-objecten."""
    # Bij één coordinaat geeft de API een object terug, bij meerdere een lijst.
    locations = payload if isinstance(payload, list) else [payload]
    if len(locations) != len(cities):
        raise WeatherError(
            f"Onverwacht antwoord: {len(locations)} locaties voor {len(cities)} steden."
        )

    forecasts = []
    for (name, _, _), location in zip(cities, locations):
        daily = location.get("daily") or {}
        if not daily.get("time"):
            raise WeatherError(f"Geen dagverwachting ontvangen voor {name}.")
        try:
            index = daily["time"].index(day.isoformat())
        except ValueError as exc:
            raise WeatherError(
                f"{day.isoformat()} zit niet in de verwachting voor {name}."
            ) from exc

        def value(key, default=None):
            column = daily.get(key)
            if not column or index >= len(column) or column[index] is None:
                return default
            return column[index]

        chance = value("precipitation_probability_max")
        forecasts.append(CityForecast(
            city=name,
            day=day,
            weather_code=int(value("weather_code", 3)),
            temp_max=float(value("temperature_2m_max", 0.0)),
            temp_min=float(value("temperature_2m_min", 0.0)),
            precipitation=float(value("precipitation_sum", 0.0)),
            precipitation_chance=None if chance is None else int(chance),
            wind_kmh=float(value("wind_speed_10m_max", 0.0)),
            gust_kmh=None if value("wind_gusts_10m_max") is None
            else float(value("wind_gusts_10m_max")),
            wind_degrees=float(value("wind_direction_10m_dominant", 0.0)),
            sunrise=_clock(value("sunrise")),
            sunset=_clock(value("sunset")),
        ))
    return forecasts


def _dominant_code(forecasts):
    """Meest voorkomende weertype; bij gelijkspel wint het zwaarste weer."""
    counts = {}
    for forecast in forecasts:
        counts[forecast.weather_code] = counts.get(forecast.weather_code, 0) + 1
    return max(counts, key=lambda code: (counts[code], code))


def summarize(forecasts):
    """Landelijke samenvatting: uitersten, dominant weertype en wind."""
    codes = _dominant_code(forecasts)
    emoji, description = WMO_CODES.get(codes, ("\U0001f321️", "wisselvallig"))
    forces = sorted(forecast.beaufort for forecast in forecasts)
    directions = [forecast.wind_degrees for forecast in forecasts]
    # Gemiddelde richting via vectoren, zodat 350 en 10 graden noord opleveren.
    import math
    x = sum(math.sin(math.radians(d)) for d in directions)
    y = sum(math.cos(math.radians(d)) for d in directions)
    mean_direction = math.degrees(math.atan2(x, y)) % 360

    return {
        "emoji": emoji,
        "description": description,
        "temp_min": min(f.temp_min for f in forecasts),
        "temp_max": max(f.temp_max for f in forecasts),
        "wind_min": forces[0],
        "wind_max": forces[-1],
        "direction": compass(mean_direction),
        "direction_words": DIRECTION_WORDS_NL[compass(mean_direction)],
        "rain_cities": sum(1 for f in forecasts if f.precipitation >= 0.2),
        "max_gust": max((f.gust_kmh or 0.0) for f in forecasts),
    }


def build_title(forecasts, template):
    summary = summarize(forecasts)
    day = forecasts[0].day
    return template.format(
        weekday=WEEKDAYS_NL[day.weekday()],
        day=day.day,
        month=MONTHS_NL[day.month - 1],
        year=day.year,
        date=dutch_date(day),
        emoji=summary["emoji"],
        summary=summary["description"],
        tmin=number(summary["temp_min"]),
        tmax=number(summary["temp_max"]),
    )


def build_body(forecasts, reference_city="Utrecht", footer=None):
    """Maak de Reddit-markdown voor het weerbericht."""
    summary = summarize(forecasts)
    day = forecasts[0].day

    wind = (
        f"{summary['wind_min']} Bft"
        if summary["wind_min"] == summary["wind_max"]
        else f"{summary['wind_min']} tot {summary['wind_max']} Bft"
    )
    lines = [
        f"**Verwachting voor {dutch_date(day)}** {summary['emoji']}",
        "",
        f"Landelijk **{number(summary['temp_min'])}° tot "
        f"{number(summary['temp_max'])}°**, {summary['description']}. "
        f"Wind uit {summary['direction_words']} ({summary['direction']}), {wind}.",
    ]
    if summary["rain_cities"]:
        lines.append("")
        lines.append(
            f"Kans op neerslag in {summary['rain_cities']} van de "
            f"{len(forecasts)} plaatsen."
        )
    if summary["max_gust"] >= 75:
        lines.append("")
        lines.append(
            f"⚠️ Zware windstoten tot "
            f"{number(summary['max_gust'])} km/u."
        )

    lines += [
        "",
        "| Plaats | Weer | Max | Min | Neerslag | Wind |",
        "|:---|:---|---:|---:|---:|:---|",
    ]
    for forecast in forecasts:
        rain = f"{number(forecast.precipitation, 1)} mm"
        if forecast.precipitation_chance is not None:
            rain += f" ({forecast.precipitation_chance}%)"
        lines.append(
            f"| {forecast.city} | {forecast.emoji} {forecast.description} "
            f"| {number(forecast.temp_max)}° | {number(forecast.temp_min)}° "
            f"| {rain} | {forecast.direction} {forecast.beaufort} Bft |"
        )

    reference = next(
        (f for f in forecasts if f.city == reference_city), forecasts[0]
    )
    if reference.sunrise and reference.sunset:
        lines += [
            "",
            f"Zon op **{reference.sunrise}** · onder **{reference.sunset}** "
            f"({reference.city})",
        ]

    lines += ["", "---", "", footer or DEFAULT_FOOTER]
    return "\n".join(lines)


DEFAULT_FOOTER = (
    "^(Bron: [Open-Meteo](https://open-meteo.com/) · windkracht in Beaufort, "
    "neerslag in mm per etmaal. Ik ben een bot; vragen of fouten? Stuur een "
    "bericht naar de moderators.)"
)


def build_post(forecasts, title_template, reference_city="Utrecht", footer=None):
    return (
        build_title(forecasts, title_template),
        build_body(forecasts, reference_city=reference_city, footer=footer),
    )
