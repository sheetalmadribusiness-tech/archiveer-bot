# Kopieer dit bestand naar config.py en vul je eigen waarden in.

# --- Reddit ---------------------------------------------------------------
REDDIT_CLIENT_ID     = "JOUW_CLIENT_ID"
REDDIT_CLIENT_SECRET = "JOUW_CLIENT_SECRET"
REDDIT_USER_AGENT    = "SubredditArchiver/1.0 by JOUW_REDDIT_GEBRUIKERSNAAM"

# Alleen nodig om te *plaatsen* (weerbot), niet om te archiveren.
REDDIT_USERNAME = "JOUW_BOT_ACCOUNT"
REDDIT_PASSWORD = "WACHTWOORD_VAN_HET_BOT_ACCOUNT"

# --- Archiver (archiver.py) ----------------------------------------------
SUBREDDIT_NAME   = "python"
LIMIT            = 1000
INCLUDE_COMMENTS = False
OUTPUT_DIR       = "output"

# --- Weerbot (weatherbot.py) ---------------------------------------------
WEATHER_SUBREDDIT = "JOUW_SUBREDDIT"   # zonder r/
WEATHER_POST_TIME = "19:45"            # Europe/Amsterdam

# Beschikbare velden: {emoji} {date} {weekday} {day} {month} {year}
#                     {summary} {tmin} {tmax}
WEATHER_TITLE_TEMPLATE = (
    "{emoji} Weerbericht voor morgen — {date}: {tmin}° tot {tmax}°, {summary}"
)

# Steden in de tabel: (naam, breedtegraad, lengtegraad).
# Laat op None staan voor de standaardlijst van 11 plaatsen door heel Nederland.
WEATHER_CITIES = None

WEATHER_REFERENCE_CITY   = "Utrecht"  # plaats voor zonop-/ondergang
WEATHER_FLAIR            = None       # bijv. "Weer"; moet bestaan in de sub
WEATHER_STICKY           = False      # post vastzetten (bot moet moderator zijn)
WEATHER_UNSTICKY_PREVIOUS = True      # gisteren losmaken voordat vandaag vastgezet wordt
WEATHER_MODEL            = None       # None = KNMI (Harmonie); "best_match" = mix van Open-Meteo
WEATHER_FOOTER           = None       # eigen ondertekst onder de tabel
