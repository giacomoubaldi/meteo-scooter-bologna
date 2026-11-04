"""Invia ogni sera il meteo scooter per il giorno successivo."""
import datetime as dt
import html
import os
import smtplib
import json
import urllib.request
import urllib.parse
from email.message import EmailMessage
from pathlib import Path
from meteo_core import TZ, REGIONS, evaluate, advice

def trip(title, origin, destination, time, day):
    departure = dt.datetime.combine(day, dt.time.fromisoformat(time), tzinfo=TZ)
    result = evaluate(REGIONS[origin], REGIONS[destination], departure)
    return trip_result(title, origin, destination, time, result)

def weather_label(code):
    if code is None: return "❔ n.d."
    code = round(code)
    if code == 0: return "☀️ Sereno"
    if code == 1: return "🌤️ Prevalentemente sereno"
    if code == 2: return "⛅ Parzialmente nuvoloso"
    if code == 3: return "☁️ Coperto"
    if code in (45, 48): return "🌫️ Nebbia"
    if code in (51, 53, 55, 56, 57): return "🌦️ Pioviggine"
    if code in (61, 63, 65, 66, 67, 80, 81, 82): return "🌧️ Pioggia"
    if code in (71, 73, 75, 77, 85, 86): return "🌨️ Neve"
    if code in (95, 96, 99): return "⛈️ Temporale"
    return "❔ Variabile"

def clothing_advice(temp, wind, rain, prob):
    if temp is None: return "🧥 Temperatura non disponibile: porta una giacca antivento."
    perceived = temp - (0 if wind is None else min(7, max(0, wind - 10) * 0.15))
    if perceived < 5: msg = "🧥 Giacca pesante imbottita, guanti caldi e scaldacollo"
    elif perceived < 11: msg = "🧥 Giacca pesante o giacca da moto con imbottitura termica"
    elif perceived < 17: msg = "🧥 Giacca antivento con strato caldo"
    elif perceived < 23: msg = "🧥 Giacca leggera antivento"
    else: msg = "🛵 Giacca da moto leggera e traspirante"
    if wind is not None and wind >= 25: msg += "; 💨 vento sostenuto: chiudi bene la giacca"
    if (prob is not None and prob >= 35) or (rain is not None and rain > 0): msg += "; 🌧️ porta uno strato impermeabile"
    return msg + "."

def trip_result(title, origin, destination, time, result, fuel=None):
    def fmt(value, unit="", digits=0):
        return "n.d." if value is None else f"{value:.{digits}f}{unit}"
    rows = ""
    for point in result["points"]:
        sample = point["samples"][1]
        cells = (point["name"], sample["time"][11:16], weather_label(sample.get("weather_code")),
                 fmt(sample["temperature"], " °C", 1), fmt(sample["probability"], "%"),
                 fmt(sample["rain_hour"], " mm", 2))
        rows += "<tr>" + "".join("<td style='padding:9px;border-bottom:1px solid #dbe4ef'>" + html.escape(str(cell)) + "</td>" for cell in cells) + "</tr>"
    samples = [point["samples"][1] for point in result["points"]]
    temps = [x["temperature"] for x in samples if x["temperature"] is not None]
    winds = [x["wind"] for x in samples if x["wind"] is not None]
    avg_temp = sum(temps) / len(temps) if temps else None
    max_wind = max(winds) if winds else None
    clothing = clothing_advice(avg_temp, max_wind, result["max_rain_hour"], result["max_probability"])
    headers = ("Punto", "Ora", "Tempo", "Temperatura", "Prob. pioggia", "Pioggia")
    head = "".join("<th style='padding:9px'>" + h + "</th>" for h in headers)
    fuel_note = ""
    if fuel:
        liters = result["distance_km"] * 0.04
        cost = liters * fuel["price_eur_l"]
        fuel_note = f"<p>⛽ Consumo stimato: {liters:.2f} L · 💶 Costo: {cost:.2f} € (4 L/100 km)</p>"
    return (
        f"<h2 style='color:#153b60'>🛵 {html.escape(title)} — {html.escape(time)}</h2>"
        f"<p>{html.escape(origin)} → {html.escape(destination)}: {result['distance_km']} km, circa {result['duration_minutes']} minuti.</p>"
        "<div style='overflow-x:auto'><table style='width:100%;border-collapse:collapse;font-size:14px'>"
        f"<thead><tr style='background:#e7f1fa;color:#153b60'>{head}</tr></thead><tbody>{rows}</tbody></table></div>"
        + fuel_note
        + f"<p><strong>🌦️ Rischio pioggia:</strong> {html.escape(advice(result))}</p>"
        f"<p><strong>👕 Come vestirsi:</strong> {html.escape(clothing)}</p>"
        f"<p style='font-size:13px;color:#53657b'>Controllo partenze ±30 min: probabilità massima {fmt(result['max_probability'], '%')}, "
        f"pioggia massima {fmt(result['max_rain_hour'], ' mm/h', 2)}, vento massimo {fmt(result['max_wind'], ' km/h')}.</p>"
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
    weekdays = ("lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica")
    months = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre")
    friendly_date = f"{weekdays[tomorrow.weekday()]} {tomorrow.day} {months[tomorrow.month - 1]}"
    fuel = None
    try:
        fuel = json.loads(Path("docs/fuel-price.json").read_text(encoding="utf-8"))
        if not isinstance(fuel.get("price_eur_l"), (int, float)) or fuel["price_eur_l"] <= 0:
            fuel = None
    except (OSError, ValueError, TypeError):
        pass
    body = ""
    for item in planned:
        origin, destination = item["from"], item["to"]
        if origin not in regions or destination not in regions:
            raise ValueError("Tappa non presente nel calendario: " + origin + " / " + destination)
        departure = dt.datetime.combine(tomorrow, dt.time.fromisoformat(item["time"]), tzinfo=TZ)
        result = evaluate(regions[origin], regions[destination], departure)
        body += trip_result(f"{origin} → {destination}", origin, destination, item["time"], result, fuel)
    if fuel:
        body = f"<p><strong>⛽ Benzina self Bologna:</strong> {fuel['price_eur_l']:.3f} €/L · Rilevazione {html.escape(str(fuel.get('extraction', 'n.d.')))}.</p>" + body
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
        "<h1>🛵 Meteo Scooter Bologna</h1>" + f"<p>Ciao Giacomo, ecco le previsioni per domani <strong>{friendly_date}</strong>!</p>" + body
        + "<p>Previsioni Open-Meteo e percorso OSRM. Durata stimata: 25 km/h + 3 minuti.</p>"
        "</body></html>", subtype="html"
    )
    if not sender.strip() or not password.strip():
        raise RuntimeError("Controlla i secrets GMAIL_USER e GMAIL_APP_PASSWORD.")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(sender.strip(), password.replace(" ", "").strip())
        smtp.send_message(message)
    print("Email inviata.")

if __name__ == "__main__":
    main()
