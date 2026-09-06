# Subreddit Archiver Bot + Weerbot

Twee bots die dezelfde Reddit-configuratie delen:

- **`archiver.py`** — archiveert posts (en optioneel reacties) van elk subreddit naar **JSON** en **CSV**.
- **`weatherbot.py`** — plaatst elke dag om **19:45** de weersverwachting voor **morgen** in Nederland.

## Vereisten

- Python 3.10+
- Reddit-account (voor de weerbot: een apart botaccount)

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

Voor de weerbot staan de extra instellingen verderop bij [Weerbot](#weerbot).

## Gebruik: archiver

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


---

# Weerbot

Plaatst elke dag om 19:45 (Europe/Amsterdam) een tekstpost met de verwachting
voor **de volgende dag**: een landelijke samenvatting plus een tabel met elf
plaatsen verspreid over het land.

Voorbeeld:

> **Verwachting voor dinsdag 7 april** 🌦️
>
> Landelijk **6° tot 19°**, lichte regen. Wind uit het zuidwesten (ZW), 3 tot 6 Bft.
>
> | Plaats | Weer | Max | Min | Neerslag | Wind |
> |:---|:---|---:|---:|---:|:---|
> | Amsterdam | ☁️ bewolkt | 16° | 8° | 1,4 mm (70%) | WZW 5 Bft |
> | Rotterdam | 🌦️ lichte regen | 16° | 8° | 3,1 mm (85%) | ZW 5 Bft |

## Waar de data vandaan komt

De bot rekent met het **KNMI-model**: Harmonie AROME, het model dat het KNMI
zelf voor Nederland draait — 2 km resolutie, elk uur ververst en ruim 48 uur
vooruit, dus de verwachting voor morgen komt volledig uit Harmonie.

De data wordt opgehaald via [Open-Meteo](https://open-meteo.com/), dat het
KNMI-model kant-en-klaar aanbiedt (`knmi_seamless`) zonder API-sleutel en
gratis voor niet-commercieel gebruik. Het alternatief is het
[KNMI Open Data Platform](https://dataplatform.knmi.nl/), maar dat levert de
ruwe Harmonie-uitvoer als GRIB/netCDF-bestanden van honderden megabytes per
run, die je zelf moet uitpakken en op coordinaten moet uitlezen — voor een
dagelijks weerberichtje is dat veel zwaarder dan nodig.

> **Eén uitzondering:** de *neerslagkans* volgt uit een ensemble en zit niet in
> een enkel deterministisch model. Levert het KNMI-model die kolom niet, dan
> vult de bot alleen dat ene percentage aan uit de standaardmix van Open-Meteo.
> Temperatuur, weertype, wind en neerslag blijven altijd van het KNMI.

Wil je toch de standaardmix van Open-Meteo (die per locatie het best passende
model kiest), zet dan `WEATHER_MODEL = "best_match"`, of draai eenmalig
`python weatherbot.py --model best_match --dry-run` om de twee te vergelijken.

## Inloggegevens aanmaken

Archiveren kan read-only; **plaatsen niet**. De weerbot logt in als het
botaccount zelf, dus je hebt vier gegevens nodig: client-ID, secret,
gebruikersnaam en wachtwoord.

**1. Maak een apart account voor de bot.** Bijvoorbeeld `jouwsub-weerbot`. Doe
dit niet met je eigen moderatoraccount: als het wachtwoord ooit uitlekt, raak
je anders je eigen account kwijt. Zet **geen** 2FA aan op het botaccount —
Reddit verwacht dan `wachtwoord:123456` als wachtwoord, en die code verloopt
binnen een halve minuut, dus een bot die dagelijks draait loopt daarop vast.

**2. Maak een app aan.** Log in als het botaccount, ga naar
https://www.reddit.com/prefs/apps en klik onderaan **"create another app..."**:

| Veld | Wat invullen |
|---|---|
| name | `weerbot` |
| type | **script** ← belangrijk; andere types kunnen niet met wachtwoord inloggen |
| description | mag leeg |
| about url | mag leeg |
| redirect uri | `http://localhost` |

Klik **create app**. Je krijgt dan:

- **client-ID**: de reeks van 14 tekens direct onder de naam van de app,
  links bovenin het grijze blok (er staat *"personal use script"* boven).
- **secret**: de langere reeks achter het label **secret**.

**3. Zet de gegevens neer.** Kies één van beide plekken — nooit allebei, en zet
ze nooit in een bestand dat je commit:

*Draai je hem op je eigen machine?* Vul `config.py` in (die staat in
`.gitignore`, dus hij komt nooit in git terecht):

| Variabele | Wat invullen |
|---|---|
| `REDDIT_CLIENT_ID` | de 14 tekens onder de app-naam |
| `REDDIT_CLIENT_SECRET` | de reeks achter *secret* |
| `REDDIT_USERNAME` | gebruikersnaam van het botaccount |
| `REDDIT_PASSWORD` | wachtwoord van het botaccount |

*Draai je hem via GitHub Actions?* Zet ze als **repository secrets** onder
*Settings → Secrets and variables → Actions → New repository secret*, met exact
deze namen: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`,
`REDDIT_PASSWORD`. GitHub laat ze daarna nooit meer zien en filtert ze uit de
logs. De subreddit zelf is geen geheim: die zet je als *variable*
`WEATHER_SUBREDDIT` op hetzelfde scherm.

**4. Controleer of het werkt** — dit plaatst nog niets:

```bash
python weatherbot.py --check
```

Je ziet dan bij welk account je inlogt, of de subreddit bereikbaar is en welke
moderatorrechten de bot heeft.

> **Deel deze vier gegevens met niemand** — ook niet in een chat, een issue of
> een screenshot. Samen geven ze volledige controle over het botaccount. Is er
> iets uitgelekt? Klik op *edit* bij de app voor een nieuw secret en wijzig het
> wachtwoord van het botaccount.

## Weerbot-instellingen

| Variabele | Standaard | Betekenis |
|---|---|---|
| `WEATHER_SUBREDDIT` | — | subreddit zonder `r/` |
| `WEATHER_POST_TIME` | `"19:45"` | tijdstip, altijd Europe/Amsterdam |
| `WEATHER_TITLE_TEMPLATE` | zie `config.example.py` | velden: `{emoji}` `{date}` `{weekday}` `{day}` `{month}` `{year}` `{summary}` `{tmin}` `{tmax}` |
| `WEATHER_CITIES` | 11 plaatsen | lijst van `("Naam", breedtegraad, lengtegraad)` |
| `WEATHER_REFERENCE_CITY` | `"Utrecht"` | plaats voor zonsopgang/-ondergang |
| `WEATHER_FLAIR` | `None` | naam van een bestaande post-flair |
| `WEATHER_STICKY` | `False` | post vastzetten (bot moet moderator zijn) |
| `WEATHER_UNSTICKY_PREVIOUS` | `True` | het bericht van gisteren eerst losmaken |
| `WEATHER_MODEL` | `"knmi_seamless"` | weermodel; `"best_match"` voor de standaardmix van Open-Meteo |
| `WEATHER_FOOTER` | `None` | eigen ondertekst onder de tabel |

Elke instelling kan ook als omgevingsvariabele — handig voor GitHub Actions of
systemd, waar je geen `config.py` wilt neerzetten. Steden zien er als
omgevingsvariabele zo uit: `WEATHER_CITIES="Amsterdam:52.37:4.89,Groningen:53.22:6.57"`.

## Gebruik: weerbot

```bash
python weatherbot.py --check        # controleer inloggegevens en rechten
python weatherbot.py --dry-run      # laat de post zien, plaatst niets
python weatherbot.py                # plaats nu het bericht voor morgen
python weatherbot.py --loop         # blijf draaien, plaats elke dag om 19:45
python weatherbot.py --date 2026-04-09 --dry-run   # andere dag bekijken
```

Overige opties: `--time HH:MM` (ander tijdstip voor `--loop`), `--force`
(plaats ook als er vandaag al een bericht stond), `--model NAAM` (ander
weermodel), `--guard` (zie hieronder).

Een geplaatst bericht wordt onthouden in `weather_state.json`, zodat een
herstart of een dubbele cron-run niet twee keer hetzelfde plaatst. Dat bestand
staat in `.gitignore`.

## Bot activeren op je subreddit

1. **Testen** — draai `python weatherbot.py --check` (inloggegevens en rechten)
   en `python weatherbot.py --dry-run` (klopt de tekst?).
2. **Bot uitnodigen** — als moderator: *Mod Tools → Moderators → Invite moderator*.
   Voor alleen plaatsen zijn geen rechten nodig; voor `WEATHER_STICKY = True`
   heeft de bot **Posts** (`posts`) nodig. Accepteer de uitnodiging in de inbox
   van het botaccount.
3. **Eerste post handmatig** — draai `python weatherbot.py` en controleer het
   resultaat in de sub.
4. **Inplannen** — kies één van de manieren hieronder.
5. Voeg het botaccount toe aan de *approved submitters* als je sub daarop
   filtert, en denk aan een eventuele karma- of accountleeftijd-drempel in
   AutoModerator: een gloednieuw botaccount wordt anders stilzwijgend
   tegengehouden.

## Inplannen

**Eigen server (het meest punctueel)** — met systemd, zie het meegeleverde
`weerbot.service`:

```bash
sudo cp weerbot.service /etc/systemd/system/
sudo systemctl enable --now weerbot
journalctl -u weerbot -f
```

Of met cron, op een machine die zelf op Nederlandse tijd staat:

```cron
45 19 * * * cd /opt/archiveer-bot && /opt/archiveer-bot/.venv/bin/python weatherbot.py >> weerbot.log 2>&1
```

**GitHub Actions (geen server nodig)** — `.github/workflows/weatherbot.yml`
staat klaar. Zet in de repo-instellingen:

- *Secrets*: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`, `REDDIT_PASSWORD`
- *Variables*: `WEATHER_SUBREDDIT`, en eventueel `WEATHER_STICKY` / `WEATHER_FLAIR`

De workflow draait op 17:45 én 18:45 UTC — dat zijn de zomer- en wintervariant
van 19:45 Nederlandse tijd. `--guard` laat alleen het juiste moment door, dus er
verschijnt één post per dag, ook na de klokwissel. Let op: Actions-cron kan
enkele minuten later starten dan gepland en `weather_state.json` blijft daar
niet bewaard; op een eigen server is de tijd nauwkeuriger.

Met *Run workflow* in het Actions-tabblad test je de bot handmatig (standaard
als dry-run).

## Tests

```bash
python -m unittest -v
```

De tests draaien zonder netwerk: ze voeden een opgeslagen Open-Meteo-antwoord
aan de opmaakcode en controleren de omrekening naar Beaufort en windrichting,
de tabel, de zomertijdlogica, het inlezen van de instellingen en dat het
KNMI-model daadwerkelijk wordt opgevraagd (inclusief de terugval voor de
neerslagkans).
