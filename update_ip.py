import ipaddress
import os
import json
import random
import socket
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import requests
from dotenv import load_dotenv

load_dotenv()

# ── Required ───────────────────────────────────────────────────────────────────
API_KEY     = os.environ["API_KEY"]
RESOURCE_ID = os.environ["RESOURCE_ID"]
RULE_ID     = os.environ["RULE_ID"]

# ── Optional ───────────────────────────────────────────────────────────────────
PANGOLIN_HOST = os.environ.get("PANGOLIN_HOST", "https://api.pangolin.example")
TARGET_DOMAIN = os.environ.get("TARGET_DOMAIN", "").strip() or None
LOOP_SECONDS  = int(os.environ.get("LOOP_SECONDS", "60"))
LOOP_JITTER   = int(os.environ.get("LOOP_JITTER", "10"))
RULE_PRIORITY = int(os.environ.get("RULE_PRIORITY", "100"))
RULE_ACTION   = os.environ.get("RULE_ACTION", "ACCEPT").upper()
RULE_MATCH    = os.environ.get("RULE_MATCH", "IP").upper()
RULE_ENABLED  = os.environ.get("RULE_ENABLED", "True").lower() == "true"

# Comma-separated list of IP services — round-robin for rotation
_DEFAULT_IP_SERVICES = "https://wtfismyip.com/text,https://api.ipify.org,https://icanhazip.com"
IP_SERVICE_URLS = [
    u.strip()
    for u in os.environ.get("IP_SERVICE_URL", _DEFAULT_IP_SERVICES).split(",")
    if u.strip()
]

EXPOSE_TRIGGER_WEBSITE = os.environ.get("EXPOSE_TRIGGER_WEBSITE", "False").lower() == "true"
if EXPOSE_TRIGGER_WEBSITE:
    TRIGGER_WEBSITE_DOMAIN = os.environ.get("TRIGGER_WEBSITE_DOMAIN", "trigger.my.dyn.dns.com")
    TRIGGER_WEBSITE_PATH   = os.environ.get("TRIGGER_WEBSITE_PATH", "/update")
    TRIGGER_WEBSITE_PORT   = int(os.environ.get("TRIGGER_WEBSITE_PORT", "8080"))
    TRIGGER_SECRET         = os.environ.get("TRIGGER_SECRET", "")

if RULE_MATCH not in ["IP", "CIDR", "PATH"]:
    raise ValueError(f"Invalid RULE_MATCH: {RULE_MATCH}")

# ── Shared HTTP session ────────────────────────────────────────────────────────
SESSION = requests.Session()
SESSION.headers.update({
    "accept": "*/*",
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (compatible; HTTPClient/1.0)",
})

# ── State ──────────────────────────────────────────────────────────────────────
_ip_service_index = 0
_cached_ip: str | None = None       # last IP successfully pushed to Pangolin
_rule_fetch_failed_at: float | None = None  # timestamp of last failed get_rule_value()
_RULE_FETCH_COOLDOWN = 60           # seconds to wait before retrying a failed fetch

# ── IP helpers ─────────────────────────────────────────────────────────────────
def get_target_ip() -> str:
    try:
        return socket.gethostbyname(TARGET_DOMAIN)
    except socket.gaierror as e:
        raise Exception(f"Failed to resolve {TARGET_DOMAIN}: {e}")


def get_external_ip() -> str:
    global _ip_service_index
    url = IP_SERVICE_URLS[_ip_service_index % len(IP_SERVICE_URLS)]
    _ip_service_index += 1
    raw = SESSION.get(url, timeout=5).text.strip()
    try:
        ipaddress.ip_address(raw)
    except ValueError:
        raise ValueError(f"IP service returned invalid address: {raw!r}")
    return raw


def get_current_ip() -> str:
    return get_target_ip() if TARGET_DOMAIN else get_external_ip()


# ── Pangolin helpers ───────────────────────────────────────────────────────────
def get_rule_value() -> str | None:
    """Fetch the current `value` field of the Pangolin rule (bootstrap only)."""
    url = f"{PANGOLIN_HOST}/v1/resource/{RESOURCE_ID}/rules?limit=1000&offset=0"
    resp = SESSION.get(url, timeout=10)
    if resp.status_code != 200:
        print(f"[error] Failed to fetch rules: {resp.status_code} {resp.text}")
        return None
    rules = resp.json()["data"]["rules"]
    for rule in rules:
        if rule["ruleId"] == int(RULE_ID):
            return rule["value"]
    print(f"[info] Rule ID {RULE_ID} not found")
    return None


