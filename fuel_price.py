"""Media giornaliera benzina self nel Comune di Bologna dai CSV MIMIT."""
import csv
import io
import json
import pathlib
import statistics
import urllib.request
import time
import urllib.error
import datetime as dt
from zoneinfo import ZoneInfo

BASE = "https://www.mimit.gov.it/images/exportCSV/"
OUTPUT = pathlib.Path("docs/fuel-price.json")

def download(name):
    hosts = [
        "https://www.mimit.gov.it/images/exportCSV/",
        "https://www.mise.gov.it/images/exportCSV/",
    ]
    errors = []
    for host in hosts:
        for attempt in range(1, 3):
            url = host + name
            request = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; MeteoScooterBologna/1.0)",
                "Accept": "text/csv,*/*",
            })
            try:
                print(f"Download {name}: {host} tentativo {attempt}/2", flush=True)
                with urllib.request.urlopen(request, timeout=25) as response:
                    data = response.read().decode("utf-8-sig", errors="replace").splitlines()
                if len(data) < 3:
                    raise ValueError("CSV incompleto")
                rows = list(csv.DictReader(io.StringIO("\n".join(data[1:])), delimiter="|"))
                if not rows or "idImpianto" not in rows[0]:
                    raise ValueError("Formato CSV non riconosciuto")
                return data[0], rows
            except (OSError, ValueError, UnicodeError) as exc:
                errors.append(f"{url} tentativo {attempt}: {exc}")
                print(f"Errore download: {exc}", flush=True)
                if attempt == 1:
                    time.sleep(3)
    raise RuntimeError("Download MIMIT non riuscito. " + " | ".join(errors))

def field(row, name):
    return next((str(v).strip() for k, v in row.items() if k and k.strip().lower() == name.lower()), "")

def calculate():
    _, stations = download("anagrafica_impianti_attivi.csv")
    extraction, prices = download("prezzo_alle_8.csv")
    ids = {field(row, "idImpianto") for row in stations
           if field(row, "Comune").casefold() == "bologna"
           and field(row, "Provincia").casefold() in ("bo", "bologna")}
    by_station = {}
    for row in prices:
        ident = field(row, "idImpianto")
        if ident not in ids or field(row, "descCarburante").casefold() != "benzina" or field(row, "isSelf") != "1":
            continue
        try:
            price = float(field(row, "prezzo").replace(",", "."))
        except ValueError:
            continue
        if 1.0 <= price <= 3.5:
            by_station[ident] = price
    if len(by_station) < 5:
        raise ValueError("Troppi pochi prezzi validi per Bologna")
    return {"city": "Bologna", "fuel": "Benzina", "service": "self",
            "price_eur_l": round(statistics.mean(by_station.values()), 3),
            "stations": len(by_station), "extraction": extraction,
            "updated_at": dt.datetime.now(ZoneInfo("Europe/Rome")).isoformat(timespec="seconds"),
            "source": "MIMIT Osservaprezzi Carburanti"}

def main():
    data = calculate()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(data)

if __name__ == "__main__":
    main()
