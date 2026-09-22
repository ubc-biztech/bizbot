# BizBot

BizTech's Discord mentorship ticket bot, built with Python 3.13, discord.py,
FastAPI, DynamoDB, and uv. Docker runs the bot and HTTP API in one process.

## Run with Docker

Install [Docker Engine and the Compose plugin](https://docs.docker.com/engine/install/ubuntu/).
For a fresh Lightsail host, Ubuntu 24.04 with 2 GB RAM is a reasonable starting
point; check `docker stats` under event load before choosing a smaller instance.

```bash
git clone https://github.com/ubc-biztech/bizbot.git
cd bizbot
cp .env.example .env
chmod 600 .env
# Fill in .env before starting.
docker compose up -d --build --wait --wait-timeout 180
docker compose logs --tail=100 -f
```

The image installs the committed `uv.lock`, runs as a non-root user, and excludes
local secrets and virtual environments from the build context. Credentials are
injected at runtime from `.env`. No host Python, uv, Node.js, or PM2 is required.
Docker must start on boot (`sudo systemctl enable --now docker` on Ubuntu).
Compose restarts the process unless explicitly stopped and rotates its logs.

### Environment

| Variable | Purpose |
| --- | --- |
| `DISCORD_TOKEN` | Bot token from the Discord Developer Portal. |
| `DISCORD_GUILD_ID` | Server ID for immediate guild command synchronization; omit for global sync. |
| `AWS_REGION` | DynamoDB region, normally `us-west-2`. |
| `ENVIRONMENT` | Ticket table suffix: `PROD` selects `biztechTicketsPROD`; empty selects `biztechTickets`. |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Dedicated bot credentials for Lightsail. Never use root credentials. |
| `AWS_SESSION_TOKEN` | Also required when using temporary AWS credentials. Refresh before expiry and recreate the container. |

Lightsail does not provide an attachable EC2 instance profile for application
credentials. Use a dedicated IAM principal restricted to the required tables.
On EC2, an instance profile is an alternative, provided the container can reach
IMDS. Do not bake credentials into the image or commit `.env`.

### DynamoDB

The current ticket commands require these existing tables; the bot does not
create them:

| Table | String partition key | String sort key |
| --- | --- | --- |
| `biztechTickets` or `biztechTicketsPROD` | `ticketID` | `eventID;year` |
| `discordEvents` or `discordEventsPROD` | `categoryID` | — |
| `discordRoles` or `discordRolesPROD` | `roleId` | — |

Ticket tables use `ENVIRONMENT`. Event and role tables independently use the
hardcoded `PROD_GUILD_ID` in
`services/discord/constants/temp_discord_roles.py`: that guild uses the `PROD`
tables; other guilds use the unsuffixed tables. Confirm both settings before
starting a production bot. `DYNAMODB_TABLE_NAME` is not read by the application.

For production ticketing, scope IAM permissions to the three production table
ARNs in the target account and region. The current commands use
`dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem`,
`dynamodb:DeleteItem`, and `dynamodb:Scan`.

### Discord event setup

1. Enable **Server Members Intent** and **Message Content Intent** in the
   [Discord Developer Portal](https://discord.com/developers/applications).
2. Invite the bot with `bot` and `applications.commands` scopes. Give it the
   permissions needed to view/send messages, embed links, read message history,
   manage channels, and manage channel permission overwrites.
3. Verify the guild, executive, and mentor IDs in
   `services/discord/constants/temp_discord_roles.py`. Setting
   `DISCORD_GUILD_ID` only controls command sync; it does not replace those IDs.
4. With an executive role, run `/createevent` in a text channel under the event
   category. It enables ticketing and creates missing `ticket-help`,
   `ticket-log`, and `incoming-tickets` channels. Review their permissions;
   newly created channels inherit the category's permissions.
5. Run `/adjustroles` to configure ticket-ping roles, then test `/ticket`, claim,
   and `/close`. Run `/stopevent` to stop new tickets when the event ends.

## Health, networking, and operations

```bash
curl --fail http://127.0.0.1:8000/health
docker compose ps
docker stats --no-stream
docker compose logs --tail=100
docker compose down
```

A healthy container requires `/health` to report `bot_connected: true`, not just
HTTP 200. This checks Discord connectivity, not DynamoDB permissions or correct
roles/channels; verify a complete ticket flow separately. Docker marks failed
probes unhealthy but only restarts an exited process automatically.

The API binds to host loopback because it includes an unauthenticated database
test route. Keep port 8000 private. Discord uses outbound connections; it needs
no public HTTP endpoint, nginx, TLS certificate, or inbound Discord port. For a
remote health check, use an SSH tunnel:

```bash
ssh -L 8000:127.0.0.1:8000 ubuntu@your-vps-ip
```

Restrict the host's inbound SSH rule to trusted administrator addresses.

## Deployment updates

```bash
git pull --ff-only origin main
docker compose up -d --build --wait --wait-timeout 180
```

The existing GitHub Actions SSH deployment now runs this Compose command from
`/opt/bizbot`. Before merging onto `main`, provision that checkout, install Docker
and Compose, create its `.env`, and allow the deployment user to run Docker.
Refresh `LIGHTSAIL_HOST`, `LIGHTSAIL_USER`, and `LIGHTSAIL_SSH_KEY` repository
secrets for the replacement host. Ensure the host can pull the repository.

If migrating a surviving PM2 installation, stop and remove its `bizbot` process
and run `pm2 save` before starting Compose. Run only one bot instance per token.
The old PM2 files remain for reference. Ticket data stays in DynamoDB; no local
data volume is required.

## Local development

```bash
uv sync --locked
uv run python main.py
uv run ruff check .
uv run pyright
```

PR CI also builds the Docker image and checks application imports without
Discord or AWS access.
