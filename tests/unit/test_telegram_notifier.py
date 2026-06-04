import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx
from plasmaagent.observability.telegram_notifier import (
    TelegramConfig,
    TelegramMessage,
    TelegramNotifier,
)


class TestTelegramConfig:
    def test_valid_config(self):
        config = TelegramConfig(
            bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
            chat_id="123456789"
        )
        assert config.bot_token == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
        assert config.chat_id == "123456789"
        assert config.enabled is True
        assert config.timeout_seconds == 30
        assert config.max_retries == 3

    def test_custom_config(self):
        config = TelegramConfig(
            bot_token="test_token",
            chat_id="test_chat",
            enabled=False,
            timeout_seconds=60,
            max_retries=5
        )
        assert config.enabled is False
        assert config.timeout_seconds == 60
        assert config.max_retries == 5

    def test_invalid_bot_token_empty(self):
        with pytest.raises(Exception):
            TelegramConfig(bot_token="", chat_id="123")

    def test_invalid_chat_id_empty(self):
        with pytest.raises(Exception):
            TelegramConfig(bot_token="test", chat_id="")

    def test_invalid_timeout(self):
        with pytest.raises(Exception):
            TelegramConfig(bot_token="test", chat_id="123", timeout_seconds=0)

    def test_invalid_max_retries(self):
        with pytest.raises(Exception):
            TelegramConfig(bot_token="test", chat_id="123", max_retries=-1)


class TestTelegramMessage:
    def test_basic_message(self):
        msg = TelegramMessage(text="Hello World")
        assert msg.text == "Hello World"
        assert msg.parse_mode is None
        assert msg.disable_notification is False

    def test_message_with_parse_mode(self):
        msg = TelegramMessage(text="*Bold*", parse_mode="Markdown")
        assert msg.parse_mode == "Markdown"

    def test_message_with_html(self):
        msg = TelegramMessage(text="<b>Bold</b>", parse_mode="HTML")
        assert msg.parse_mode == "HTML"

    def test_message_with_markdown_v2(self):
        msg = TelegramMessage(text="*Bold*", parse_mode="MarkdownV2")
        assert msg.parse_mode == "MarkdownV2"

    def test_invalid_parse_mode(self):
        with pytest.raises(Exception):
            TelegramMessage(text="test", parse_mode="Invalid")

    def test_empty_text(self):
        with pytest.raises(Exception):
            TelegramMessage(text="")

    def test_text_too_long(self):
        with pytest.raises(Exception):
            TelegramMessage(text="x" * 5000)

    def test_disable_notification(self):
        msg = TelegramMessage(text="test", disable_notification=True)
        assert msg.disable_notification is True


class TestTelegramNotifier:
    @pytest.fixture
    def config(self):
        return TelegramConfig(
            bot_token="test_token",
            chat_id="123456789"
        )

    @pytest.fixture
    def notifier(self, config):
        return TelegramNotifier(config)

    def test_init(self, notifier, config):
        assert notifier.config == config
        assert notifier.base_url == "https://api.telegram.org/bottest_token"

    @pytest.mark.asyncio
    async def test_send_message_success(self, notifier):
        msg = TelegramMessage(text="Test message")

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await notifier.send_message(msg)
            assert result is True

    @pytest.mark.asyncio
    async def test_send_message_disabled(self, notifier):
        notifier.config.enabled = False
        msg = TelegramMessage(text="Test")

        result = await notifier.send_message(msg)
        assert result is False

    @pytest.mark.asyncio
    async def test_send_message_with_parse_mode(self, notifier):
        msg = TelegramMessage(text="*Bold*", parse_mode="Markdown")

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await notifier.send_message(msg)
            assert result is True

            call_args = mock_client.post.call_args
            assert call_args[1]["json"]["parse_mode"] == "Markdown"

    @pytest.mark.asyncio
    async def test_send_message_failure(self, notifier):
        msg = TelegramMessage(text="Test")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            result = await notifier.send_message(msg)
            assert result is False

    @pytest.mark.asyncio
    async def test_send_message_retry(self, notifier):
        notifier.config.max_retries = 2
        msg = TelegramMessage(text="Test")

        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(
                side_effect=[
                    httpx.HTTPError("Fail 1"),
                    httpx.HTTPError("Fail 2"),
                    mock_response
                ]
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await notifier.send_message(msg)
                assert result is True
                assert mock_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_send_message_max_retries_exceeded(self, notifier):
        notifier.config.max_retries = 1
        msg = TelegramMessage(text="Test")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(side_effect=httpx.HTTPError("Always fails"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await notifier.send_message(msg)
                assert result is False
                assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_send_alert(self, notifier):
        with patch.object(notifier, "send_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await notifier.send_alert(
                alert_name="High CPU",
                metric_name="cpu_usage",
                current_value=95.5,
                threshold=80.0,
                condition="greater_than"
            )

            assert result is True
            assert mock_send.called
            call_args = mock_send.call_args[0][0]
            assert "High CPU" in call_args.text
            assert "cpu_usage" in call_args.text
            assert "95.5" in call_args.text
            assert call_args.parse_mode == "Markdown"

    @pytest.mark.asyncio
    async def test_send_task_completion_success(self, notifier):
        with patch.object(notifier, "send_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await notifier.send_task_completion(
                task_name="Backup DB",
                task_id="abc-123",
                status="COMPLETED",
                duration_ms=5000
            )

            assert result is True
            call_args = mock_send.call_args[0][0]
            assert "✅" in call_args.text
            assert "Backup DB" in call_args.text
            assert "abc-123" in call_args.text

    @pytest.mark.asyncio
    async def test_send_task_completion_failed(self, notifier):
        with patch.object(notifier, "send_message", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            result = await notifier.send_task_completion(
                task_name="Backup DB",
                task_id="abc-123",
                status="FAILED",
                duration_ms=1000
            )

            assert result is True
            call_args = mock_send.call_args[0][0]
            assert "❌" in call_args.text
            assert "FAILED" in call_args.text

    @pytest.mark.asyncio
    async def test_test_connection_success(self, notifier):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": {"username": "TestBot"}
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            success, message = await notifier.test_connection()
            assert success is True
            assert "@TestBot" in message

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, notifier):
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Connection failed"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            success, message = await notifier.test_connection()
            assert success is False
            assert "HTTP error" in message

    @pytest.mark.asyncio
    async def test_test_connection_invalid_response(self, notifier):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": False}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            success, message = await notifier.test_connection()
            assert success is False
            assert "Invalid response" in message
