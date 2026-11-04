from __future__ import annotations

import traceback
import sys
import logging
from pathlib import Path

from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings
from botbuilder.schema import Activity
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

if __package__ in {None, ""}:
    # Support `python azure_bot_service/app.py` as well as package execution.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from azure_bot_service.agent_client import AgentBackendClient
    from azure_bot_service.bot import AzureHrBot
    from azure_bot_service.config import AzureBotSettings
else:
    from .agent_client import AgentBackendClient
    from .bot import AzureHrBot
    from .config import AzureBotSettings


ENV_FILE = Path(__file__).with_name(".env")
load_dotenv(ENV_FILE)
logger = logging.getLogger("azure_bot_service.authentication")
settings = AzureBotSettings.from_env()
adapter = BotFrameworkAdapter(
    BotFrameworkAdapterSettings(
        settings.microsoft_app_id,
        settings.microsoft_app_password,
        channel_auth_tenant=settings.microsoft_app_tenant_id or None,
    )
)
agent = AgentBackendClient(
    settings.agent_backend_url,
    settings.agent_backend_api_key,
    settings.request_timeout_seconds,
)
bot = AzureHrBot(settings, agent)


async def on_error(turn_context, error: Exception) -> None:
    traceback.print_exception(type(error), error, error.__traceback__)
    await turn_context.send_activity(
        "The HR Assistant encountered an error. Please try again later."
    )


adapter.on_turn_error = on_error

app = FastAPI(
    title="Azure Bot Service Gateway for HRMS",
    description=(
        "Dedicated Microsoft Azure Bot Service/Teams activity endpoint. "
        "Business logic remains in the separate HRMS FastAPI backend."
    ),
    version="1.0.0",
)


@app.post(
    "/api/messages",
    status_code=status.HTTP_201_CREATED,
    tags=["Azure Bot"],
    summary="Receive a Microsoft Bot Framework activity",
    description=(
        "Public HTTPS webhook configured as the Azure Bot messaging endpoint. "
        "Microsoft Teams sends a complete Bot Framework activity and Bearer "
        "token here; this is not a simple chat-query endpoint."
    ),
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"type": "object", "additionalProperties": True},
                    "example": {
                        "type": "message",
                        "channelId": "emulator",
                        "from": {"id": "local-user", "name": "Test User"},
                        "recipient": {"id": "bot", "name": "HR Assistant"},
                        "conversation": {"id": "local-conversation"},
                        "text": "How many leaves do I have?",
                        "serviceUrl": "https://smba.trafficmanager.net/REGION/",
                    },
                }
            },
        }
    },
)
async def messages(request: Request) -> Response:
    if "application/json" not in request.headers.get("Content-Type", ""):
        raise HTTPException(status_code=415, detail="Content-Type must be application/json")
    try:
        body = await request.json()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON body") from exc
    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")
    try:
        invoke_response = await adapter.process_activity(
            activity, auth_header, bot.on_turn
        )
    except PermissionError as exc:
        # Log only the validator's reason. Never log the Authorization header.
        logger.warning("Bot Framework authentication failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "A valid Microsoft Bot Framework Authorization Bearer token is "
                "required. Teams/Azure Bot Service supplies this automatically; "
                "a direct Swagger request does not."
            ),
        ) from exc
    if invoke_response:
        return JSONResponse(
            content=invoke_response.body, status_code=invoke_response.status
        )
    return Response(status_code=status.HTTP_201_CREATED)


@app.get("/health", tags=["Operations"])
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "azure-bot-gateway",
        "agent_backend": settings.agent_backend_url,
        "environment_file": str(ENV_FILE),
        "configuration_warnings": settings.production_warnings(),
    }


@app.get("/ready", tags=["Operations"])
async def ready() -> dict[str, str]:
    warnings = settings.production_warnings()
    if warnings:
        raise HTTPException(status_code=503, detail={"configuration_warnings": warnings})
    return {"status": "ready"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.port)

