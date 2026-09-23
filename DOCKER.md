## Docker deployment

The image runs the Discord bot and FastAPI in one Python 3.13 process as a
non-root user. Dependencies come from `uv.lock`. Docker replaces PM2 for this
setup; Node.js and nginx are not required to run the bot.

### Build now, without credentials

Install [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)
on Windows and use Linux containers. From this directory:

```sh
docker build -t bizbot:local .
```

This does not connect to Discord or AWS. `.dockerignore` allows only build inputs,
and the image does not include `.env`. The build follows the
[uv Docker integration](https://docs.astral.sh/uv/guides/integration/docker/).

### Configure runtime access

If `.env` does not already exist, copy `.env.example` to `.env` (PowerShell:
`Copy-Item .env.example .env`; Linux: `cp .env.example .env`). Preserve an existing
`.env` and fill in the missing values:

- `DISCORD_TOKEN`: the bot token, provided securely by its owner.
- `DISCORD_GUILD_ID`: the target Discord server ID.
- `AWS_REGION`: the region containing the actual DynamoDB tables. The example
  uses `us-west-2`; confirm it with the team before deployment.
- `ENVIRONMENT`: optional suffix appended to database table names; leave empty
  only if the intended tables have no suffix.
- AWS credentials using the team's approved method. For environment credentials,
  set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`, plus `AWS_SESSION_TOKEN`
  for temporary credentials. Temporary credentials must be renewed before expiry.

Compose passes `.env` into the running container. Host AWS profiles are not
mounted automatically. Do not commit credentials or put them into Docker build
arguments. On Linux, protect the file with `chmod 600 .env`.

The previous guide's automatic Lightsail instance-role authentication assumption
is not a working credential setup. Arrange credentials and least-privilege
DynamoDB permissions with the AWS administrator before starting the bot.

`DYNAMODB_TABLE_NAME` is currently not used. Ticket operations use the hardcoded
`biztechTickets` plus `ENVIRONMENT`. Other features use additional tables,
including `discordEvents` / `discordEventsPROD` and `discordRoles` /
`discordRolesPROD`, selected by guild ID and then suffixed by `ENVIRONMENT`.
Confirm the existing tables, schemas, guild configuration, and required
permissions with the team; this Docker setup does not create tables.

In Discord, invite the bot with the bot and application-command scopes, enable
Server Members Intent and Message Content Intent in the Developer Portal, and
configure its server permissions and role hierarchy. The code also contains
server-specific role IDs in `services/discord/constants/temp_discord_roles.py`.
Confirm these match your target server.

### Start and verify

```sh
docker compose up -d --build --wait --wait-timeout 180
docker compose ps
docker compose logs --follow --tail=100 bizbot
```

Inspect `http://localhost:8000/health` from the host. Container health requires
`bot_connected: true`; it does not verify DynamoDB permissions or successful cog
loading. Check startup logs and test a ticket flow in the intended server.
Docker reports an unhealthy container but does not restart it solely because of
health status. Exited processes restart under `unless-stopped`.

The HTTP API binds to the host's loopback address only because it includes an
unauthenticated database test endpoint. Discord uses outbound connections; no
public HTTP port is needed. Do not expose port 8000 publicly.

### Lightsail host setup

1. Create an Ubuntu Lightsail instance in the team's AWS account and connect by
   SSH. Confirm the plan and region with the account owner.
2. Install [Docker Engine and the Compose plugin](https://docs.docker.com/engine/install/ubuntu/).
   Enable the daemon at boot with `sudo systemctl enable --now docker`.
3. Clone this repository into `/opt/bizbot` and configure `.env` there as above.
   The deploy SSH user needs permission to run Docker and read that checkout.
4. If migrating an existing PM2 deployment, run `pm2 stop bizbot` and
   `pm2 delete bizbot`, then `pm2 save`, as its owner before starting Docker.
   This prevents duplicate bots and port conflicts.
5. Run the start and verification commands above from `/opt/bizbot`.

Keep SSH access restricted to approved sources. No domain, static IP, nginx, or
TLS certificate is required for the outbound Discord bot connection.

### Updates and management

```sh
git pull --ff-only origin main
docker compose up -d --build --wait --wait-timeout 180
```

Re-run `up` after changing `.env`; `restart` does not apply environment changes.
Updates recreate the container and briefly interrupt the bot. DynamoDB data
remains in AWS. Keep one running instance of this bot.

| Task | Command | Optional Make shortcut |
| --- | --- | --- |
| Build without credentials | `docker build -t bizbot:local .` | `make build` |
| Build and start/update | `docker compose up -d --build --wait --wait-timeout 180` | `make up` |
| View logs | `docker compose logs --follow --tail=100 bizbot` | `make logs` |
| Status | `docker compose ps` | `make status` |
| Restart existing container | `docker compose restart bizbot` | `make restart` |
| Stop and remove container | `docker compose down` | `make down` |

Make is optional; use the Docker commands directly in PowerShell. Logs rotate
at 10 MB per file with three files retained.

### GitHub Actions

The team's existing `deploy.yml` remains unchanged and uses PM2. Docker deployment
is manual using the commands above. Coordinate a workflow migration before using
Docker on the same host targeted by that workflow, or a later push could restart
the PM2 bot alongside the container.

The separate `docker.yml` workflow only builds the image for pull requests;
it does not deploy or use runtime credentials.

A failed readiness wait does not roll back or stop the container automatically.
Inspect `docker compose ps` and logs on the host.
