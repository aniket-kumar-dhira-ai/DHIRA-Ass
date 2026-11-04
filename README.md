# Azure Bot Service gateway

This package contains only the Microsoft Azure Bot Service and Teams-facing
code. It validates incoming Bot Framework activities, maps the authenticated
Teams user to an employee, and forwards the normalized request to the existing
HRMS FastAPI application. HRMS, agent and MCP business logic remain outside the
Azure gateway.

## Local architecture

```text
Teams / Bot Emulator
        -> Azure bot gateway :3979/api/messages
        -> existing HRMS FastAPI :3978/api/internal/chat
        -> mock, REST or MCP HRMS provider
```

The ports are intentionally different. Port `3979` is the Teams-facing
gateway, while port `3978` is the private business-logic backend. A Bot
Framework activity's `serviceUrl` is supplied by Microsoft Teams (or by Bot
Framework Emulator) and identifies the channel callback used for replies. It
is not the gateway URL and it is not `AGENT_BACKEND_URL`.

## Run locally

From `hrms_teams_bot`, start the existing HR backend:

```powershell
..\myenv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 3978
```

Both the Azure gateway and the HR FastAPI backend load configuration from
`azure_bot_service/.env`, regardless of the terminal's working directory.
This is the single active configuration file. Copy the configuration and start
the separate gateway:

```powershell
Copy-Item azure_bot_service\.env.example azure_bot_service\.env
..\myenv\Scripts\python.exe -m uvicorn azure_bot_service.app:app --host 0.0.0.0 --port 3979 --reload
```

Set `AGENT_BACKEND_API_KEY` once in this file. The Azure gateway sends it and
the HR backend validates the same value. `INTERNAL_AGENT_API_KEY` remains an
optional backward-compatible override but is no longer required. The public
`/api/chat` route remains only for local Swagger testing.

You can also run the gateway with:

```powershell
..\myenv\Scripts\python.exe -m azure_bot_service
```

`MICROSOFT_APP_PASSWORD` must be the client secret **Value** shown once when
the secret is created. A UUID copied from the Secret ID column is not the app
password, and the readiness endpoint reports this mistake.

Operational endpoints:

- `http://127.0.0.1:3979/health`
- `http://127.0.0.1:3979/ready`
- `http://127.0.0.1:3979/docs`
- Bot messages: `POST http://127.0.0.1:3979/api/messages`

Connect Bot Framework Emulator to `http://localhost:3979/api/messages`. Empty
Microsoft credentials are acceptable only for local Emulator testing.

## Azure configuration

1. Create a single-tenant Microsoft Entra application registration.
2. Create a client secret or, where supported by the hosting design, use a
   certificate/federated identity. Never commit the credential.
3. Create an Azure Bot resource using the Entra application ID.
4. Enable the Microsoft Teams channel.
5. Deploy this gateway to a public HTTPS host.
6. Set the Azure Bot messaging endpoint to
   `https://YOUR-HOST/api/messages`.
7. Configure the environment values from `.env.example` in the hosting secret
   store or Azure Key Vault.
8. Replace placeholders in `manifest/manifest.template.json`, add 32x32
   outline and 192x192 color icons, zip the three files, and upload the Teams
   app through Developer Portal or the Teams admin center.
9. Add an Azure Bot OAuth connection when Entra SSO or ERPNext account linking
   is implemented. OAuth tokens must stay server-side and outside LLM prompts.

## Production changes still required

- Replace `AZURE_BOT_AAD_EMPLOYEE_MAP` with the database-backed identity and
  Bot Token Service described in the architecture report.
- Protect the HR backend with network isolation plus an internal service
  identity. `X-Internal-Api-Key` is a starter boundary, not the ideal final
  Azure design.
- Disable Emulator access and remove local credentials.
- Use per-user ERPNext OAuth tokens in the MCP/ERPNext layer.
- Add confirmation cards and idempotency for writes.
- Add rate limiting, redacted audit logging, monitoring and webhook validation.

