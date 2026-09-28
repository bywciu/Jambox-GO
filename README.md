# Jambox-GO

Lekki proxy HLS dla Jambox/SGT.

## Uruchomienie lokalne

```bash
python3 main.py
```

Przy pierwszym uruchomieniu program utworzy:

- `data/config.json`
- `data/credentials.json`
- `data/cookie.json`

Uzupełnij dane logowania w `data/credentials.json` i uruchom ponownie.

## Konfiguracja

Przykładowe `data/config.json`:

```json
{
    "host": "172.0.0.1",
    "port": 8080,
    "debug": false,
    "quality": "high",
    "threaded": true,
    "hls": true
}
```

`host` określa adres hosta używany w wygenerowanej playliście `tv.m3u`.
W Dockerze powinien to być adres IP hosta w LAN, a nie adres kontenera.

`port` jest portem HTTP proxy i można go zmienić w `config.json`.
Przy Dockerze trzeba wtedy zmienić również mapowanie `ports`.

## Docker

```bash
docker compose up -d --build
```

Konfiguracja i cookie są przechowywane w lokalnym katalogu `data/`.

Domyślnie proxy jest dostępne na:

```text
http://<host>:<port>/
```

Kanały:

```text
http://<host>:<port>/0
http://<host>:<port>/1
...
```
