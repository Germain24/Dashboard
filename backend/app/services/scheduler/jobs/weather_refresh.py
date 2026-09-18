def run(session):
    try:
        import httpx
        params = {
            "latitude": 45.5017, "longitude": -73.5673,
            "current": "temperature_2m,weather_code",
            "timezone": "America/Montreal"
        }
        resp = httpx.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=10.0)
        data = resp.json()
        temp = data["current"]["temperature_2m"]
        return f"Météo: {temp}°C"
    except Exception as e:
        return f"Weather refresh failed: {e}"
