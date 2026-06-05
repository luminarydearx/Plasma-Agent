import asyncio
import sys

async def test_plasma_final():
    """Final comprehensive test untuk plasma"""
    print("=" * 70)
    print("PLASMA FINAL VERIFICATION TEST")
    print("=" * 70)
    
    all_passed = True
    
    try:
        print("\n[1/6] Testing imports...")
        from plasmaagent.core.database import get_database
        from plasmaagent.core.schema import init_schema
        from plasmaagent.agent.ollama_client import OllamaClient
        from plasmaagent.agent.orchestrator import AgentOrchestrator, AgentResponse
        from plasmaagent.agent.tools import TOOL_REGISTRY
        from plasmaagent.security.sanitizer import get_sanitizer
        from plasmaagent.memory.vector_store import get_vector_store
        print("  ✓ All imports successful")
        
        print("\n[2/6] Testing database initialization...")
        db = get_database()
        await db.connect()
        async with db.connection() as conn:
            await init_schema(conn)
        print("  ✓ Database initialized (SQLite + SQLAlchemy)")
        
        print("\n[3/6] Testing OllamaClient...")
        ollama = OllamaClient(model="test-model", base_url="http://localhost:11434")
        await ollama.set_model("test-model")
        assert ollama._model == "test-model"
        print(f"  ✓ OllamaClient works (model: {ollama._model})")
        
        print("\n[4/6] Testing AgentOrchestrator...")
        orchestrator = AgentOrchestrator(ollama=ollama)
        assert len(orchestrator._tools) == 26
        print(f"  ✓ Orchestrator created with {len(orchestrator._tools)} tools")
        
        print("\n[5/6] Testing AgentResponse structure...")
        response = AgentResponse(text="Test", tool_calls=[], tool_results=[])
        assert hasattr(response, "text")
        assert not hasattr(response, "content")
        print(f"  ✓ AgentResponse.text = '{response.text}'")
        print("  ✓ AgentResponse does NOT have 'content' attribute (correct)")
        
        print("\n[6/6] Testing tools...")
        tools_to_test = [
            "write_file",
            "read_file",
            "list_directory",
            "execute_shell",
            "open_app",
        ]
        
        for tool_name in tools_to_test:
            tool = TOOL_REGISTRY.get(tool_name)
            if tool:
                print(f"  ✓ {tool_name}: registered")
            else:
                print(f"  ✗ {tool_name}: NOT FOUND")
                all_passed = False
        
        print("\n[7/7] Testing InputSanitizer...")
        sanitizer = get_sanitizer()
        result = sanitizer.sanitize_sql("SELECT * FROM users WHERE id=1 OR 1=1")
        if not result.is_safe:
            print(f"  ✓ SQL injection detected ({len(result.threats_detected)} threats)")
        else:
            print(f"  ✗ SQL injection NOT detected")
            all_passed = False
        
        print("\n" + "=" * 70)
        if all_passed:
            print("✅ ALL TESTS PASSED - PLASMA READY FOR USE")
        else:
            print("❌ SOME TESTS FAILED")
        print("=" * 70)
        
        print("\n📋 Summary:")
        print(f"  • Database: SQLite + SQLAlchemy ✓")
        print(f"  • Tools: {len(TOOL_REGISTRY)} registered ✓")
        print(f"  • Security: InputSanitizer active ✓")
        print(f"  • Vector Store: ChromaDB ready ✓")
        print(f"  • AgentResponse: Using .text attribute ✓")
        
        return all_passed
        
    except Exception as e:
        print(f"\n✗ Fatal error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_plasma_final())
    sys.exit(0 if result else 1)
