import os
import socketserver
import time
import json
from urllib import response
import requests
import socket

from dotenv import load_dotenv

load_dotenv()                              # read .env at runtime

API_KEY        = os.environ["API_KEY"]
RESOURCE_ID    = os.environ["RESOURCE_ID"]
RULE_ID        = os.environ["RULE_ID"]
PANGOLIN_HOST  = os.environ.get("PANGOLIN_HOST", "https://api.pangolin.example:3004") # new ip since 1.9.0
IP_SERVICE_URL = os.environ.get("IP_SERVICE_URL", "https://api.ipify.org")
TARGET_DOMAIN  = os.environ.get("TARGET_DOMAIN", "my.dyn.dns.com") # your dyn dns
LOOP_SECONDS   = int(os.environ.get("LOOP_SECONDS", "60"))
RULE_PRIORITY  = int(os.environ.get("RULE_PRIORITY", "100"))
RULE_ACTION    = os.environ.get("RULE_ACTION", "ACCEPT").upper()
RULE_MATCH     = os.environ.get("RULE_MATCH", "IP").upper()

EXPOSE_TRIGGER_WEBSITE = os.environ.get("EXPOSE_TRIGGER_WEBSITE", "False").lower() == "true"
if EXPOSE_TRIGGER_WEBSITE:
    TRIGGER_WEBSITE_DOMAIN = os.environ.get("TRIGGER_WEBSITE_DOMAIN", "trigger.my.dyn.dns.com")
    TRIGGER_WEBSITE_PATH = os.environ.get("TRIGGER_WEBSITE_PATH", "/update")
    TRIGGER_WEBSITE_PORT = int(os.environ.get("TRIGGER_WEBSITE_PORT", "8080"))

if RULE_MATCH not in ["IP", "CIDR", "PATH"]:
    raise ValueError(f"Invalid RULE_MATCH: {RULE_MATCH}")
RULE_ENABLED  = os.environ.get("RULE_ENABLED", "True").lower() == "true" 

HEADERS = {
    "accept": "*/*",
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

def get_target_ip() -> str:
    """Return the current IPv4 address of the target hostname."""
    try:
        ip = socket.gethostbyname(TARGET_DOMAIN)
        return ip
    except socket.gaierror as e:
        raise Exception(f"Failed to resolve {TARGET_DOMAIN}: {e}")

def get_external_ip() -> str:
    """Return the current public IPv4 address as a string."""
    return requests.get(IP_SERVICE_URL, timeout=5).text.strip()

def get_rule_value() -> str:
    """Fetch the current `value` field of the Pangolin rule."""
    url = f"{PANGOLIN_HOST}/v1/resource/{RESOURCE_ID}/rules?limit=1000&offset=0"
    resp = requests.get(url, headers=HEADERS, timeout=10)
    if resp.status_code != 200:
        print(f"[error] Failed to fetch rules: {resp.status_code} {resp.text}")
        return None
    rules = resp.json()["data"]["rules"]
    print(f"[pangolin] Fetched {len(rules)} rules")
    for rule in rules:
        if rule["ruleId"] == int(RULE_ID):
            return rule["value"]
    print(f"[info] Rule ID {RULE_ID} not found")
    return None

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
    if resp.status_code != 200:
        print(f"[error] Failed to update rule {RULE_ID}: {resp.status_code} {resp.text}")
    print(f"[pangolin] Updated rule {RULE_ID} to {new_ip}")

class RequestHandler(socketserver.BaseRequestHandler):
    html_template_ok = """
    <html>
    <head><title>IP Update Trigger</title></head>
    <body>
    <h1>IP Update Trigger</h1>
    <p>An update was triggered.</p>
    <p>New IP: {incoming_ip_address}</p>
    <p>Old IP: {stored_ip}</p>
    </body>
    </html>
    """
    html_template_nok = """
    <html>
    <head><title>IP Update Trigger</title></head>
    <body>
    <h1>IP Update Trigger</h1>
    <p>An update was not triggered.</p>
    </body>
    </html>
    """
    html_template_no_change = """
    <html>
    <head><title>IP Update Trigger</title></head>
    <body>
    <h1>IP Update Trigger</h1>
    <p>No IP update was necessary.</p>
    </body>
    </html>
    """

    def handle(self):
        # Simple HTTP response for trigger
        request_data = self.request.recv(1024).decode(errors="ignore")
        
        # print(self.request)
        # Parse HTTP request to extract Host and Path
        response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + RequestHandler.html_template_nok
        lines = request_data.split("\r\n")
        path = ""
        host = ""
        incoming_ip_address = None
        if lines:
            # First line: GET /path HTTP/1.1
            parts = lines[0].split()
            if len(parts) > 1:
                path = parts[1]
            print(lines[1:])
            for line in lines[1:]:
                if line.lower().startswith("host:"):
                    host = line.split(":", 1)[1].strip()
                if line.lower().startswith("x-forwarded-for:"):
                    incoming_ip_address = line.split(":", 1)[1].strip()
                    print(f"[info] Incoming request from (X-Forwarded-For): {incoming_ip_address}")
                if line.lower().startswith("cf-connecting-ip:"):
                    incoming_ip_address = line.split(":", 1)[1].strip()
                    print(f"[info] Incoming request from (CF-Connecting-IP): {incoming_ip_address}")

        print(f"[info] Incoming request address: {host}{path}")
        host = host.split(":")[0]
        if path == TRIGGER_WEBSITE_PATH and host == TRIGGER_WEBSITE_DOMAIN:
            if not incoming_ip_address:
                incoming_ip_address = self.client_address[0]
            print(f"[info] Incoming request from: {incoming_ip_address}")
            stored_ip = get_rule_value()
            if incoming_ip_address != stored_ip and stored_ip is not None:
                update_rule(incoming_ip_address)
                print(f"[info] IP address changed: {incoming_ip_address} != {stored_ip}")
                response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + RequestHandler.html_template_ok
            elif stored_ip is not None:
                print(f"[info] IP address unchanged: {incoming_ip_address} == {stored_ip}")
                response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + RequestHandler.html_template_no_change
            else:
                print(f"[info] No IP address stored/Rule not found")
                response = "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n\r\n" + RequestHandler.html_template_nok

        self.request.sendall(response.encode())

def main():
    if EXPOSE_TRIGGER_WEBSITE:
        # listen on TRIGGER_WEBSITE_DOMAIN:TRIGGER_WEBSITE_PORT
        while True:
            # open http server
            try:
                with socketserver.TCPServer(('0.0.0.0', TRIGGER_WEBSITE_PORT), RequestHandler) as httpd:
                    print(f"[info] Listening for updates on {TRIGGER_WEBSITE_DOMAIN}:{TRIGGER_WEBSITE_PORT}")
                    httpd.serve_forever()
            except Exception as e:
                print(f"[error] {e}")
    else:
        while True:
            try:
                if TARGET_DOMAIN != "my.dyn.dns.com": # the TARGET_DOMAIN is set, that means you want to use it
                    current_ip = get_target_ip() 
                else:
                    current_ip = get_external_ip() # default, get the external IP address of this machine
                stored_ip  = get_rule_value()
                if stored_ip is None:
                    print(f"[info] No IP address stored")
                    continue
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

