import os
import sys
import re
import requests

COLORS = {
    "ROUTINE": 0x2ECC71,    # green
    "ELEVATED": 0xF1C40F,   # yellow
    "CRITICAL": 0xE74C3C,   # red
}

PINGS = {
    "ROUTINE": "",
    "ELEVATED": "@here",
    "CRITICAL": "@everyone",
}

def get_webhook_url():
    config_path = os.path.join(os.path.dirname(__file__), "webhook_config.txt")
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            url = f.read().strip()
            if url and not url.startswith("PASTE_YOUR_WEBHOOK_URL_HERE"):
                return url
    return os.environ.get("DISCORD_WEBHOOK_URL")

def parse_headline_block(content):
    """Extract headline block fields from briefing markdown."""
    headline = {
        "tier": "ROUTINE",
        "timestamp": "",
        "session": "",
        "sentiment": "",
        "key": "",
        "trigger": ""
    }

    # Escalation tier
    for tier in ["CRITICAL", "ELEVATED", "ROUTINE"]:
        if tier in content:
            headline["tier"] = tier
            break

    # Timestamp and session from section header
    header_match = re.search(
        r'##\s+([\d]{4}-[\d]{2}-[\d]{2}\s[\d]{2}:[\d]{2}\sUTC)\s*[—-]\s*([^\n—-]+)',
        content
    )
    if header_match:
        headline["timestamp"] = header_match.group(1).strip()
        headline["session"] = header_match.group(2).strip()

    # Sentiment line
    sentiment_match = re.search(r'Sentiment:\s*([^\n]+)', content)
    if sentiment_match:
        headline["sentiment"] = sentiment_match.group(1).strip()

    # Key development
    key_match = re.search(r'Key:\s*([^\n]+)', content)
    if key_match:
        headline["key"] = key_match.group(1).strip()

    # Trigger line (ELEVATED/CRITICAL only)
    trigger_match = re.search(r'Trigger:\s*([^\n]+)', content)
    if trigger_match:
        headline["trigger"] = trigger_match.group(1).strip()

    return headline

def push_to_discord(file_path, tier_override=None):
    webhook_url = get_webhook_url()
    if not webhook_url:
        print("Error: Discord Webhook URL is not set.")
        sys.exit(1)

    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' does not exist.")
        sys.exit(1)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    filename = os.path.basename(file_path)
    headline = parse_headline_block(content)

    if tier_override:
        headline["tier"] = tier_override.upper()

    tier = headline["tier"]
    color = COLORS.get(tier, COLORS["ROUTINE"])
    ping = PINGS.get(tier, "")

    # Build embed
    embed = {
        "title": f"[{tier}] {headline['timestamp']} — {headline['session']}",
        "color": color,
        "fields": []
    }

    if headline["sentiment"]:
        embed["fields"].append({
            "name": "Sentiment / Snapshot",
            "value": headline["sentiment"],
            "inline": False
        })

    if headline["key"]:
        embed["fields"].append({
            "name": "Key Development",
            "value": headline["key"],
            "inline": False
        })

    if headline["trigger"] and tier in ["ELEVATED", "CRITICAL"]:
        embed["fields"].append({
            "name": "⚠️ Trigger",
            "value": headline["trigger"],
            "inline": False
        })

    embed["footer"] = {"text": f"Full report attached: {filename}"}

    payload = {"embeds": [embed]}
    if ping:
        payload["content"] = ping

    # Send embed first
    try:
        embed_response = requests.post(
            webhook_url,
            json=payload
        )
        if embed_response.status_code not in [200, 204]:
            print(f"Embed failed. Status: {embed_response.status_code}")
            print(embed_response.text)
    except Exception as e:
        print(f"Error sending embed: {e}")

    # Attach full file
    try:
        with open(file_path, 'rb') as f:
            file_payload = {"content": ""}
            files = {"file": (filename, f, "text/markdown")}
            file_response = requests.post(webhook_url, data=file_payload, files=files)
            if file_response.status_code in [200, 204]:
                print(f"Successfully pushed {filename} to Discord.")
            else:
                print(f"File attach failed. Status: {file_response.status_code}")
                print(file_response.text)
    except Exception as e:
        print(f"Error attaching file: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python push_to_discord.py <file_path> [TIER]")
        sys.exit(1)

    file_path = sys.argv[1]
    tier_override = sys.argv[2] if len(sys.argv) > 2 else None
    push_to_discord(file_path, tier_override)
