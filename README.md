# 🛵 Meteo Scooter Bologna

Previsioni meteo spazio-temporali per gli spostamenti in scooter a Bologna.

## Pagina web
La pagina statica si trova in `docs/index.html`. Per pubblicarla: **Settings → Pages → Deploy from a branch → main → /docs → Save**.

La pagina permette di scegliere partenza, arrivo, data e ora, e aggiungere regioni salvate nel browser. Per ogni tragitto controlla partenza, metà strada e arrivo, considerando i tempi stimati di percorrenza e tre orari di partenza (−30, 0, +30 minuti).

## Email ogni sera alle 21 (ora italiana)
Il workflow `.github/workflows/meteo.yml` esegue `send_email.py` per il giorno successivo:
- 09:00: casa → fisica
- 18:30: fisica → casa

In **Settings → Secrets and variables → Actions**, crea:
- `GMAIL_USER`: indirizzo Gmail mittente
- `GMAIL_APP_PASSWORD`: password per le app Google (non la password principale)

Destinatario predefinito: `giacomoubaldi@gmail.com`. Per un test: **Actions → Meteo scooter serale → Run workflow**.

Il workflow usa 19:00 e 20:00 UTC e invia solo quando in Italia sono le 21. GitHub Actions può subire ritardi: in tal caso il controllo sull'ora può saltare l'invio.

## Limiti
Open-Meteo (previsioni), Nominatim (geocoding), OSRM (percorso) sono servizi pubblici che possono essere temporaneamente indisponibili. La durata scooter è stimata con 25 km/h + 3 minuti. L'interpolazione non aumenta la risoluzione reale delle previsioni. Le regioni aggiunte nel browser non modificano le email automatiche.
