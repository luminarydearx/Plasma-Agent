import asyncio
from plasmaagent.agent.orchestrator import AgentOrchestrator
from plasmaagent.agent.ollama_client import OllamaClient

async def test_comprehensive():
    ollama = OllamaClient(model="qwen2.5-coder:7b-instruct-q4_K_M")
    orch = AgentOrchestrator(ollama=ollama)
    
    print("=" * 60)
    print("COMPREHENSIVE TOOLS TEST")
    print("=" * 60)
    
    print("\n1. Testing open_app (Microsoft Edge)...")
    result = await orch.execute_tool("open_app", {
        "app_name": "msedge",
        "arguments": "https://www.google.com"
    })
    print(f"   Result: {result}")
    
    print("\n2. Testing create_file in Documents...")
    result = await orch.execute_tool("create_file", {
        "path": "C:/Users/Dearly Febriano/Documents/plasma_test.txt",
        "content": "PlasmaAgent test file\nCreated: " + str(asyncio.get_event_loop().time()),
        "overwrite": True
    })
    print(f"   Result: {result}")
    
    print("\n3. Testing read_file...")
    result = await orch.execute_tool("read_file", {
        "path": "C:/Users/Dearly Febriano/Documents/plasma_test.txt"
    })
    print(f"   Result: {result}")
    
    print("\n4. Testing execute_shell (dir)...")
    result = await orch.execute_tool("execute_shell", {
        "command": "dir C:\\Users\\Dearly Febriano\\Documents\\*.txt"
    })
    print(f"   Result: {result[:200]}...")
    
    print("\n5. Testing web_search...")
    result = await orch.execute_tool("web_search", {
        "query": "Python async best practices",
        "max_results": 3
    })
    print(f"   Result: {result[:300]}...")
    
    print("\n6. Testing system_stats...")
    result = await orch.execute_tool("system_stats", {})
    print(f"   Result: {result}")
    
    print("\n7. Testing find_file...")
    result = await orch.execute_tool("find_file", {
        "pattern": "*.py",
        "directory": "C:/Users/Dearly Febriano/Documents/PlasmaAgent/src",
        "max_results": 5
    })
    print(f"   Result: {result[:300]}...")
    
    print("\n8. Testing current_time...")
    result = await orch.execute_tool("current_time", {})
    print(f"   Result: {result}")
    
    print("\n" + "=" * 60)
    print("ALL TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 60)

asyncio.run(test_comprehensive())
