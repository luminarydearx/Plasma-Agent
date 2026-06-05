import asyncio
import sys
from pathlib import Path

async def test_plasma_chat():
    """Test plasma chat dengan berbagai scenario"""
    from plasmaagent.agent.ollama_client import OllamaClient
    from plasmaagent.agent.orchestrator import AgentOrchestrator
    from plasmaagent.core.database import get_database
    from plasmaagent.core.schema import init_schema
    
    print("=" * 60)
    print("PLASMA INTERACTIVE TEST")
    print("=" * 60)
    
    db = get_database()
    await db.connect()
    async with db.connection() as conn:
        await init_schema(conn)
    print("✓ Database initialized")
    
    ollama = OllamaClient(model="qwen2.5-coder:7b-instruct-q4_K_M", base_url="http://localhost:11434")
    await ollama.set_model("qwen2.5-coder:7b-instruct-q4_K_M")
    print(f"✓ Model set: {ollama._model}")
    
    orchestrator = AgentOrchestrator(ollama=ollama)
    print(f"✓ Orchestrator created with {len(orchestrator._tools)} tools")
    
    test_cases = [
        {
            "name": "Simple greeting",
            "input": "Hai",
            "expect_tool": False,
        },
        {
            "name": "Create file",
            "input": "Buat file test_plasma.txt di Documents dengan isi 'Hello from PlasmaAgent'",
            "expect_tool": True,
        },
        {
            "name": "List directory",
            "input": "List isi folder Documents",
            "expect_tool": True,
        },
        {
            "name": "Run shell command",
            "input": "Jalankan command 'echo Hello World' di shell",
            "expect_tool": True,
        },
        {
            "name": "Open browser",
            "input": "Buka browser Edge dan search 'Python tutorial'",
            "expect_tool": True,
        },
    ]
    
    print("\n" + "=" * 60)
    print("TEST CASES")
    print("=" * 60)
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}] {test['name']}")
        print(f"Input: {test['input']}")
        print("-" * 60)
        
        try:
            response = await orchestrator.chat(test['input'])
            
            print(f"Response type: {type(response).__name__}")
            print(f"Has text: {bool(response.text)}")
            print(f"Has tool_calls: {bool(response.tool_calls)}")
            
            if response.tool_calls:
                print(f"Tool calls ({len(response.tool_calls)}):")
                for tc in response.tool_calls:
                    tool_name = tc.get("name") or tc.get("function", {}).get("name", "unknown")
                    print(f"  - {tool_name}")
            
            if response.text:
                print(f"Text preview: {response.text[:100]}...")
            
            if test['expect_tool'] and not response.tool_calls:
                print(f"⚠ Expected tool call but got none")
            elif not test['expect_tool'] and response.tool_calls:
                print(f"⚠ Did not expect tool call but got one")
            else:
                print("✓ Test passed")
                
        except Exception as e:
            print(f"✗ Error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_plasma_chat())
