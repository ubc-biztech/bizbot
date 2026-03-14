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
