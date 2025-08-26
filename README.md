# Dynamic IP Updater for Pangolin Rules

[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)](https://www.python.org/)

A lightweight Docker container that automatically monitors your external IP address and updates Pangolin rules when changes are detected. Perfect for home servers, VPS instances, or any infrastructure that needs to maintain dynamic IP-based firewall rules.

## 🚀 Features

- **Automatic IP Monitoring**: Checks your external IP address every minute (configurable)
- **Smart Updates**: Only updates firewall rules when IP actually changes
- **Environment-Based Configuration**: All settings managed through `.env` file
- **Docker Compose Ready**: Easy deployment with single command
- **Robust Error Handling**: Continues running even if API calls fail temporarily
- **Detailed Logging**: Track all IP changes and rule updates

## 📋 Prerequisites

- Docker and Docker Compose installed
- Enable the Integration API: https://docs.digpangolin.com/manage/integration-api
- Valid Pangolin API access token
  - Permission required: Resource Rule -> List Resource Rules
  - Permission required: Resource Rule -> Update Resource Rule
- Pangolin rule ID that you want to update
  - Visit the Swagger API at https://api.url.com/v1/docs
Authorize using your Pangolin API token
Enter your Resource ID (from the URL in Pangolin) into the Rules /resource/{resourceId}/rules API and click "Execute". This will list out all the Rules and the Rule ID associated with the Pangolin Resource

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/olizimmermann/pangolin_rule_updater.git
   cd pangolin_rule_updater
   ```

2. **Create your environment file**
   ```bash
   cp .env.example .env
   ```

3. **Configure your settings** (see Configuration section below)

4. **Build and start the container**
   ```bash
   docker compose up -d
   ```

## ⚙️ Configuration

Create a `.env` file in the project root with the following variables:

```env
# Pangolin credentials
API_KEY=YOUR_LONG_BEARER_TOKEN
RESOURCE_ID=1 # replace with your resource id
RULE_ID=1 # replace with your rule
RULE_PRIORITY=1 # replace with yours
RULE_ACTION=ACCEPT 
RULE_MATCH=IP # IP, CIDR, PATH 
RULE_ENABLED=True
TARGET_DOMAIN=my.dyn.dns.com  # your dynamic DNS hostname or leave empty to check for current IP of the host

PANGOLIN_HOST=https://api.pangolin.example:3004

# Runtime controls (optional)
IP_SERVICE_URL=https://api.ipify.org     # any plain-text IP service
LOOP_SECONDS=60                          # check interval in seconds


# Enable this to expose a website to trigger an update, make sure that only trusted clients can access it/know it
EXPOSE_TRIGGER_WEBSITE=False
TRIGGER_WEBSITE_DOMAIN=trigger.my.dyn.dns.com
TRIGGER_WEBSITE_PATH=/update
TRIGGER_WEBSITE_PORT=8080                  # check interval in seconds
```

### Configuration Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `API_KEY` | ✅ | - | Your Pangolin API Bearer token |
| `RESOURCE_ID` | ✅ | - | The resource ID in Pangolin API |
| `RULE_ID` | ✅ | - | The specific rule ID to update |
| `PANGOLIN_HOST` | ✅  | `https://api.pangolin.example` | Pangolin API base URL |
| `RULE_PRIORITY` | ❌ | 100 | The specific rule priority |
| `RULE_ACTION` | ❌ | ACCEPT | The specific rule action [ACCEPT, DROP]  |
| `RULE_MATCH` | ❌ | IP | The specific rule match [IP, CIDR, PATH] |
| `RULE_ENABLED` | ❌ | True | Enable or disable the rule |
| `IP_SERVICE_URL` | ❌ | `https://api.ipify.org` | External IP detection service |
| `LOOP_SECONDS` | ❌ | `60` | Check interval in seconds |
| `TARGET_DOMAIN` | ❌ | `my.dyn.dns.com` | Your dynamic DNS hostname (disables the default self-ip-check)|
| `EXPOSE_TRIGGER_WEBSITE` | ❌ | False | Enable trigger website for manual updates (disables automatic updates) |
| `TRIGGER_WEBSITE_DOMAIN` | ❌ | `trigger.my.dyn.dns.com` | Domain for the trigger website |
| `TRIGGER_WEBSITE_PATH` | ❌ | `/update` | Path for the trigger website |
| `TRIGGER_WEBSITE_PORT` | ❌ | 8080 | Port for the trigger website |

## 🚀 Usage

### Start the Service
```bash
docker compose up -d
```

### View Logs
```bash
docker compose logs -f
```

### Stop the Service
```bash
docker compose down
```

### Rebuild After Changes
```bash
docker compose build --no-cache
docker compose up -d
```

### Using DYN DNS

Just set the `TARGET_DOMAIN` variable in your `.env` file to your dynamic DNS hostname. **This will replace the default self-IP check.**

### Using the trigger webservice

The trigger webservice allows you to manually trigger an IP update by sending a request to the specified endpoint, or just by visiting the URL in your browser. Set the following in your `docker-compose.yml`:

```yaml
services:
  ip-updater:
    build: .
    env_file: .env       
    restart: unless-stopped
    ports:
      - "${TRIGGER_WEBSITE_PORT}:${TRIGGER_WEBSITE_PORT}"
```

In your `.env` file, set the following variables:

```env
EXPOSE_TRIGGER_WEBSITE=True
TRIGGER_WEBSITE_DOMAIN=trigger.my.dyn.dns.com
TRIGGER_WEBSITE_PATH=/update
TRIGGER_WEBSITE_PORT=8080
```

#### Warning: Exposing the trigger website can pose security risks. Ensure that only trusted clients can access it.

Choose a slightly cryptic subdomain name for your trigger website to make it less predictable. As a best practice, avoid using easily guessable names. Same goes for the path and port.

If you have enabled the trigger webservice, **the self-IP check and the dynamic DNS update will be disabled, and you will need to manually trigger updates via the webservice.

## 🚀 Stack Deployment in Portainer (Example)
```bash
services:
  pangolin-rule-updater:
    container_name: pangolin-rule-updater
    build:
      context: https://github.com/olizimmermann/pangolin_rule_updater.git#main
      dockerfile: Dockerfile
    restart: unless-stopped
    environment:
      # --- Required ---
      API_KEY: YOUR_API_TOKEN  # Pangolin API Token
      RESOURCE_ID: "1"                      # ID of your Pangolin Resource
      RULE_ID: "1"                          # ID of your Rule

      # --- Optional ---
      RULE_PRIORITY: "1"
      RULE_ACTION: "ACCEPT"                 # ACCEPT oder DROP
      RULE_MATCH: "IP"                      # IP, CIDR oder PATH
      RULE_ENABLED: "True"
      PANGOLIN_HOST: "https://api.example.com"

      IP_SERVICE_URL: "https://api.ipify.org" # External IP
      LOOP_SECONDS: "60"                       # Check interval in seconds
```

## 📁 Project Structure

```
pangolin-ip-updater/
├── Dockerfile              # Container definition
├── docker-compose.yml      # Service orchestration
├── update_ip.py            # Main application logic
├── requirements.txt        # Python dependencies
├── .env.example            # Template for environment variables
├── .env                    # Your actual configuration (create this)
├── .gitignore              # Git ignore rules
└── README.md               # This file
```

## 🔧 API Reference

The application interacts with Pangolin API using these endpoints:

### Get Rule Information
```bash
curl -X 'GET' \
  'https://api.pangolin.example/v1/resource/{RESOURCE_ID}/rules' \
  -H 'Authorization: Bearer {API_KEY}'
```

### Update Rule
```bash
curl -X 'POST' \
  'https://api.pangolin.example/v1/resource/{RESOURCE_ID}/rule/{RULE_ID}' \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer {API_KEY}' \
  -d '{
    "action": "ACCEPT",
    "match": "IP",
    "value": "NEW.IP.ADDRESS.HERE",
    "priority": 2,
    "enabled": true
  }'
```

## 🐛 Troubleshooting

### Common Issues

**Container exits immediately**
- Check your `.env` file exists and has all required variables
- Verify your API key is valid
- Check logs: `docker compose logs`

**API authentication errors**
- Ensure your `API_KEY` is correct and active
- Verify the Bearer token format

**Rule not updating**
- Confirm `RESOURCE_ID` and `RULE_ID` are correct
- Test API access manually with curl commands above
- Check if your IP actually changed

**Network connectivity issues**
- Verify container has internet access
- Try different IP detection service in `IP_SERVICE_URL`

### Debug Mode
To run with more verbose logging:
```bash
docker compose logs -f ip-updater
```

## 🔒 Security Considerations

- **Never commit your `.env` file** - it contains sensitive API credentials
- Store your `.env` file securely and restrict file permissions
- Consider using Docker secrets for production deployments
- Regularly rotate your API keys

## 🚀 Advanced Usage

### Multiple Rules
To update multiple rules, deploy separate containers with different `.env` files:

```bash
# Rule 1
docker compose -f docker-compose.rule1.yml up -d

# Rule 2  
docker compose -f docker-compose.rule2.yml up -d
```

### Custom Check Intervals
Adjust the `LOOP_SECONDS` variable for different check frequencies:
- `30` - Every 30 seconds (aggressive)
- `300` - Every 5 minutes (conservative)
- `3600` - Every hour (minimal)

### IPv6 Support
To monitor IPv6 addresses, update your `.env`:
```env
IP_SERVICE_URL=https://api6.ipify.org
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Pangolin](https://pangolin.example) for providing this great project
- [ipify](https://www.ipify.org/) for reliable IP detection service
- Docker community for containerization best practices

## 📞 Support

If you encounter any issues or have questions:

1. Check the [Troubleshooting](#-troubleshooting) section
2. Review existing [Issues](https://github.com/olizimmermann/pangolin_rule_updater/issues)
3. Create a new issue with detailed information about your problem

---

**⭐ If this project helped you, please consider giving it a star!**
