import asyncio
import time
import sys

sys.path.insert(0, "src")

from plasmaagent.agent.ollama_client import OllamaClient
from plasmaagent.agent.orchestrator import AgentOrchestrator


async def test():
    ollama = OllamaClient(model="qwen2.5-coder:7b-instruct-q3_k_m")

    ok = await ollama.health_check()
    status = "OK" if ok else "FAIL"
    print(f"Ollama health: {status}")
    if not ok:
        return

    print("\n=== TEST 1: Simple Greeting ===")
    orch = AgentOrchestrator(ollama=ollama)
    start = time.time()
    resp = await orch.chat("halo, siapa kamu? jawab 1 kalimat saja")
    elapsed = time.time() - start
    text = resp.text[:200] if resp.text else "(empty)"
    print(f"Response: {text}")
    print(f"Time: {elapsed:.1f}s")
    print(f"Tool calls: {len(resp.tool_calls)}")


asyncio.run(test())
