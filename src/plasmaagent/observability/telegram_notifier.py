from typing import Optional
import httpx
import asyncio
from pydantic import BaseModel, Field


class TelegramConfig(BaseModel):
    bot_token: str = Field(..., min_length=1, max_length=100)
    chat_id: str = Field(..., min_length=1, max_length=50)
    enabled: bool = True
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    max_retries: int = Field(default=3, ge=0, le=10)


class TelegramMessage(BaseModel):
    text: str = Field(..., min_length=1, max_length=4096)
    parse_mode: Optional[str] = Field(default=None, pattern="^(HTML|Markdown|MarkdownV2)$")
    disable_notification: bool = False


class TelegramNotifier:
    def __init__(self, config: TelegramConfig):
        self.config = config
        self.base_url = f"https://api.telegram.org/bot{config.bot_token}"

    async def send_message(self, message: TelegramMessage) -> bool:
        if not self.config.enabled:
            return False

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.config.chat_id,
            "text": message.text,
            "disable_notification": message.disable_notification,
        }

        if message.parse_mode:
            payload["parse_mode"] = message.parse_mode

        for attempt in range(self.config.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    result = response.json()
                    return result.get("ok", False)
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                if attempt == self.config.max_retries:
                    return False
                await asyncio.sleep(2 ** attempt)

        return False

    async def send_alert(self, alert_name: str, metric_name: str, current_value: float, threshold: float, condition: str) -> bool:
        text = (
            f"🚨 *Alert Triggered*\n\n"
            f"*Alert:* {alert_name}\n"
            f"*Metric:* {metric_name}\n"
            f"*Current Value:* {current_value}\n"
            f"*Threshold:* {threshold}\n"
            f"*Condition:* {condition}\n\n"
            f"Time: {asyncio.get_event_loop().time():.0f}"
        )

        message = TelegramMessage(text=text, parse_mode="Markdown")
        return await self.send_message(message)

    async def send_task_completion(self, task_name: str, task_id: str, status: str, duration_ms: int) -> bool:
        emoji = "✅" if status == "COMPLETED" else "❌"
        text = (
            f"{emoji} *Task {status}*\n\n"
            f"*Name:* {task_name}\n"
            f"*ID:* `{task_id}`\n"
            f"*Duration:* {duration_ms}ms"
        )

        message = TelegramMessage(text=text, parse_mode="Markdown")
        return await self.send_message(message)

    async def test_connection(self) -> tuple[bool, str]:
        try:
            url = f"{self.base_url}/getMe"
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                response = await client.get(url)
                response.raise_for_status()
                result = response.json()
                if result.get("ok"):
                    bot_info = result.get("result", {})
                    bot_name = bot_info.get("username", "Unknown")
                    return True, f"Connected to bot: @{bot_name}"
                return False, "Invalid response from Telegram API"
        except httpx.HTTPError as e:
            return False, f"HTTP error: {str(e)}"
        except Exception as e:
            return False, f"Error: {str(e)}"
