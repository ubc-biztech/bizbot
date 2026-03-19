## BizBot
is an internal Discord bot built to streamline attendee support at BizTech events. It provides a structured mentorship ticketing system directly within Discord — allowing attendees to request help, mentors to self-assign based on their expertise, and executives to maintain full visibility over support activity in real time.

## Functionality
- **Verification** — attendees and partners authenticate via `/verify` using their registered email, which is checked against the member database and assigned the appropriate Discord role automatically
- **Ticket creation** — members submit help requests through a guided modal flow, specifying a category and problem description, which are posted to a managed queue channel
- **Mentor assignment** — mentors subscribe to skill categories and are pinged on relevant tickets; claiming a ticket is atomic to prevent race conditions, and opens a private channel between the attendee, mentor, and exec team
- **Ticket lifecycle** — tickets move through `OPEN → CLAIMED → CLOSED` states, with a full audit log posted to a dedicated exec-visible log channel

**Stack:**
- **Bot** — Python with `discord.py`, managed by PM2 on an AWS Lightsail VPS
- **Dependency management** — `uv`
- **Database** — AWS DynamoDB
- **Resource Access** — IAM
- **CI/CD** — GitHub Actions

## Deployment Deployment Guide

---

## Prerequisites

- AWS Lightsail VPS running Ubuntu/Debian
- IAM role attached to the Lightsail instance with DynamoDB permissions
- Discord bot token from Discord Developer Portal
- DynamoDB table created in AWS

---

## 1. Initial VPS Setup

SSH into your Lightsail instance:

```bash
ssh ubuntu@your-lightsail-ip
```

### Install System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.13 (if not available, use 3.11+)
sudo apt install -y python3.13 python3.13-venv python3-pip

# Install Node.js and npm (for PM2)
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
sudo apt install -y nodejs

# Install nginx (reverse proxy)
sudo apt install -y nginx

# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env

# Install PM2 globally
sudo npm install -g pm2
```

---

## 2. Clone and Configure the Repository

```bash
# Create deployment directory
sudo mkdir -p /opt/bizbot
sudo chown $USER:$USER /opt/bizbot

# Clone repository
cd /opt/bizbot
git clone https://github.com/your-org/bizbot.git .

# Create environment file from template
cp .env.example .env
nano .env
```

Fill in your actual values in `.env`:

```bash
DISCORD_TOKEN=your_actual_discord_bot_token
DISCORD_GUILD_ID=your_guild_id
DYNAMODB_TABLE_NAME=bizbot-tickets
AWS_REGION=us-east-1
```

### Verify IAM Role Permissions

The Lightsail instance must have an IAM role with DynamoDB access. Test with:

```bash
aws dynamodb list-tables --region us-east-1
```

If this fails, attach an IAM role via the Lightsail console with these permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": "arn:aws:dynamodb:*:*:table/bizbot-*"
    }
  ]
}
```

---

## 3. Install Dependencies and Test

```bash
# Install Python dependencies using uv
uv sync

# Test the bot locally (optional)
uv run python main.py
# Press Ctrl+C to stop after verifying startup
```

---

## 4. Configure PM2

Update the deployment path in `ecosystem.config.js`:

```bash
nano ecosystem.config.js
# Change 'cwd' to: /opt/bizbot
```

Create logs directory:

```bash
mkdir -p logs
```

Start the bot with PM2:

```bash
pm2 start ecosystem.config.js
pm2 logs bizbot  # View logs
```

### Enable Auto-Start on Boot

```bash
pm2 startup
# Follow the instructions output by this command
pm2 save
```

### PM2 Management Commands

```bash
pm2 status              # Check bot status
pm2 logs bizbot         # View logs
pm2 restart bizbot      # Restart bot
pm2 stop bizbot         # Stop bot
pm2 delete bizbot       # Remove from PM2
```

---

## 5. Configure nginx (Reverse Proxy)

Create nginx configuration for the FastAPI endpoints:

```bash
sudo nano /etc/nginx/sites-available/bizbot
```

Add the following configuration:

```nginx
server {
    listen 80;
    server_name your-domain.com;  # Or use IP address

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/bizbot /etc/nginx/sites-enabled/
sudo nginx -t  # Test configuration
sudo systemctl restart nginx
```

Test the API:

```bash
curl http://localhost/health
# Should return: {"status":"ok",...}
```

---

## 6. Set Up SSL (Optional but Recommended)

If using a domain, enable HTTPS with Let's Encrypt:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## 7. Deploying Updates

When pushing new code:

```bash
cd /opt/bizbot
git pull origin main
uv sync  # Update dependencies if needed
pm2 restart bizbot
```

For zero-downtime deployments, consider using PM2's reload:

```bash
pm2 reload bizbot
```

---

## 8. Monitoring and Logs

View real-time logs:

```bash
pm2 logs bizbot --lines 100
```

Monitor resource usage:

```bash
pm2 monit
```

Check nginx logs:

```bash
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```

---

## 9. Troubleshooting

### Bot won't start

Check PM2 logs:

```bash
pm2 logs bizbot --err --lines 50
```

Common issues:
- Invalid `DISCORD_TOKEN` in `.env`
- Missing IAM permissions for DynamoDB
- Port 8000 already in use (check with `sudo lsof -i :8000`)

### DynamoDB connection errors

Verify IAM role:

```bash
aws sts get-caller-identity
aws dynamodb describe-table --table-name bizbot-tickets --region us-east-1
```

### Bot not responding to commands

- Check if bot is online in Discord
- Verify slash commands are synced (check startup logs)
- Ensure bot has proper permissions in your Discord server

---

## 10. Security Best Practices

- Never commit `.env` to git
- Restrict SSH access (use key-based auth only)
- Keep system packages updated: `sudo apt update && sudo apt upgrade`
- Use firewall rules to restrict access to ports 22, 80, 443 only
- Regularly rotate Discord tokens
- Review IAM permissions (principle of least privilege)

---

## Architecture Overview

```
User → Discord → BizBot (discord.py)
                    ↓
                DynamoDB

Admin/Monitoring → nginx → FastAPI (port 8000)
                              ↓
                         BizBot status
```

Both discord.py and FastAPI run in a single Python process managed by PM2, sharing the same asyncio event loop.

---

## Support

For issues or questions:
- Check PM2 logs: `pm2 logs bizbot`
- Review this deployment guide
- Check the main README.md for architecture details
