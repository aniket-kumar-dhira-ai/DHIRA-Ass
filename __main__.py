"""Run the Azure Bot Service gateway with `python -m azure_bot_service`."""

import uvicorn

from .app import settings


if __name__ == "__main__":
    uvicorn.run(
        "azure_bot_service.app:app",
        host="0.0.0.0",
        port=settings.port,
        reload=False,
    )
