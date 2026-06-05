import pytest
from uuid import uuid4
from plasmaagent.agent.ollama_client import OllamaClient, AgentOrchestrator
from plasmaagent.memory.service import MemoryService
from plasmaagent.memory.models import MemoryType
from plasmaagent.core.database import get_database


class TestOllamaIntegration:
    async def test_ollama_health_check(self):
        client = OllamaClient()
        is_healthy = await client.health_check()
        assert is_healthy, "Ollama server not reachable"

    async def test_ollama_list_models(self):
        client = OllamaClient()
        models = await client.list_models()
        assert len(models) > 0, "No models available in Ollama"
        model_names = [m.get("name", "") for m in models]
        has_qwen = any("qwen2.5-coder" in name for name in model_names)
        assert has_qwen, f"qwen2.5-coder not found. Available: {model_names}"

    async def test_ollama_generate_simple(self):
        client = OllamaClient()
        response = await client.generate(
            prompt="Say 'OK' and nothing else.",
            temperature=0.1
        )
        assert len(response) > 0
        assert "OK" in response.upper() or "ok" in response.lower()

    async def test_ollama_chat_format(self):
        client = OllamaClient()
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Reply briefly."},
            {"role": "user", "content": "What is 2+2? Answer with just the number."}
        ]
        response = await client.chat(messages, temperature=0.1)
        assert len(response) > 0
        assert "4" in response


class TestMemoryWithOllamaIntegration:
    async def test_store_and_query_memory_with_ollama(self):
        db = get_database()
        await db.connect()
        ollama = OllamaClient()
        memory_id = None

        try:
            async with db.connection() as conn:
                mem_service = MemoryService(conn)

                memory = await mem_service.store_memory(
                    "The capital of Indonesia is Jakarta",
                    MemoryType.FACT,
                    user_id=None,
                    metadata={"source": "integration_test"}
                )
                memory_id = memory.id
                await conn.commit()

            async with db.connection() as conn:
                mem_service = MemoryService(conn)
                results = await mem_service.search_memories("capital")
                assert len(results) >= 1

                context = f"Known facts: {[m.content for m in results]}"
                prompt = f"Based on this context: '{context}', what is the capital of Indonesia? Answer in one word."

                response = await ollama.generate(prompt, temperature=0.1)
                assert len(response) > 0

            async with db.connection() as conn:
                mem_service = MemoryService(conn)
                await mem_service.delete_memory(memory_id)
                await conn.commit()
        finally:
            await db.disconnect()

    async def test_agent_orchestrator_end_to_end(self):
        orchestrator = AgentOrchestrator()
        result = await orchestrator.process_query("Hello, how are you?")

        assert "response" in result
        assert "query" in result
        assert "model" in result
        assert len(result["response"]) > 0
        assert result["query"] == "Hello, how are you?"
