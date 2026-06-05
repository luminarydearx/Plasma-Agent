import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from plasmaagent.agent.ollama_client import OllamaClient, AgentOrchestrator


class TestOllamaClient:
    async def test_generate_returns_response(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Hello world"}
        mock_response.raise_for_status = MagicMock()

        with patch("plasmaagent.agent.ollama_client.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            client = OllamaClient()
            result = await client.generate("test prompt")

            assert result == "Hello world"

    async def test_chat_returns_content(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "message": {"role": "assistant", "content": "Chat response"}
        }
        mock_response.raise_for_status = MagicMock()

        with patch("plasmaagent.agent.ollama_client.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            client = OllamaClient()
            messages = [{"role": "user", "content": "Hi"}]
            result = await client.chat(messages)

            assert result == "Chat response"

    async def test_health_check_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("plasmaagent.agent.ollama_client.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            client = OllamaClient()
            result = await client.health_check()

            assert result is True

    async def test_health_check_failure(self):
        with patch("plasmaagent.agent.ollama_client.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value = mock_client

            client = OllamaClient()
            result = await client.health_check()

            assert result is False


class TestAgentOrchestrator:
    async def test_process_query(self):
        mock_ollama = AsyncMock(spec=OllamaClient)
        mock_ollama.generate = AsyncMock(return_value="Agent response")
        mock_ollama._model = "test-model"

        orchestrator = AgentOrchestrator(ollama=mock_ollama)
        result = await orchestrator.process_query("Hello agent")

        assert result["response"] == "Agent response"
        assert result["query"] == "Hello agent"
        assert result["model"] == "test-model"
        mock_ollama.generate.assert_called_once()
