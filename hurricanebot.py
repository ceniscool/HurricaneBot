import requests
import hashlib
import os
import time
from datetime import datetime

WEBHOOK_URL = "https://discordapp.com/api/webhooks/1402124321714868294/vlwCMFTMFQm2acBu5bMB3xkvzKmL5kbs223Sak4IWlQfvqeTrV2EhJG0Q1NrRQjkPr9f"

IMAGE_URL = "https://www.nhc.noaa.gov/xgtwo/two_atl_7d0.png"
STORM_DATA_URL = "https://www.nhc.noaa.gov/CurrentStorms.json"

HASH_FILE = "last_hash.txt"


# ---------------------------
# Season check
# ---------------------------
def in_season():
    now = datetime.utcnow()
    return 6 <= now.month <= 11


# ---------------------------
# Image hash
# ---------------------------
def get_image_hash():
    response = requests.get(IMAGE_URL)
    return hashlib.md5(response.content).hexdigest()


def load_last_hash():
    if not os.path.exists(HASH_FILE):
        return None
    with open(HASH_FILE, "r") as f:
        return f.read().strip()


def save_hash(h):
    with open(HASH_FILE, "w") as f:
        f.write(h)


# ---------------------------
# Storm detection
# ---------------------------
def get_storm_info():
    try:
        response = requests.get(STORM_DATA_URL)
        data = response.json()

        storms = []
        invests = []

        for storm in data.get("activeStorms", []):
            if storm.get("basin") != "AL":
                continue  # Atlantic only

            name = storm.get("name", "Unnamed")
            stype = storm.get("type", "")
            number = storm.get("id", "")

            # Detect INVESTS (like AL90)
            if "INVEST" in stype.upper() or "INV" in name.upper():
                invests.append(f"🟡 {number}")
                continue

            # Storm categories
            if "Hurricane" in stype:
                storms.append(f"🌀 Hurricane {name}")
            elif "Tropical Storm" in stype:
                storms.append(f"🌧 Tropical Storm {name}")
            elif "Depression" in stype:
                storms.append(f"🌊 Tropical Depression {name}")
            else:
                storms.append(f"🌪 {name}")

        text = ""

        if storms:
            text += "**Active Storms:**\n" + "\n".join(storms)

        if invests:
            if text:
                text += "\n\n"
            text += "**Invests:**\n" + "\n".join(invests)

        if not text:
            text = "✅ No active Atlantic tropical systems."

        return text

    except Exception:
        return "⚠️ Error fetching storm data."


# ---------------------------
# Webhook
# ---------------------------
def send_webhook(description):
    embed = {
        "title": "🚨 Atlantic Hurricane Update",
        "description": description,
        "color": 0xe67e22,
        "image": {
            "url": IMAGE_URL
        },
        "footer": {
            "text": "Ryan's Hurricane Tracking Bot"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

    data = {
        "username": "Hurricane Tracker",
        "embeds": [embed]
    }

    requests.post(WEBHOOK_URL, json=data)


# ---------------------------
# Main logic
# ---------------------------
def check():
    if not in_season():
        print("🟡 Off-season (June 1 - Nov 30)")
        return

    new_hash = get_image_hash()
    old_hash = load_last_hash()

    if new_hash != old_hash:
        print("🌪 Update detected!")

        storm_info = get_storm_info()
        send_webhook(storm_info)

        save_hash(new_hash)
    else:
        print("No change.")


# ---------------------------
# Loop
# ---------------------------
if __name__ == "__main__":
    while True:
        check()
        time.sleep(600)