from __future__ import annotations

from dataclasses import dataclass

import httpx


class AgentBackendError(RuntimeError):
    """A safe error returned when the HR agent backend cannot answer."""


@dataclass(frozen=True)
class AgentUserContext:
    employee_id: str
    aad_object_id: str
    tenant_id: str
    conversation_id: str
    channel_id: str


class AgentBackendClient:
    """HTTP client for the existing FastAPI HRMS/agent application.

    Azure credentials and Bot Framework activities stop at this gateway. Only
    the normalized message and resolved employee identifier are sent onward.
    """

    def __init__(self, base_url: str, api_key: str = "", timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    async def ask(self, message: str, context: AgentUserContext) -> str:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-Internal-Api-Key"] = self.api_key
        payload = {
            "message": message,
            "employee_id": context.employee_id,
            "aad_object_id": context.aad_object_id,
            "tenant_id": context.tenant_id,
            "conversation_id": context.conversation_id,
            "channel_id": context.channel_id,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/internal/chat", json=payload, headers=headers
                )
        except httpx.RequestError as exc:
            raise AgentBackendError("The HR service is temporarily unavailable.") from exc

        if response.status_code == 404:
            detail = response.json().get("detail", "The requested HR record was not found.")
            raise AgentBackendError(str(detail))
        if response.status_code == 422:
            raise AgentBackendError("Please check the request values and date format.")
        if response.status_code in {401, 403}:
            raise AgentBackendError("The HR service did not authorize this request.")
        if response.is_error:
            raise AgentBackendError("The HR service could not complete the request.")

        data = response.json()
        reply = data.get("reply")
        if not isinstance(reply, str) or not reply.strip():
            raise AgentBackendError("The HR service returned an invalid response.")
        return reply

