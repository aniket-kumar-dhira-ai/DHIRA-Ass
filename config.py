from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AzureBotSettings:
    microsoft_app_id: str = ""
    microsoft_app_password: str = ""
    microsoft_app_tenant_id: str = ""
    microsoft_app_type: str = "SingleTenant"
    agent_backend_url: str = "http://127.0.0.1:3978"
    agent_backend_api_key: str = ""
    request_timeout_seconds: float = 15.0
    port: int = 3979
    allow_emulator: bool = True
    aad_employee_map: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "AzureBotSettings":
        raw_mapping = os.getenv("AZURE_BOT_AAD_EMPLOYEE_MAP", "{}")
        try:
            mapping = json.loads(raw_mapping)
        except json.JSONDecodeError as exc:
            raise ValueError("AZURE_BOT_AAD_EMPLOYEE_MAP must be valid JSON") from exc
        if not isinstance(mapping, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in mapping.items()
        ):
            raise ValueError("AZURE_BOT_AAD_EMPLOYEE_MAP must map string IDs to employee IDs")

        return cls(
            microsoft_app_id=os.getenv("MICROSOFT_APP_ID", "").strip(),
            microsoft_app_password=os.getenv("MICROSOFT_APP_PASSWORD", "").strip(),
            microsoft_app_tenant_id=os.getenv("MICROSOFT_APP_TENANT_ID", "").strip(),
            microsoft_app_type=os.getenv(
                "MICROSOFT_APP_TYPE", "SingleTenant"
            ).strip(),
            agent_backend_url=os.getenv(
                "AGENT_BACKEND_URL", "http://127.0.0.1:3978"
            ).rstrip("/"),
            agent_backend_api_key=os.getenv("AGENT_BACKEND_API_KEY", "").strip(),
            request_timeout_seconds=float(os.getenv("AZURE_BOT_TIMEOUT_SECONDS", "15")),
            port=int(os.getenv("AZURE_BOT_PORT", "3979")),
            allow_emulator=_as_bool(os.getenv("AZURE_BOT_ALLOW_EMULATOR"), True),
            aad_employee_map=mapping,
        )

    def production_warnings(self) -> list[str]:
        warnings: list[str] = []
        if not self.microsoft_app_id:
            warnings.append("MICROSOFT_APP_ID is empty")
        if not self.microsoft_app_password:
            warnings.append("MICROSOFT_APP_PASSWORD is empty")
        elif re.fullmatch(
            r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}",
            self.microsoft_app_password,
        ):
            warnings.append(
                "MICROSOFT_APP_PASSWORD looks like a Secret ID; use the client secret Value"
            )
        if not self.microsoft_app_tenant_id:
            warnings.append("MICROSOFT_APP_TENANT_ID is empty")
        if not self.agent_backend_api_key:
            warnings.append("AGENT_BACKEND_API_KEY is empty")
        if self.microsoft_app_type not in {"SingleTenant", "MultiTenant"}:
            warnings.append("MICROSOFT_APP_TYPE must be SingleTenant or MultiTenant")
        if not self.aad_employee_map:
            warnings.append("AZURE_BOT_AAD_EMPLOYEE_MAP has no user mappings")
        return warnings