def update_rule(new_ip: str) -> None:
    url = f"{PANGOLIN_HOST}/v1/resource/{RESOURCE_ID}/rule/{RULE_ID}"
    payload = {
        "action":   RULE_ACTION,
        "match":    RULE_MATCH,
        "value":    new_ip,
        "priority": RULE_PRIORITY,
        "enabled":  RULE_ENABLED,
    }
    resp = SESSION.post(url, data=json.dumps(payload), timeout=10)
    if resp.status_code != 200:
        raise Exception(f"Failed to update rule {RULE_ID}: {resp.status_code} {resp.text}")
    print(f"[pangolin] Rule {RULE_ID} updated → {new_ip}")


# ── Trigger website ────────────────────────────────────────────────────────────
_HTML_OK = """\
<html><head><title>IP Update Trigger</title></head><body>
<h1>IP Update Trigger</h1>
<p>Update triggered successfully.</p>
<p>New IP: {ip}</p>
</body></html>"""

_HTML_NOK = """\
<html><head><title>IP Update Trigger</title></head><body>
<h1>IP Update Trigger</h1>
<p>Update could not be triggered.</p>
</body></html>"""

_HTML_NO_CHANGE = """\
<html><head><title>IP Update Trigger</title></head><body>
<h1>IP Update Trigger</h1>
<p>No change — IP is already up-to-date.</p>
</body></html>"""


_HTML_UNAUTHORIZED = """\
<html><head><title>IP Update Trigger</title></head><body>
<h1>IP Update Trigger</h1>
<p>Unauthorized.</p>
</body></html>"""


class TriggerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global _cached_ip, _rule_fetch_failed_at
        parsed = urlparse(self.path)
        host = self.headers.get("Host", "").split(":")[0]
        path = parsed.path

        if path != TRIGGER_WEBSITE_PATH or host != TRIGGER_WEBSITE_DOMAIN:
            self._send(404, "<h1>Not Found</h1>")
            return

        if TRIGGER_SECRET:
            provided = parse_qs(parsed.query).get("token", [""])[0]
            if provided != TRIGGER_SECRET:
                print(f"[warn] Unauthorized trigger attempt — bad or missing token")
                self._send(401, _HTML_UNAUTHORIZED)
                return

        incoming_ip = (
            self.headers.get("Cf-Connecting-Ip")
            or (self.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
            or self.client_address[0]
        )
        print(f"[trigger] Request from {incoming_ip}")

        if _cached_ip is None:
            now = time.time()
            if _rule_fetch_failed_at is None or now - _rule_fetch_failed_at >= _RULE_FETCH_COOLDOWN:
                try:
                    _cached_ip = get_rule_value()
                except Exception as e:
                    print(f"[error] Could not fetch rule value: {e}")
                if _cached_ip is None:
                    _rule_fetch_failed_at = now

        if _cached_ip is None:
            self._send(503, _HTML_NOK)
            return

        if incoming_ip != _cached_ip:
            try:
                update_rule(incoming_ip)
                _cached_ip = incoming_ip
                self._send(200, _HTML_OK.format(ip=incoming_ip))
            except Exception as e:
                print(f"[error] {e}")
                self._send(500, _HTML_NOK)
        else:
            print(f"[trigger] IP unchanged ({incoming_ip})")
            self._send(200, _HTML_NO_CHANGE)

    def _send(self, code: int, body: str) -> None:
        encoded = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        pass  # suppress default CLF access log


def run_trigger_server() -> None:
    print(f"[info] Trigger server on :{TRIGGER_WEBSITE_PORT}  ({TRIGGER_WEBSITE_DOMAIN}{TRIGGER_WEBSITE_PATH})")
    with HTTPServer(("0.0.0.0", TRIGGER_WEBSITE_PORT), TriggerHandler) as httpd:
        httpd.serve_forever()


# ── Polling loop ───────────────────────────────────────────────────────────────
def run_polling_loop() -> None:
    global _cached_ip
    backoff = 5

    while True:
        try:
            current_ip = get_current_ip()

            if _cached_ip is None or current_ip != _cached_ip:
                label = "Initial IP" if _cached_ip is None else f"{_cached_ip} →"
                print(f"[info] {label} {current_ip}")
                update_rule(current_ip)
                _cached_ip = current_ip
            else:
                print(f"[info] IP unchanged ({current_ip})")

            backoff = 5  # reset after a clean iteration
            jitter = random.uniform(-LOOP_JITTER, LOOP_JITTER)
            time.sleep(max(1, LOOP_SECONDS + jitter))

        except Exception as e:
            import traceback
            print(f"[error] {e}")
            traceback.print_exc()
            print(f"[info]  Retrying in {backoff}s")
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)


# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    global _cached_ip

    print("[info] Fetching initial rule state from Pangolin...")
    _cached_ip = get_rule_value()
    if _cached_ip:
        print(f"[info] Cached IP: {_cached_ip}")
    else:
        print("[warn] Could not fetch initial rule value; will push on first check")

    if EXPOSE_TRIGGER_WEBSITE:
        run_trigger_server()
    else:
        run_polling_loop()


if __name__ == "__main__":
    main()
