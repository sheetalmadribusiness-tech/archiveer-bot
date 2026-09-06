"""Weerbot: plaatst elke dag om 19:45 de verwachting voor morgen op Reddit."""

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import praw

import weather
from weather import WeatherError

TIMEZONE = ZoneInfo("Europe/Amsterdam")
STATE_FILE = "weather_state.json"

DEFAULTS = {
    "WEATHER_SUBREDDIT": None,
    "WEATHER_POST_TIME": "19:45",
    "WEATHER_TITLE_TEMPLATE": "{emoji} Weerbericht voor morgen — {date}: {tmin}° tot {tmax}°, {summary}",
    "WEATHER_CITIES": weather.DEFAULT_CITIES,
    "WEATHER_REFERENCE_CITY": "Utrecht",
    "WEATHER_FLAIR": None,
    "WEATHER_STICKY": False,
    "WEATHER_UNSTICKY_PREVIOUS": True,
    "WEATHER_MODEL": weather.DEFAULT_MODEL,
    "WEATHER_FOOTER": None,
}


def load_settings():
    """Instellingen uit config.py, met omgevingsvariabelen als overrides.

    Zo werkt de bot zowel lokaal (config.py) als in CI/systemd (env vars).
    """
    settings = dict(DEFAULTS)
    settings.update({
        "REDDIT_CLIENT_ID": None,
        "REDDIT_CLIENT_SECRET": None,
        "REDDIT_USER_AGENT": "WeerbotNL/1.0",
        "REDDIT_USERNAME": None,
        "REDDIT_PASSWORD": None,
    })

    try:
        import config
    except ImportError:
        config = None
    if config is not None:
        for key in settings:
            # None in config.py betekent "gebruik de standaardwaarde".
            if hasattr(config, key) and getattr(config, key) is not None:
                settings[key] = getattr(config, key)

    for key in settings:
        if os.environ.get(key):
            settings[key] = os.environ[key]

    settings["WEATHER_STICKY"] = _as_bool(settings["WEATHER_STICKY"])
    settings["WEATHER_UNSTICKY_PREVIOUS"] = _as_bool(settings["WEATHER_UNSTICKY_PREVIOUS"])
    settings["WEATHER_CITIES"] = _as_cities(settings["WEATHER_CITIES"])
    return settings


def _as_bool(value):
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "ja", "yes", "on")
    return bool(value)


def _as_cities(value):
    """Steden als lijst van tuples, of als env-var: 'Naam:lat:lon,Naam:lat:lon'."""
    if not isinstance(value, str):
        return [tuple(city) for city in value]
    cities = []
    for entry in value.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":")
        if len(parts) != 3:
            raise SystemExit(f"Ongeldige stad in WEATHER_CITIES: {entry!r}")
        cities.append((parts[0].strip(), float(parts[1]), float(parts[2])))
    return cities


def parse_time(value):
    try:
        hour, minute = (int(part) for part in value.split(":"))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError
    except ValueError:
        raise SystemExit(f"Ongeldige tijd: {value!r}. Gebruik HH:MM, bijv. 19:45.")
    return hour, minute


def read_state(path=STATE_FILE):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def write_state(state, path=STATE_FILE):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)


def build_forecast_post(settings, target_day):
    forecasts = weather.fetch_forecast(
        cities=settings["WEATHER_CITIES"],
        day=target_day,
        model=settings["WEATHER_MODEL"],
    )
    return weather.build_post(
        forecasts,
        settings["WEATHER_TITLE_TEMPLATE"],
        reference_city=settings["WEATHER_REFERENCE_CITY"],
        footer=settings["WEATHER_FOOTER"],
    )


def check_credentials(settings):
    """Controleer vooraf of we uberhaupt kunnen plaatsen."""
    if not settings.get("WEATHER_SUBREDDIT"):
        raise SystemExit("WEATHER_SUBREDDIT is niet ingesteld.")
    missing = [
        key for key in
        ("REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USERNAME", "REDDIT_PASSWORD")
        if not settings.get(key)
    ]
    if missing:
        raise SystemExit(
            "Ontbrekende inloggegevens: " + ", ".join(missing) +
            ".\nPlaatsen vereist een script-app met gebruikersnaam en wachtwoord "
            "van het botaccount (zie README)."
        )


def make_reddit(settings):
    check_credentials(settings)
    return praw.Reddit(
        client_id=settings["REDDIT_CLIENT_ID"],
        client_secret=settings["REDDIT_CLIENT_SECRET"],
        user_agent=settings["REDDIT_USER_AGENT"],
        username=settings["REDDIT_USERNAME"],
        password=settings["REDDIT_PASSWORD"],
    )


def submit_post(settings, title, body, state):
    reddit = make_reddit(settings)
    subreddit_name = settings["WEATHER_SUBREDDIT"].lstrip("/").removeprefix("r/")
    subreddit = reddit.subreddit(subreddit_name)

    flair_id = None
    if settings["WEATHER_FLAIR"]:
        flair_id = find_flair_id(subreddit, settings["WEATHER_FLAIR"])
        if flair_id is None:
            print(f"Let op: flair {settings['WEATHER_FLAIR']!r} niet gevonden; "
                  "post wordt zonder flair geplaatst.")

    submission = subreddit.submit(title, selftext=body, flair_id=flair_id)
    print(f"Geplaatst: https://reddit.com{submission.permalink}")

    if settings["WEATHER_STICKY"]:
        previous_id = state.get("last_post_id")
        if settings["WEATHER_UNSTICKY_PREVIOUS"] and previous_id:
            unsticky(reddit, previous_id)
        try:
            # bottom=True laat een eventuele aankondiging bovenaan staan.
            submission.mod.sticky(state=True, bottom=True)
            print("Post vastgezet.")
        except Exception as exc:
            print(f"Vastzetten mislukt (is de bot moderator?): {exc}")

    return submission


