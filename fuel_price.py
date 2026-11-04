"""Media giornaliera benzina self nel Comune di Bologna dai CSV MIMIT."""
import csv
import io
import json
import pathlib
import statistics
import urllib.request
import datetime as dt
from zoneinfo import ZoneInfo

BASE = "https://www.mimit.gov.it/images/exportCSV/"
OUTPUT = pathlib.Path("docs/fuel-price.json")

def download(name):
    request = urllib.request.Request(BASE + name, headers={"User-Agent": "MeteoScooterBologna/1.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read().decode("utf-8-sig", errors="replace").splitlines()
    if len(data) < 3:
        raise ValueError("CSV incompleto: " + name)
    return data[0], list(csv.DictReader(io.StringIO("\n".join(data[1:])), delimiter="|"))

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
