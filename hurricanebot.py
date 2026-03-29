import requests
import os
import time
import json
import re
from datetime import datetime, UTC

WEBHOOK_URL = os.getenv("WEBHOOK_URL") or "YOUR_WEBHOOK_URL"

IMAGE_URL = "https://www.nhc.noaa.gov/xgtwo/two_atl_7d0.png"
STORM_DATA_URL = "https://www.nhc.noaa.gov/CurrentStorms.json"
OUTLOOK_URL = "https://www.nhc.noaa.gov/text/MIATWOAT.shtml"

STORM_FILE = "storms.json"
OFFSEASON_FILE = "offseason.json"
PERCENT_FILE = "percent.json"


# ---------------------------
# Season check
# ---------------------------
def in_season():
    now = datetime.now(UTC)
    return 6 <= now.month <= 11


# ---------------------------
# CLEAN NOAA outlook
# ---------------------------
def get_real_outlook():
    try:
        response = requests.get(OUTLOOK_URL, timeout=10)
        text = response.text

        start = text.find("For the North Atlantic")
        end = text.find("$$", start)

        if start == -1 or end == -1:
            return "No clean outlook available.", []

        outlook = text[start:end]

        clean = re.sub(r"<.*?>", "", outlook)

        lines = []
        for line in clean.splitlines():
            line = line.strip()

            if not line:
                continue

            if any(x in line.lower() for x in [
                "http", "rss", "map", "product", "format", "gis"
            ]):
                continue

            lines.append(line)

        percentages = sorted(
            set(re.findall(r"\d{1,3}%", clean)),
            key=lambda x: int(x[:-1])
        )

        formatted = []
        for line in lines:
            line = re.sub(r"(\d{1,3}%)", r"**\1**", line)
            formatted.append(line)

        return "\n".join(formatted[:10]), percentages

    except Exception as e:
        return f"Failed to fetch outlook: {e}", []


# ---------------------------
# Percent tracking
# ---------------------------
def load_old_percents():
    if not os.path.exists(PERCENT_FILE):
        return []
    with open(PERCENT_FILE, "r") as f:
        return json.load(f)


def save_percents(p):
    with open(PERCENT_FILE, "w") as f:
        json.dump(p, f)


def percent_increased(new, old):
    if not old:
        return True
    return max([int(n[:-1]) for n in new], default=0) > max([int(o[:-1]) for o in old], default=0)


# ---------------------------
# Region detection
# ---------------------------
def detect_region(text):
    t = text.lower()

    if "gulf" in t:
        return "🟠 Gulf of America 🦅🇺🇸"
    elif "caribbean" in t:
        return "🟡 Caribbean Sea"
    elif "atlantic" in t:
        return "🔵 Atlantic Ocean"
    return "🌍 General Atlantic Basin"


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

    return (now - last_sent).total_seconds() >= 604800


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

    outlook_text, percentages = get_real_outlook()
    old_percent = load_old_percents()

    region = detect_region(outlook_text)
    percent_text = " / ".join(percentages) if percentages else "None"

    highest = max([int(p[:-1]) for p in percentages], default=0)

    if highest >= 70:
        color = 0xe74c3c
    elif highest >= 40:
        color = 0xf39c12
    elif highest > 0:
        color = 0xf1c40f
    else:
        color = 0x95a5a6

    if percent_increased(percentages, old_percent):
        title = "🚨 Development Chances Increased!"
    else:
        title = "🟡 Atlantic Hurricane Off-Season Update"

    embed = {
        "title": title,
        "description": (
            f"📴 **Off-season status**\n\n"
            f"⏳ **{days_left} days until June 1**\n\n"
            f"📍 **Region:** {region}\n"
            f"📊 **Formation Chances:** {percent_text}\n\n"
            f"📡 **Latest NHC Outlook:**\n{outlook_text[:1200]}"
        ),
        "color": color,
        "image": {
            "url": IMAGE_URL
        },
        "footer": {
            "text": "Live data from NOAA / NHC"
        },
        "timestamp": now.isoformat()
    }

    requests.post(WEBHOOK_URL, json={
        "username": "Hurricane Tracker",
        "embeds": [embed]
    })

    save_percents(percentages)


# ---------------------------
# Storm memory
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
# Get storms
# ---------------------------
def get_storms():
    try:
        response = requests.get(STORM_DATA_URL, timeout=10)
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

    except Exception as e:
        print("Storm fetch error:", e)
        return []


# ---------------------------
# Detect new storms
# ---------------------------
def detect_new_storms(new, old):
    old_ids = {s["id"] for s in old}
    return [s for s in new if s["id"] not in old_ids]


# ---------------------------
# Format storm
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
# Send storm alert
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

    requests.post(WEBHOOK_URL, json={
        "username": "Hurricane Alerts",
        "embeds": [embed]
    })


# ---------------------------
# Main logic
# ---------------------------
def check():
    if not in_season():
        print("🟡 Off-season")

        if should_send_offseason():
            send_offseason()
            update_offseason_time()
            print("📨 Sent weekly update")

        return
    else:
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
# Loop
# ---------------------------
if __name__ == "__main__":
    while True:
        try:
            check()
            time.sleep(600)
        except Exception as e:
            print("Error:", e)
            time.sleep(60)
