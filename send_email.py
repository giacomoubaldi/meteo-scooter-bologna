"""Invia ogni sera il meteo scooter per il giorno successivo."""
import datetime as dt
import html
import os
import smtplib
import json
import urllib.request
import urllib.parse
from email.message import EmailMessage
from meteo_core import TZ, REGIONS, evaluate, advice

def trip(title, origin, destination, time, day):
    departure = dt.datetime.combine(day, dt.time.fromisoformat(time), tzinfo=TZ)
    result = evaluate(REGIONS[origin], REGIONS[destination], departure)
    return trip_result(title, origin, destination, time, result)

def trip_result(title, origin, destination, time, result):
    def fmt(value, unit="", digits=0):
        return "n.d." if value is None else f"{value:.{digits}f}{unit}"
    rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            html.escape(point["name"]),
            point["samples"][1]["time"][11:16],
            fmt(point["samples"][1]["probability"], "%"),
            fmt(point["samples"][1]["rain_hour"], " mm/h", 2),
        )
        for point in result["points"]
    )
    return (
        f"<h2>{title} — {time}</h2>"
        f"<p>{origin} → {destination}: {result['distance_km']} km, circa {result['duration_minutes']} minuti.</p>"
        "<table border='1' cellpadding='7'><tr><th>Punto</th><th>Ora</th>"
        f"<th>Probabilità pioggia</th><th>Pioggia</th></tr>{rows}</table>"
        f"<p>Controllo partenze ±30 min: probabilità massima {fmt(result['max_probability'], '%')}, "
        f"pioggia massima {fmt(result['max_rain_hour'], ' mm/h', 2)}, "
        f"vento massimo {fmt(result['max_wind'], ' km/h')}.</p>"
        f"<p><strong>{html.escape(advice(result))}</strong></p>"
    )

def calendar_trips(day):
    """Read the weekly schedule from the repository checked out by GitHub Actions."""
    with open("data/config.json", encoding="utf-8") as source:
        payload = json.load(source)
    regions = {**REGIONS, **payload.get("tappe", {})}
    trips = sorted(
        (item for item in payload.get("calendar", []) if item.get("day") == day.weekday()),
        key=lambda item: item.get("time", ""),
    )
    return regions, trips

def main():
    now = dt.datetime.now(TZ)
    if os.getenv("SCHEDULED") == "true" and now.hour != 21:
        print("Non sono le 21 in Italia: nessuna email.")
        return
    tomorrow = (now + dt.timedelta(days=1)).date()
    regions, planned = calendar_trips(tomorrow)
    body = ""
    for item in planned:
        origin, destination = item["from"], item["to"]
        if origin not in regions or destination not in regions:
            raise ValueError("Tappa non presente nel calendario: " + origin + " / " + destination)
        departure = dt.datetime.combine(tomorrow, dt.time.fromisoformat(item["time"]), tzinfo=TZ)
        result = evaluate(regions[origin], regions[destination], departure)
        body += trip_result(f"{origin} → {destination}", origin, destination, item["time"], result)
    if not planned:
        body = "<p>Nessun tragitto previsto nel calendario per domani.</p>"
    sender = os.environ["GMAIL_USER"]
    password = os.environ["GMAIL_APP_PASSWORD"]
    message = EmailMessage()
    message["Subject"] = f"🛵 Meteo Scooter — {tomorrow:%d/%m/%Y}"
    message["From"] = sender
    message["To"] = os.getenv("MAIL_TO", "giacomoubaldi@gmail.com")
    message.set_content("Apri questa email in formato HTML per visualizzare le previsioni.")
    message.add_alternative(
        "<html><body style='font-family:Arial;max-width:720px'>"
        "<h1>🛵 Meteo Scooter Bologna</h1>" + body
        + "<p>Previsioni Open-Meteo e percorso OSRM. Durata stimata: 25 km/h + 3 minuti.</p>"
        "</body></html>", subtype="html"
    )
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(sender, password)
        smtp.send_message(message)
    print("Email inviata.")

if __name__ == "__main__":
    main()
