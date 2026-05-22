import os
import sys
import re
import time
import logging
import requests

logging.basicConfig(
    filename='push_to_discord.log',
    level=logging.INFO,
    format='%(asctime)s — %(levelname)s — %(message)s'
)

ALLOWED_PATTERNS = [
    r'^macro update \(\d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC\)\.md$',
    r'^macro weekly synthesis \(\d{4}-\d{2}-\d{2} UTC\)\.md$',
]

VALID_TIERS = {"ROUTINE", "ELEVATED", "CRITICAL"}

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

MAX_FILE_SIZE_MB = 7

def is_allowed_file(file_path):
    filename = os.path.basename(file_path)
    return any(re.match(pattern, filename) for pattern in ALLOWED_PATTERNS)

def get_webhook_url():
    url = os.environ.get("DISCORD_WEBHOOK_URL")
    if url:
        return url
    config_path = os.path.join(os.path.dirname(__file__), "webhook_config.txt")
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            url = f.read().strip()
            if url and not url.startswith("PASTE_YOUR_WEBHOOK_URL_HERE"):
                return url
    return None

def post_with_retry(url, retries=3, delay=10, **kwargs):
    for attempt in range(retries):
        try:
            response = requests.post(url, verify=True, **kwargs)
            if response.status_code in [200, 204]:
                return response
            logging.error(f"Attempt {attempt + 1} failed: {response.status_code}")
        except Exception as e:
            logging.error(f"Attempt {attempt + 1} error: {e}")
        if attempt < retries - 1:
            time.sleep(delay)
    return None

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
    if not is_allowed_file(file_path):
        logging.error(f"File path '{file_path}' does not match allowed patterns. Exiting.")
        sys.exit(1)

    webhook_url = get_webhook_url()
    if not webhook_url:
        logging.error("Discord Webhook URL is not set.")
        sys.exit(1)

    if not os.path.exists(file_path):
        logging.error(f"File '{file_path}' does not exist.")
        sys.exit(1)

    if tier_override:
        tier_override = tier_override.upper()
        if tier_override not in VALID_TIERS:
            logging.error(f"Invalid tier '{tier_override}'.")
            sys.exit(1)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    filename = os.path.basename(file_path)
    headline = parse_headline_block(content)

    if tier_override:
        headline["tier"] = tier_override

    tier = headline["tier"]
    color = COLORS.get(tier, COLORS["ROUTINE"])
    ping = PINGS.get(tier, "")

    # File size check
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    file_too_large = file_size_mb > MAX_FILE_SIZE_MB

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

    if file_too_large:
        embed["footer"] = {"text": f"Full report not attached (exceeds {MAX_FILE_SIZE_MB}MB): {filename}"}
    else:
        embed["footer"] = {"text": f"Full report attached: {filename}"}

    payload = {"embeds": [embed]}
    if ping:
        payload["content"] = ping

    # Send embed first
    logging.info(f"Sending embed for {filename}...")
    embed_response = post_with_retry(webhook_url, json=payload)
    if not embed_response:
        logging.error("Failed to send embed after retries.")

    # Attach full file if not too large
    if not file_too_large:
        logging.info(f"Attaching file {filename}...")
        try:
            with open(file_path, 'rb') as f:
                file_payload = {"content": ""}
                files = {"file": (filename, f, "text/markdown")}
                file_response = post_with_retry(webhook_url, data=file_payload, files=files)
                if file_response:
                    logging.info(f"Successfully pushed {filename} to Discord.")
                else:
                    logging.error("File attach failed after retries.")
        except Exception as e:
            logging.error(f"Error attaching file: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        logging.error("Usage: python push_to_discord.py <file_path> [TIER]")
        sys.exit(1)

    file_path_arg = sys.argv[1]
    tier_arg = sys.argv[2] if len(sys.argv) > 2 else None
    push_to_discord(file_path_arg, tier_arg)
