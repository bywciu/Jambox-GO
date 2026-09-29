# Jambox-GO

Proxy HLS dla Jambox GO z obsługą Plex/HDHomeRun oraz EPG.

## Uruchomienie lokalne

```bash
python3 main.py
```

Przy pierwszym uruchomieniu program utworzy w katalogu `data`:

- `config.json`
- `credentials.json`
- `cookie.json`

Uzupełnij dane logowania w `data/credentials.json` i uruchom program ponownie.

## Konfiguracja

Przykładowe `data/config.json`:

```json
{
    "host": "127.0.0.1",
    "port": 8080,
    "debug": false,
    "quality": "high",
    "threaded": true,
    "hls": true,
    "tuners": 4
}
```

- `host` — adres hosta używany w adresach generowanych dla klientów.
- `port` — port HTTP proxy.
- `debug` — włącza logowanie diagnostyczne.
- `quality` — jakość strumienia.
- `threaded` — obsługa żądań w trybie wielowątkowym.
- `hls` — użycie strumieni HLS.
- `tuners` — liczba tunerów zgłaszana klientom HDHomeRun/Plex.

## Playlist i Plex / HDHomeRun

Playlistę M3U udostępnia endpoint:

```text
http://<host>:<port>/playlist.m3u
```

Dostępne są również endpointy HDHomeRun:

```text
/discover.json
/device.xml
/lineup.json
/lineup_status.json
```

## EPG

EPG jest dostępne w formacie XMLTV pod adresem:

```text
http://<host>:<port>/xmltv.xml
```

## Docker

```bash
docker compose up -d --build
```

Katalog `data` jest przechowywany poza kontenerem i zawiera konfigurację oraz dane potrzebne aplikacji.
