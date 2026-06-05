import asyncio
import sys

async def test_plasma_basic():
    """Test basic plasma functionality tanpa Ollama API call"""
    print("=" * 60)
    print("PLASMA QUICK TEST")
    print("=" * 60)
    
    try:
        from plasmaagent.core.database import get_database
        from plasmaagent.core.schema import init_schema
        print("✓ Imports successful")
        
        db = get_database()
        await db.connect()
        async with db.connection() as conn:
            await init_schema(conn)
        print("✓ Database initialized")
        
        from plasmaagent.agent.ollama_client import OllamaClient
        from plasmaagent.agent.orchestrator import AgentOrchestrator, AgentResponse
        print("✓ Agent modules loaded")
        
        ollama = OllamaClient(model="test-model", base_url="http://localhost:11434")
        await ollama.set_model("test-model")
        print(f"✓ OllamaClient created (model: {ollama._model})")
        
        orchestrator = AgentOrchestrator(ollama=ollama)
        print(f"✓ Orchestrator created with {len(orchestrator._tools)} tools")
        
        test_response = AgentResponse(text="Test response", tool_calls=[], tool_results=[])
        print(f"✓ AgentResponse created (text: {test_response.text})")
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_plasma_basic())
    sys.exit(0 if result else 1)
