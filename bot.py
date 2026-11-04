from __future__ import annotations

from botbuilder.core import ActivityHandler, MessageFactory, TurnContext
from botbuilder.schema import ChannelAccount

from .agent_client import AgentBackendClient, AgentBackendError, AgentUserContext
from .config import AzureBotSettings


WELCOME = (
    "Welcome to the HR Assistant. Ask naturally, for example: "
    "'How many leaves do I have?', 'What is the status of my family leave?', "
    "or 'Show upcoming holidays'."
)


class AzureHrBot(ActivityHandler):
    def __init__(self, settings: AzureBotSettings, agent: AgentBackendClient) -> None:
        self.settings = settings
        self.agent = agent

    async def on_members_added_activity(
        self, members_added: list[ChannelAccount], turn_context: TurnContext
    ) -> None:
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(MessageFactory.text(WELCOME))

    @staticmethod
    def _is_personal_chat(turn_context: TurnContext) -> bool:
        conversation_type = getattr(
            turn_context.activity.conversation, "conversation_type", None
        )
        return conversation_type in (None, "personal")

    def _resolve_employee(self, turn_context: TurnContext) -> tuple[str, str]:
        sender = turn_context.activity.from_property
        aad_object_id = getattr(sender, "aad_object_id", None) or ""
        if aad_object_id and aad_object_id in self.settings.aad_employee_map:
            return self.settings.aad_employee_map[aad_object_id], aad_object_id
        if (
            turn_context.activity.channel_id == "emulator"
            and self.settings.allow_emulator
        ):
            return "EMP001", "emulator-user"
        raise AgentBackendError(
            "Your Microsoft Teams account is not mapped to an active ERPNext employee."
        )

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        if not self._is_personal_chat(turn_context):
            await turn_context.send_activity(
                "Please use a personal chat for private HR information."
            )
            return

        message = TurnContext.remove_recipient_mention(turn_context.activity).strip()
        if not message:
            await turn_context.send_activity(WELCOME)
            return

        try:
            employee_id, aad_object_id = self._resolve_employee(turn_context)
            tenant_id = getattr(turn_context.activity.conversation, "tenant_id", None) or ""
            if self.settings.microsoft_app_tenant_id and tenant_id:
                if tenant_id != self.settings.microsoft_app_tenant_id:
                    raise AgentBackendError("This organisation is not allowed to use the bot.")
            context = AgentUserContext(
                employee_id=employee_id,
                aad_object_id=aad_object_id,
                tenant_id=tenant_id,
                conversation_id=turn_context.activity.conversation.id or "",
                channel_id=turn_context.activity.channel_id or "",
            )
            reply = await self.agent.ask(message, context)
        except AgentBackendError as exc:
            reply = str(exc)

        await turn_context.send_activity(MessageFactory.text(reply))

