# Subreddit Archiver Bot

Archiveert posts (en optioneel reacties) van elk subreddit naar **JSON** en **CSV**.

## Vereisten

- Python 3.8+
- Reddit-account

## Installatie

```bash
git clone https://github.com/JOUW_GEBRUIKERSNAAM/subreddit-archiver-bot.git
cd subreddit-archiver-bot
pip install -r requirements.txt
cp config.example.py config.py
```

## Reddit API-toegang

1. Ga naar https://www.reddit.com/prefs/apps
2. Klik **"create another app..."**
3. Kies type **script**, redirect URI: `http://localhost`
4. Kopieer **Client ID** (onder de app-naam) en **Client Secret**

## Configuratie

Bewerk `config.py`:

| Variabele | Wat invullen |
|---|---|
| `REDDIT_CLIENT_ID` | 14-tekens ID van je app |
| `REDDIT_CLIENT_SECRET` | Secret van je app |
| `REDDIT_USER_AGENT` | bijv. `Archiver/1.0 by jouw_naam` |
| `SUBREDDIT_NAME` | subreddit zonder `r/` |
| `LIMIT` | aantal posts (`None` = alles) |
| `INCLUDE_COMMENTS` | `True` om ook reacties op te halen |

## Gebruik

```bash
python archiver.py
```

Output in de `output/` map:

```
output/
  python_20260401_143000.json
  python_20260401_143000.csv
```

## Let op

- `config.py` staat in `.gitignore` — commit je credentials nooit.
- Reddit rate-limit: ~60 req/min. Bij `LIMIT=None` kan dit uren duren.
- Verwijderde posts verschijnen als `[deleted]` / `[removed]`.
