import requests
import hashlib
import os
import time
import json
from datetime import datetime, UTC

WEBHOOK_URL = os.getenv("WEBHOOK_URL") or "YOUR_WEBHOOK_URL"

IMAGE_URL = "https://www.nhc.noaa.gov/xgtwo/two_atl_7d0.png"
STORM_DATA_URL = "https://www.nhc.noaa.gov/CurrentStorms.json"

STORM_FILE = "storms.json"
OFFSEASON_FILE = "offseason.json"


# ---------------------------
# Season check
# ---------------------------
def in_season():
    now = datetime.now(UTC)
    return 6 <= now.month <= 11


# ---------------------------
# Weekly off-season system
# ---------------------------
def should_send_offseason():
    if not os.path.exists(OFFSEASON_FILE):
        return True

    with open(OFFSEASON_FILE, "r") as f:
        data = json.load(f)

    last_sent = datetime.fromisoformat(data["last_sent"])
    now = datetime.now(UTC)

    return (now - last_sent).total_seconds() >= 604800  # 7 days


def update_offseason_time():
    with open(OFFSEASON_FILE, "w") as f:
        json.dump({
            "last_sent": datetime.now(UTC).isoformat()
        }, f)


# ---------------------------
# Off-season embed
# ---------------------------
def send_offseason():
    now = datetime.now(UTC)

    year = now.year
    june_first = datetime(year, 6, 1, tzinfo=UTC)

    if now > june_first:
        june_first = datetime(year + 1, 6, 1, tzinfo=UTC)

    days_left = (june_first - now).days

    # Ocean conditions (simple simulation)
    if days_left > 120:
        ocean_text = "🌡️ Ocean temperatures are currently stable for this time of year."
    elif days_left > 60:
        ocean_text = "🌡️ Ocean temperatures are gradually warming across the Atlantic."
    else:
        ocean_text = "🔥 Ocean temperatures are warming — conditions may soon become favorable for development."

    # Smart outlook
    if days_left > 150:
        outlook = "Quiet pattern typical of winter months."
    elif days_left > 90:
        outlook = "Gradual transition toward pre-season conditions."
    elif days_left > 30:
        outlook = "Pre-season signals increasing. Early development becomes possible."
    else:
        outlook = "Hurricane season is approaching rapidly. Monitoring will increase."

    embed = {
        "title": "🟡 Atlantic Hurricane Off-Season Update",
        "description": (
            f"📴 **Off-season status**\n\n"
            f"⏳ **{days_left} days until June 1**\n\n"
            f"{ocean_text}\n\n"
            f"🧠 **Outlook:** {outlook}"
        ),
        "color": 0xf1c40f,
        "image": {
            "url": IMAGE_URL
        },
        "footer": {
            "text": "Ryan's Hurricane Tracking Bot"
        },
        "timestamp": now.isoformat()
    }

    data = {
        "username": "Hurricane Tracker",
        "embeds": [embed]
    }

    requests.post(WEBHOOK_URL, json=data)


# ---------------------------
# Load/save storm memory
# ---------------------------
def load_old_storms():
    if not os.path.exists(STORM_FILE):
        return []
    with open(STORM_FILE, "r") as f:
        return json.load(f)


def save_storms(storms):
    with open(STORM_FILE, "w") as f:
        json.dump(storms, f)


# ---------------------------
# Get storm data
# ---------------------------
def get_storms():
    response = requests.get(STORM_DATA_URL)
    data = response.json()

    storms = []

    for storm in data.get("activeStorms", []):
        if storm.get("basin") != "AL":
            continue

        storms.append({
            "id": storm.get("id"),
            "name": storm.get("name"),
            "type": storm.get("type"),
            "wind": storm.get("windSpeed", "N/A"),
            "pressure": storm.get("pressure", "N/A")
        })

    return storms


# ---------------------------
# Detect new storms
# ---------------------------
def detect_new_storms(new, old):
    old_ids = {s["id"] for s in old}
    return [s for s in new if s["id"] not in old_ids]


# ---------------------------
# Format storm message
# ---------------------------
def format_storm(storm):
    name = storm["name"]
    stype = storm["type"]
    wind = storm["wind"]
    pressure = storm["pressure"]

    if "Hurricane" in stype:
        emoji = "🌀"
    elif "Tropical Storm" in stype:
        emoji = "🌧"
    elif "Depression" in stype:
        emoji = "🌊"
    else:
        emoji = "🌪"

    return (
        f"{emoji} **{stype} {name}**\n"
        f"💨 Wind: {wind} mph\n"
        f"📉 Pressure: {pressure} mb"
    )


# ---------------------------
# Send storm webhook
# ---------------------------
def send_webhook(new_storms):
    description = "\n\n".join(format_storm(s) for s in new_storms)

    embed = {
        "title": "🚨 New Atlantic Storm Detected!",
        "description": description,
        "color": 0xe74c3c,
        "image": {
            "url": IMAGE_URL
        },
        "footer": {
            "text": "Ryan's Hurricane Tracking Bot"
        },
        "timestamp": datetime.now(UTC).isoformat()
    }

    data = {
        "username": "Hurricane Alerts",
        "embeds": [embed]
    }

    requests.post(WEBHOOK_URL, json=data)


# ---------------------------
# Main logic
# ---------------------------
def check():
    if not in_season():
        print("🟡 Off-season")

        if should_send_offseason():
            send_offseason()
            update_offseason_time()
            print("📨 Sent weekly off-season update")

        return
    else:
        # Reset offseason tracker when season starts
        if os.path.exists(OFFSEASON_FILE):
            os.remove(OFFSEASON_FILE)

    new_storms = get_storms()
    old_storms = load_old_storms()

    new_detected = detect_new_storms(new_storms, old_storms)

    if new_detected:
        print("🌪 NEW STORM!")
        send_webhook(new_detected)
        save_storms(new_storms)
    else:
        print("No new storms.")


# ---------------------------
# Loop (auto-restart safe)
# ---------------------------
if __name__ == "__main__":
    while True:
        try:
            check()
            time.sleep(600)
        except Exception as e:
            print("Error:", e)
            time.sleep(60)
