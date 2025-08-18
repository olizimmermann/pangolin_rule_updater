import os
import time
import json
import requests
from dotenv import load_dotenv

load_dotenv()                              # read .env at runtime

API_KEY        = os.environ["API_KEY"]
RESOURCE_ID    = os.environ["RESOURCE_ID"]
RULE_ID        = os.environ["RULE_ID"]
PANGOLIN_HOST  = os.environ.get("PANGOLIN_HOST", "https://api.pangolin.example")
IP_SERVICE_URL = os.environ.get("IP_SERVICE_URL", "https://api.ipify.org")
LOOP_SECONDS   = int(os.environ.get("LOOP_SECONDS", "60"))
RULE_PRIORITY  = int(os.environ.get("RULE_PRIORITY", "100"))
RULE_ACTION    = os.environ.get("RULE_ACTION", "ACCEPT").upper()
RULE_MATCH     = os.environ.get("RULE_MATCH", "IP").upper()
if RULE_MATCH not in ["IP", "CIDR", "PATH"]:
    raise ValueError(f"Invalid RULE_MATCH: {RULE_MATCH}")
RULE_ENABLED  = os.environ.get("RULE_ENABLED", "True").lower() == "true" 

HEADERS = {
    "accept": "*/*",
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

def get_external_ip() -> str:
    """Return the current public IPv4 address as a string."""
    return requests.get(IP_SERVICE_URL, timeout=5).text.strip()

def get_rule_value() -> str:
    """Fetch the current `value` field of the Pangolin rule."""
    url = f"{PANGOLIN_HOST}/v1/resource/{RESOURCE_ID}/rules?limit=1000&offset=0"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    rules = resp.json()["data"]["rules"]
    for rule in rules:
        if rule["ruleId"] == int(RULE_ID):
            return rule["value"]
    raise ValueError(f"Rule ID {RULE_ID} not found")

def update_rule(new_ip: str):
    """POST an updated rule when the IP has changed."""
    url = f"{PANGOLIN_HOST}/v1/resource/{RESOURCE_ID}/rule/{RULE_ID}"
    payload = {
        "action":   RULE_ACTION,
        "match":    RULE_MATCH,
        "value":    new_ip,
        "priority": RULE_PRIORITY,
        "enabled":  RULE_ENABLED
    }
    resp = requests.post(url, headers=HEADERS, data=json.dumps(payload), timeout=10)
    resp.raise_for_status()
    print(f"[pangolin] Updated rule {RULE_ID} to {new_ip}")

def main():
    while True:
        try:
            current_ip = get_external_ip()
            stored_ip  = get_rule_value()
            if current_ip != stored_ip:
                print(f"[info] Detected IP change: {stored_ip} → {current_ip}")
                update_rule(current_ip)
            else:
                print(f"[info] IP unchanged ({current_ip})")
        except Exception as e:
            print(f"[error] {e}")
        time.sleep(LOOP_SECONDS)

if __name__ == "__main__":
    main()

