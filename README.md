# Dynamic IP Updater for Pangolin Rules

[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)](https://www.python.org/)

A lightweight Docker container that automatically monitors your external IP address and updates Pangolin firewall rules when changes are detected. Perfect for home servers, VPS instances, or any infrastructure that needs dynamic IP-based access rules.

## ✨ Features

- **Automatic IP Monitoring** — checks your external IP on a configurable interval
- **Smart Updates** — only calls the Pangolin API when the IP actually changes (local cache, no unnecessary reads)
- **Rotating IP Services** — round-robins across multiple IP-check endpoints to reduce fingerprinting
- **Jittered Intervals** — adds random ± seconds to each check to avoid predictable traffic patterns
- **Exponential Backoff** — backs off gracefully on transient errors instead of hammering the API
- **Persistent HTTP Session** — reuses the TCP connection to Pangolin for lower overhead
- **Dynamic DNS Support** — resolve a hostname instead of checking this machine's own IP
- **Webhook / Trigger Mode** — expose an HTTP endpoint so an external source (e.g. your browser, a cron, a reverse proxy) pushes its IP directly
- **Environment-Based Config** — everything managed through a `.env` file
- **Docker Compose Ready** — single-command deployment

## 📋 Prerequisites

- Docker and Docker Compose
- Pangolin Integration API enabled: https://docs.digpangolin.com/manage/integration-api
- Valid Pangolin API access token with:
  - `Resource Rule → List Resource Rules`
  - `Resource Rule → Update Resource Rule`
- The Rule ID you want to keep updated
  - Visit the Swagger UI at `https://<your-pangolin>/v1/docs`, authorize with your token, and call `GET /resource/{resourceId}/rules` to list rules and find your Rule ID

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/olizimmermann/pangolin_rule_updater.git
   cd pangolin_rule_updater
   ```

2. **Create your environment file**
   ```bash
   cp example.env .env
   ```

3. **Configure your settings** (see [Configuration](#️-configuration) below)

4. **Build and start**
   ```bash
   docker compose up -d
   ```

## ⚙️ Configuration

Create a `.env` file in the project root:

```env
# Pangolin credentials
API_KEY=YOUR_LONG_BEARER_TOKEN
RESOURCE_ID=1
RULE_ID=1
RULE_PRIORITY=1
RULE_ACTION=ACCEPT
RULE_MATCH=IP                # IP, CIDR, PATH
RULE_ENABLED=True
TARGET_DOMAIN=               # dynamic DNS hostname — leave empty to use this machine's IP

PANGOLIN_HOST=https://api.pangolin.example

# Runtime controls (optional)
IP_SERVICE_URL=https://wtfismyip.com/text,https://api.ipify.org,https://icanhazip.com
LOOP_SECONDS=60              # check interval in seconds
LOOP_JITTER=10               # ± random seconds added to each interval

# Webhook trigger (optional)
EXPOSE_TRIGGER_WEBSITE=False
TRIGGER_WEBSITE_DOMAIN=trigger.my.dyn.dns.com
TRIGGER_WEBSITE_PATH=/update
TRIGGER_WEBSITE_PORT=8080
```

### Configuration reference

| Parameter | Required | Default | Description |
|-----------|:--------:|---------|-------------|
| `API_KEY` | ✅ | — | Pangolin API Bearer token |
| `RESOURCE_ID` | ✅ | — | Resource ID in Pangolin |
| `RULE_ID` | ✅ | — | Rule ID to update |
| `PANGOLIN_HOST` | ✅ | `https://api.pangolin.example` | Pangolin API base URL |
| `RULE_PRIORITY` | ❌ | `100` | Rule priority |
| `RULE_ACTION` | ❌ | `ACCEPT` | `ACCEPT` or `DROP` |
| `RULE_MATCH` | ❌ | `IP` | `IP`, `CIDR`, or `PATH` |
| `RULE_ENABLED` | ❌ | `True` | Enable or disable the rule |
| `TARGET_DOMAIN` | ❌ | — | Resolve this hostname instead of checking machine's external IP |
| `IP_SERVICE_URL` | ❌ | three built-in services | Comma-separated list of plain-text IP services, rotated round-robin |
| `LOOP_SECONDS` | ❌ | `60` | Base check interval in seconds |
| `LOOP_JITTER` | ❌ | `10` | Random ± seconds added to each interval |
| `EXPOSE_TRIGGER_WEBSITE` | ❌ | `False` | Enable webhook trigger mode (disables automatic polling) |
| `TRIGGER_WEBSITE_DOMAIN` | ❌ | `trigger.my.dyn.dns.com` | Expected `Host` header for the trigger endpoint |
| `TRIGGER_WEBSITE_PATH` | ❌ | `/update` | Path for the trigger endpoint |
| `TRIGGER_WEBSITE_PORT` | ❌ | `8080` | Port the trigger server listens on |

## 🚀 Usage

### Start the service
```bash
docker compose up -d
```

### View logs
```bash
docker compose logs -f
```

### Stop the service
```bash
docker compose down
```

### Rebuild after changes
```bash
docker compose build --no-cache && docker compose up -d
```

### Using dynamic DNS

Set `TARGET_DOMAIN` to your DynDNS hostname. The script will resolve its IP instead of detecting this machine's external IP.

```env
TARGET_DOMAIN=my.dyn.dns.com
```

### Using the webhook trigger

When `EXPOSE_TRIGGER_WEBSITE=True`, automatic polling is disabled. Instead, a tiny HTTP server listens for incoming connections and uses the **requester's IP** to update the rule. This is handy when the device that needs access can initiate the request itself.

Enable the port in `docker-compose.yml`:

```yaml
services:
  ip-updater:
    build: .
    env_file: .env
    restart: unless-stopped
    ports:
      - "${TRIGGER_WEBSITE_PORT}:${TRIGGER_WEBSITE_PORT}"
```

Set in `.env`:

```env
EXPOSE_TRIGGER_WEBSITE=True
TRIGGER_WEBSITE_DOMAIN=trigger.my.dyn.dns.com
TRIGGER_WEBSITE_PATH=/update
TRIGGER_WEBSITE_PORT=8080
```

> ⚠️ **Security note:** Anyone who can reach this endpoint can update your firewall rule. Use an unpredictable subdomain and path, restrict access at the network level where possible, and never expose it without a trusted front-end.

## 🐳 Stack deployment in Portainer (example)

```yaml
services:
  pangolin-rule-updater:
    container_name: pangolin-rule-updater
    build:
      context: https://github.com/olizimmermann/pangolin_rule_updater.git#main
      dockerfile: Dockerfile
    restart: unless-stopped
    environment:
      # --- Required ---
      API_KEY: YOUR_API_TOKEN
      RESOURCE_ID: "1"
      RULE_ID: "1"
      PANGOLIN_HOST: "https://api.example.com"

      # --- Optional ---
      RULE_PRIORITY: "1"
      RULE_ACTION: "ACCEPT"
      RULE_MATCH: "IP"
      RULE_ENABLED: "True"

      IP_SERVICE_URL: "https://wtfismyip.com/text,https://api.ipify.org"
      LOOP_SECONDS: "60"
      LOOP_JITTER: "10"
```

## 📁 Project structure

```
pangolin-ip-updater/
├── Dockerfile              # Container definition
├── docker-compose.yml      # Service orchestration
├── update_ip.py            # Main application logic
├── requirements.txt        # Python dependencies
├── example.env             # Template for environment variables
├── .env                    # Your actual config (create this, never commit it)
└── README.md
```

## 🔧 API reference

### List rules
```bash
curl -X GET \
  'https://api.pangolin.example/v1/resource/{RESOURCE_ID}/rules' \
  -H 'Authorization: Bearer {API_KEY}'
```

### Update rule
```bash
curl -X POST \
  'https://api.pangolin.example/v1/resource/{RESOURCE_ID}/rule/{RULE_ID}' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer {API_KEY}' \
  -d '{"action":"ACCEPT","match":"IP","value":"1.2.3.4","priority":1,"enabled":true}'
```

## 🐛 Troubleshooting

| Symptom | Check |
|---------|-------|
| Container exits immediately | `.env` exists and has all required variables; API key is valid |
| `401` / auth errors | `API_KEY` correct and active; `Bearer` prefix is added automatically |
| Rule not updating | Correct `RESOURCE_ID` + `RULE_ID`; test with the curl commands above |
| Network errors | Container has internet access; try a different `IP_SERVICE_URL` |

**View live logs:**
```bash
docker compose logs -f
```

## 🔒 Security considerations

- **Never commit `.env`** — it contains your API credentials
- Restrict file permissions: `chmod 600 .env`
- Use Docker secrets for production deployments
- Rotate API keys regularly
- If using the trigger website, prefer a non-guessable subdomain, path, and port

## 🚀 Advanced usage

### Custom check intervals
```env
LOOP_SECONDS=300   # check every 5 minutes
LOOP_JITTER=30     # ± 30 s randomisation
```

### IPv6
```env
IP_SERVICE_URL=https://api6.ipify.org
```

### Multiple rules
Deploy separate containers with different `.env` files:
```bash
docker compose -f docker-compose.rule1.yml up -d
docker compose -f docker-compose.rule2.yml up -d
```

## ⭐ Like this project?

If this saved you time, please consider giving it a star on GitHub — it helps others find the project and motivates further development!

[![Star on GitHub](https://img.shields.io/github/stars/olizimmermann/pangolin_rule_updater?style=social)](https://github.com/olizimmermann/pangolin_rule_updater)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

MIT — see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Pangolin](https://github.com/fosrl/pangolin) for the great self-hosted tunneling platform
- [ipify](https://www.ipify.org/) for a reliable IP detection API
- Docker community for containerisation best practices

---

**Found a bug or have a question? Open an [issue](https://github.com/olizimmermann/pangolin_rule_updater/issues).**
