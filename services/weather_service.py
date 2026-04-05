import json
import urllib.request
import urllib.parse
from datetime import datetime


def get_weather_data(latitude=30.4278, longitude=-9.5981, timezone="auto"):
    """Fetch simple weather data from Open-Meteo without requiring an API key."""
    query = urllib.parse.urlencode({
        "latitude": latitude,
        "longitude": longitude,
        "current_weather": "true",
        "hourly": "temperature_2m,relativehumidity_2m",
        "past_days": 1,
        "timezone": timezone,
    })
    url = f"https://api.open-meteo.com/v1/forecast?{query}"

    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.load(response)
    except Exception:
        return None

    current = data.get("current_weather", {})
    hourly = data.get("hourly", {})

    humidity = None
    current_time = current.get("time")
    if current_time and "time" in hourly and "relativehumidity_2m" in hourly:
        times = hourly["time"]
        humidity_values = hourly["relativehumidity_2m"]
        if times and humidity_values:
            try:
                index = times.index(current_time)
                humidity = humidity_values[index]
            except ValueError:
                humidity = humidity_values[0] if humidity_values else None

    return {
        "current": {
            "temperature": current.get("temperature"),
            "humidity": humidity,
            "wind_speed": current.get("windspeed"),
            "wind_deg": current.get("winddirection"),
        },
        "hourly": hourly
    }
