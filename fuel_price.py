"""Estrae prezzo medio benzina Bologna dal testo di Mappa Carburanti."""
import datetime as dt
import html
import json
import pathlib
import re
import time
import urllib.request
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

URL = "https://mappacarburanti.it/prezzi-benzina/bologna.html"
OUTPUT = pathlib.Path("docs/fuel-price.json")


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
        try:
            req = urllib.request.Request(
                URL,
                headers={"User-Agent": "Mozilla/5.0 (compatible; MeteoScooterBologna/1.0)",
                         "Accept": "text/html,application/xhtml+xml"},
            )
            with urllib.request.urlopen(req, timeout=25) as response:
                return response.read().decode("utf-8", errors="replace")
        except (OSError, TimeoutError) as exc:
            print(f"Download HTML tentativo {attempt}/3 fallito: {exc}", flush=True)
            if attempt == 3:
                raise
            time.sleep(attempt * 3)


def calculate():
    parser = TextExtractor()
    parser.feed(download())
    text = re.sub(r"\s+", " ", html.unescape(" ".join(parser.parts)))

    # Usa il testo visibile della pagina, non i CSV dei distributori.
    # La pagina può avere più formulazioni della frase e spazi Unicode.
    text = text.replace("\u00a0", " ").replace("\u202f", " ")
    date_match = re.search(
        r"(?:Oggi\s+|aggiornat[io]\s+il\s+)(\d{4}-\d{2}-\d{2})", text, re.I
    )
    price_match = re.search(
        r"prezzo\s+medio\s+(?:della?|di)\s+benzina\s+è\s*(?:di\s*)?"
        r"€?\s*([0-9]+[.,][0-9]{2,3})\s*/\s*L", text, re.I
    )
    if not date_match or not price_match:
        print("DIAGNOSTICA: HTML scaricato, lunghezza:", len(text), flush=True)
        print("DIAGNOSTICA: titolo/testo iniziale:", repr(text[:1100]), flush=True)
        print("DIAGNOSTICA: frasi contenenti 'benzina':",
              repr([text[max(0,m.start()-100):m.start()+150]
                    for m in list(re.finditer("benzina", text, re.I))[:5]]),
              flush=True)
        raise ValueError("Prezzo medio benzina Bologna o data non trovati nel testo HTML; controlla diagnostica nei log")
    date, price_text = date_match.group(1), price_match.group(1)

    price = float(price_text.replace(",", "."))
    if not 1.0 <= price <= 3.5:
        raise ValueError(f"Prezzo fuori intervallo: {price}")
    date_value = dt.date.fromisoformat(date)
    today = dt.datetime.now(ZoneInfo("Europe/Rome")).date()
    if date_value > today or (today - date_value).days > 2:
        raise ValueError(f"Rilevazione non recente ({date}): JSON precedente conservato")

    stations_match = re.search(r"su\s+(\d+)\s+distributori\s+monitorati", text, re.I)
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
    data = calculate()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(data)


if __name__ == "__main__":
    main()