def find_flair_id(subreddit, wanted):
    try:
        for template in subreddit.flair.link_templates.user_selectable():
            if template["flair_text"].strip().lower() == wanted.strip().lower():
                return template["flair_template_id"]
    except Exception as exc:
        print(f"Flairs ophalen mislukt: {exc}")
    return None


def unsticky(reddit, submission_id):
    try:
        reddit.submission(id=submission_id).mod.sticky(state=False)
        print(f"Vorige post ({submission_id}) losgemaakt.")
    except Exception as exc:
        print(f"Losmaken van vorige post mislukt: {exc}")


def post_once(settings, target_day=None, dry_run=False, force=False, state_file=STATE_FILE):
    """Plaats één weerbericht. Geeft True terug als er iets geplaatst is."""
    target_day = target_day or datetime.now(TIMEZONE).date() + timedelta(days=1)
    if not dry_run:
        # Eerst de instellingen controleren; scheelt een onnodige API-aanvraag.
        check_credentials(settings)
    state = read_state(state_file)

    if not force and not dry_run and state.get("last_forecast_day") == target_day.isoformat():
        print(f"Verwachting voor {target_day} is al geplaatst; overgeslagen.")
        return False

    try:
        title, body = build_forecast_post(settings, target_day)
    except WeatherError as exc:
        print(f"Fout: {exc}", file=sys.stderr)
        return False

    if dry_run:
        print(f"--- TITEL ---\n{title}\n\n--- TEKST ---\n{body}")
        return True

    submission = submit_post(settings, title, body, state)
    state.update({
        "last_forecast_day": target_day.isoformat(),
        "last_post_id": submission.id,
        "last_posted_at": datetime.now(TIMEZONE).isoformat(timespec="seconds"),
    })
    write_state(state, state_file)
    return True


def next_run(now, hour, minute):
    run_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if run_at <= now:
        run_at += timedelta(days=1)
    return run_at


def run_loop(settings, post_time, dry_run=False, state_file=STATE_FILE):
    """Blijf draaien en plaats elke dag op het ingestelde tijdstip."""
    hour, minute = parse_time(post_time)
    print(f"Weerbot actief; plaatst dagelijks om {post_time} (Europe/Amsterdam).")
    while True:
        now = datetime.now(TIMEZONE)
        run_at = next_run(now, hour, minute)
        seconds = (run_at - now).total_seconds()
        print(f"Volgende post: {run_at:%Y-%m-%d %H:%M %Z} "
              f"(over {seconds / 3600:.1f} uur)")
        # In stukjes slapen, zodat een zomertijdsprong snel wordt opgemerkt.
        while seconds > 0:
            time.sleep(min(seconds, 300))
            seconds = (run_at - datetime.now(TIMEZONE)).total_seconds()
        try:
            post_once(settings, dry_run=dry_run, state_file=state_file)
        except SystemExit:
            raise
        except Exception as exc:  # de lus mag nooit stoppen door één misser
            print(f"Plaatsen mislukt: {exc}", file=sys.stderr)


def within_window(post_time, minutes=20, now=None):
    """True als het nu (Amsterdamse tijd) rond het geplande tijdstip is.

    Handig voor cron-diensten die in UTC draaien: plan twee tijden in en laat
    deze controle bepalen welke van de twee de juiste is, ook rond de
    zomertijdwissel.
    """
    hour, minute = parse_time(post_time)
    now = now or datetime.now(TIMEZONE)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return abs((now - target).total_seconds()) <= minutes * 60


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Plaatst dagelijks de weersverwachting voor Nederland op Reddit."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="toon de post, plaats hem niet")
    parser.add_argument("--loop", action="store_true",
                        help="blijf draaien en plaats elke dag op het ingestelde tijdstip")
    parser.add_argument("--date", metavar="JJJJ-MM-DD",
                        help="verwachting voor deze dag (standaard: morgen)")
    parser.add_argument("--time", dest="post_time",
                        help="tijdstip voor --loop (standaard uit config, 19:45)")
    parser.add_argument("--guard", action="store_true",
                        help="stop zonder te plaatsen als het nu niet rond het "
                             "ingestelde tijdstip is (voor cron in UTC)")
    parser.add_argument("--guard-minutes", type=int, default=20, metavar="N",
                        help="speling in minuten voor --guard (standaard 20)")
    parser.add_argument("--force", action="store_true",
                        help="plaats ook als er vandaag al een bericht stond")
    parser.add_argument("--model", metavar="NAAM",
                        help=f"weermodel (standaard {weather.DEFAULT_MODEL}; "
                             "'best_match' voor de standaardmix van Open-Meteo)")
    args = parser.parse_args(argv)

    settings = load_settings()
    post_time = args.post_time or settings["WEATHER_POST_TIME"]
    if args.model:
        settings["WEATHER_MODEL"] = args.model

    if args.loop:
        run_loop(settings, post_time, dry_run=args.dry_run)
        return 0

    if args.guard and not within_window(post_time, minutes=args.guard_minutes):
        now = datetime.now(TIMEZONE)
        print(f"Het is {now:%H:%M} in Amsterdam, niet rond {post_time}; niets gedaan.")
        return 0

    target_day = date.fromisoformat(args.date) if args.date else None
    posted = post_once(settings, target_day=target_day,
                       dry_run=args.dry_run, force=args.force)
    return 0 if posted else 1


if __name__ == "__main__":
    sys.exit(main())
