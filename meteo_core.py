"""Previsioni meteo lungo un tragitto, con interpolazione spazio-temporale."""
import datetime as dt
import json
import math
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Rome")
REGIONS = {
    "casa": "Via Alceste Giovannini, Bologna, Italia",
    "fisica": "Via Irnerio 46, Bologna, Italia",
    "ingegneria": "Viale del Risorgimento 2, Bologna, Italia",
}

def api(url):
    request = urllib.request.Request(url, headers={"User-Agent": "MeteoScooterBologna/1.0 (personal weather app)"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)

def geocode(address):
    params = urllib.parse.urlencode({"q": address, "format": "json", "limit": 1})
    matches = api("https://nominatim.openstreetmap.org/search?" + params)
    if not matches:
        raise ValueError("Indirizzo non trovato: " + address)
    return float(matches[0]["lat"]), float(matches[0]["lon"])

def distance(a, b):
    rad = math.pi / 180
    lat = (b[0] - a[0]) * rad
    lon = (b[1] - a[1]) * rad
    x = math.sin(lat / 2) ** 2 + math.cos(a[0] * rad) * math.cos(b[0] * rad) * math.sin(lon / 2) ** 2
    return 12742000 * math.asin(math.sqrt(x))

def midpoint(coords):
    lengths = [distance(a, b) for a, b in zip(coords, coords[1:])]
    half = sum(lengths) / 2
    elapsed = 0
    for i, length in enumerate(lengths):
        if elapsed + length >= half:
            fraction = (half - elapsed) / length if length else 0
            return tuple(coords[i][j] + fraction * (coords[i + 1][j] - coords[i][j]) for j in (0, 1))
        elapsed += length
    return coords[-1]

def interpolate(times, values, when):
    timestamps = [dt.datetime.fromisoformat(value) for value in times]
    when = when.replace(tzinfo=None)
    if not timestamps or when < timestamps[0] or when > timestamps[-1]:
        return None
    for i in range(len(timestamps) - 1):
        if timestamps[i] <= when <= timestamps[i + 1]:
            a, b = values[i:i + 2]
            if a is None or b is None:
                return None
            weight = (when - timestamps[i]).total_seconds() / (timestamps[i + 1] - timestamps[i]).total_seconds()
            return a + (b - a) * weight
    return values[-1]

def evaluate(origin, destination, departure):
    start, end = geocode(origin), geocode(destination)
    routing_url = (
        f"https://router.project-osrm.org/route/v1/driving/{start[1]},{start[0]};"
        f"{end[1]},{end[0]}?overview=full&geometries=geojson"
    )
    route = api(routing_url)["routes"][0]
    coords = [(lonlat[1], lonlat[0]) for lonlat in route["geometry"]["coordinates"]]
    duration = max(3, route["distance"] / 1000 / 25 * 60 + 3)
    points = [start, midpoint(coords), end]
    all_times = [
        departure + dt.timedelta(minutes=duration * i / 2 + offset)
        for i in range(3) for offset in (-30, 0, 30)
    ]
    first, last = min(all_times).date(), max(all_times).date()
    results = []
    for i, point in enumerate(points):
        query = urllib.parse.urlencode({
            "latitude": point[0], "longitude": point[1],
            "hourly": "precipitation_probability,precipitation,temperature_2m,wind_speed_10m",
            "timezone": "Europe/Rome",
            "start_date": first.isoformat(), "end_date": last.isoformat(),
        })
        hourly = api("https://api.open-meteo.com/v1/forecast?" + query)["hourly"]
        variants = []
        for offset in (-30, 0, 30):
            passage = departure + dt.timedelta(minutes=duration * i / 2 + offset)
            variants.append({
                "time": passage.isoformat(),
                "probability": interpolate(hourly["time"], hourly["precipitation_probability"], passage),
                "rain_hour": interpolate(hourly["time"], hourly["precipitation"], passage),
                "temperature": interpolate(hourly["time"], hourly["temperature_2m"], passage),
                "wind": interpolate(hourly["time"], hourly["wind_speed_10m"], passage),
            })
        results.append({"name": ("Partenza", "Metà percorso", "Arrivo")[i], "samples": variants})
    def maximum(key):
        values = [sample[key] for point in results for sample in point["samples"] if sample[key] is not None]
        return max(values) if values else None
    return {
        "distance_km": round(route["distance"] / 1000, 2),
        "duration_minutes": round(duration),
        "points": results,
        "max_probability": maximum("probability"),
        "max_rain_hour": maximum("rain_hour"),
        "max_wind": maximum("wind"),
    }

def advice(result):
    probability, rain = result["max_probability"], result["max_rain_hour"]
    if (probability is not None and probability >= 70) or (rain is not None and rain >= 1):
        return "🔴 Rischio pioggia elevato: valuta un mezzo alternativo."
    if (probability is not None and probability >= 35) or (rain is not None and rain > 0):
        return "🟡 Possibile pioggia: porta l'antipioggia."
    return "🟢 Condizioni relativamente favorevoli per lo scooter."
