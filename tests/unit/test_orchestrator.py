import asyncio
from plasmaagent.agent.orchestrator import AgentOrchestrator
from plasmaagent.agent.ollama_client import OllamaClient

async def test():
    ollama = OllamaClient(model="qwen2.5-coder:7b-instruct-q4_K_M")
    orch = AgentOrchestrator(ollama=ollama)
    
    print("Testing orchestrator with model: qwen2.5-coder:7b-instruct-q4_K_M")
    resp = await orch.chat("hai")
    
    print(f"Text: {repr(resp.text)}")
    print(f"Tool calls: {resp.tool_calls}")
    print(f"Tool results: {resp.tool_results}")
    
    if resp.tool_calls:
        for tc in resp.tool_calls:
            tool_name = tc.get("name") or tc.get("function", {}).get("name", "unknown")
            tool_args = tc.get("args") or tc.get("function", {}).get("arguments", {})
            print(f"\nExecuting tool: {tool_name}")
            print(f"Args: {tool_args}")
            result = await orch.execute_tool(tool_name, tool_args)
            print(f"Result: {result}")

asyncio.run(test())
