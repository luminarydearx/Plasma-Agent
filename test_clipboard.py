import asyncio
from plasmaagent.agent.orchestrator import AgentOrchestrator
from plasmaagent.agent.ollama_client import OllamaClient

async def test_clipboard():
    ollama = OllamaClient(model="qwen2.5-coder:7b-instruct-q4_K_M")
    orch = AgentOrchestrator(ollama=ollama)
    
    print("Testing clipboard_set...")
    result = await orch.execute_tool("clipboard_set", {"content": "Test from PlasmaAgent"})
    print(f"Result: {result}\n")
    
    print("Testing clipboard_get...")
    result = await orch.execute_tool("clipboard_get", {})
    print(f"Result: {result}\n")

asyncio.run(test_clipboard())
