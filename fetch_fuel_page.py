"""Extract Bologna self-service petrol average from OpenCarburanti HTML."""
import datetime as dt
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import urllib.request

URL = "https://www.opencarburanti.it/prezzi-carburanti/emilia-romagna/bologna/bologna"
OUTPUT = Path("docs/fuel-price.json")

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)

def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 (compatible; MeteoScooter/1.0)"})
    with urllib.request.urlopen(req, timeout=25) as response:
        page = response.read().decode("utf-8", errors="replace")
    parser = TextParser()
    parser.feed(page)
    content = re.sub(r"\s+", " ", html.unescape(" ".join(parser.parts)))
    match = re.search(r"benzina self service costa in media\s*([0-9]+[,.][0-9]{2,3})\s*euro/L", content, re.I)
    date_match = re.search(r"Ultimo aggiornamento:\s*(\d{2})/(\d{2})/(\d{4})", content, re.I)
    if not match or not date_match:
        raise ValueError("Prezzo o data non trovati nella pagina OpenCarburanti")
    price = float(match.group(1).replace(",", "."))
    date = f"{date_match.group(3)}-{date_match.group(2)}-{date_match.group(1)}"
    if not 1 < price < 3.5:
        raise ValueError("Prezzo fuori intervallo")
    data = {"city": "Bologna", "fuel": "Benzina", "service": "self",
            "price_eur_l": price, "extraction": date,
            "source": "OpenCarburanti / MIMIT", "source_url": URL,
            "checked_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(data)

if __name__ == "__main__":
    main()
