"""Estrae prezzo medio benzina Bologna dal testo di Mappa Carburanti."""
import datetime as dt
import html
import json
import pathlib
import re
import time
import urllib.request
import urllib.parse
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

URL = "https://mappacarburanti.it/prezzi-benzina/bologna.html"
OUTPUT = pathlib.Path("docs/fuel-price.json")
API_URL = "https://mappacarburanti.it/api/prezzi/citta/bologna.json"


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def download():
    for attempt in range(1, 4):
        # URL sempre diverso per evitare copie HTML memorizzate nelle cache.
        query = urllib.parse.urlencode({"_refresh": time.time_ns()})
        url = URL + "?" + query
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "it-IT,it;q=0.9,en;q=0.5",
                    "Cache-Control": "no-cache, no-store, max-age=0",
                    "Pragma": "no-cache",
                },
            )
            print(f"Richiesta HTML (tentativo {attempt}/3): {url}", flush=True)
            with urllib.request.urlopen(req, timeout=25) as response:
                print(
                    f"HTTP {response.status}; URL finale: {response.url}; "
                    f"Age: {response.headers.get('Age', '-')}; "
                    f"Cache: {response.headers.get('CF-Cache-Status', '-')}; "
                    f"Last-Modified: {response.headers.get('Last-Modified', '-')}",
                    flush=True,
                )
                return response.read().decode("utf-8", errors="replace")
        except (OSError, TimeoutError) as exc:
            print(f"Download HTML tentativo {attempt}/3 fallito: {exc}", flush=True)
            if attempt == 3:
                raise
            time.sleep(attempt * 3)



def download_api():
    req = urllib.request.Request(
        API_URL + "?_refresh=" + str(time.time_ns()),
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Firefox/128.0",
            "Accept": "application/json,*/*",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        print(f"API HTTP {response.status}; Content-Type: {response.headers.get('Content-Type')}", flush=True)
        return json.load(response)


def parse_api(data):
    """Accetta schemi JSON comuni, senza confondere minimo e prezzo medio."""
    print("API struttura:", repr(data)[:1800], flush=True)
    if not isinstance(data, dict):
        raise ValueError("La risposta API non è un oggetto JSON")
    candidates = [data]
    for key in ("data", "city", "citta", "prices", "prezzi", "fuels", "carburanti", "summary", "riepilogo"):
        nested = data.get(key)
        if isinstance(nested, dict):
            candidates.append(nested)
            for fuel_key in ("benzina", "Benzina", "gasoline", "petrol"):
                if isinstance(nested.get(fuel_key), dict):
                    candidates.append(nested[fuel_key])
    for key in ("benzina", "Benzina", "gasoline", "petrol"):
        if isinstance(data.get(key), dict):
            candidates.append(data[key])

    def date_value(value):
        if isinstance(value, str):
            match = re.search(r"\d{4}-\d{2}-\d{2}", value)
            if match:
                return match.group()
        return None

    date = None
    for obj in candidates:
        for key in ("extraction", "extraction_date", "data_estrazione", "date",
                    "updated_at", "last_updated", "data_aggiornamento", "dataset_date"):
            date = date_value(obj.get(key))
            if date:
                break
        if date:
            break
    if not date:
        raise ValueError("API: data rilevazione assente o schema non riconosciuto")

    for obj in candidates:
        for key in ("price_eur_l", "avg_price", "average_price", "prezzo_medio",
                    "prezzoMedio", "media", "average", "avg"):
            val = obj.get(key)
            if isinstance(val, dict):
                continue
            try:
                price = float(str(val).replace(",", "."))
            except (TypeError, ValueError):
                continue
            if 1.0 <= price <= 3.5:
                stations = next((obj[k] for k in ("stations", "distributori", "count", "n_stations")
                                 if isinstance(obj.get(k), int)), None)
                return {
                    "city": "Bologna", "fuel": "Benzina", "service": "self",
                    "price_eur_l": round(price, 3), "stations": stations,
                    "extraction": date,
                    "updated_at": dt.datetime.now(ZoneInfo("Europe/Rome")).isoformat(timespec="seconds"),
                    "source": "Mappa Carburanti Italia (dati MIMIT, licenza CC0)",
                    "source_url": API_URL,
                }
    raise ValueError("API: prezzo medio benzina assente o schema non riconosciuto")

def calculate():
    parser = TextExtractor()
    parser.feed(download())
    text = re.sub(r"\s+", " ", html.unescape(" ".join(parser.parts)))

    # Usa il testo visibile della pagina, non i CSV dei distributori.
    # La pagina può avere più formulazioni della frase e spazi Unicode.
    text = text.replace("\u00a0", " ").replace("\u202f", " ")
    # La pagina statica usa "Nell’estrazione MIMIT del YYYY-MM-DD a Bologna".
    date_match = re.search(
        r"estrazione\s+MIMIT\s+del\s+(\d{4}-\d{2}-\d{2})", text, re.I
    )
    price_match = re.search(
        r"prezzo\s+medio\s+(?:della?|di)\s+benzina\s+è\s*(?:di\s*)?"
        r"€?\s*([0-9]+[.,][0-9]{2,3})\s*/\s*L", text, re.I
    )
    if not date_match or not price_match:
        print("DIAGNOSTICA: testo HTML:", repr(text[:1500]), flush=True)
        raise ValueError("Prezzo medio benzina Bologna o data non trovati nel testo HTML")
    date, price_text = date_match.group(1), price_match.group(1)
    print(f"Rilevazione ricevuta dal sito: {date}; prezzo: {price_text} €/L", flush=True)

    price = float(price_text.replace(",", "."))
    if not 1.0 <= price <= 3.5:
        raise ValueError(f"Prezzo fuori intervallo: {price}")
    date_value = dt.date.fromisoformat(date)
    today = dt.datetime.now(ZoneInfo("Europe/Rome")).date()
    if date_value > today or (today - date_value).days > 2:
        raise ValueError(f"Rilevazione non recente ({date}): JSON precedente conservato")

    stations_match = re.search(r"su\s+(\d+)\s+distributori", text, re.I)
    return {
        "city": "Bologna",
        "fuel": "Benzina",
        "service": "self",
        "price_eur_l": round(price, 3),
        "stations": int(stations_match.group(1)) if stations_match else None,
        "extraction": date,
        "updated_at": dt.datetime.now(ZoneInfo("Europe/Rome")).isoformat(timespec="seconds"),
        "source": "Mappa Carburanti (dati MIMIT)",
        "source_url": URL,
    }


def main():
    try:
        data = parse_api(download_api())
        print("Prezzo recuperato dalla API JSON", flush=True)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"API non utilizzabile: {exc}. Provo HTML come fallback.", flush=True)
        data = calculate()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(data)


if __name__ == "__main__":
    main()
