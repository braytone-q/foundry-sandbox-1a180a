from datetime import datetime, timezone


def fresh_location(**changes):
    # Synthetic test coordinates, never a real submitting device's location.
    return {"latitude": 0.12345, "longitude": 36.12345, "accuracy_m": 12.0,
            "captured_at": datetime.now(timezone.utc).isoformat(), "source": "browser_geolocation"} | changes
