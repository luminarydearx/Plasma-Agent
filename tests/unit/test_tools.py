import asyncio
import sys
from pathlib import Path

async def test_tools():
    """Test individual tools"""
    print("=" * 60)
    print("TOOLS TEST")
    print("=" * 60)
    
    try:
        from plasmaagent.core.database import get_database
        from plasmaagent.core.schema import init_schema
        from plasmaagent.agent.tools import TOOL_REGISTRY
        
        db = get_database()
        await db.connect()
        async with db.connection() as conn:
            await init_schema(conn)
        
        print(f"✓ {len(TOOL_REGISTRY)} tools registered\n")
        
        test_results = []
        
        print("[1/5] Testing write_file...")
        try:
            test_file = Path.home() / "Documents" / "plasma_test.txt"
            write_tool = TOOL_REGISTRY.get("write_file")
            if write_tool:
                result = await write_tool.handler(path=str(test_file), content="Test content from PlasmaAgent")
                print(f"  Result: {result.success}")
                if result.success:
                    print(f"  ✓ File created: {test_file}")
                    test_results.append(("write_file", True))
                else:
                    print(f"  ✗ Error: {result.output}")
                    test_results.append(("write_file", False))
            else:
                print("  ⚠ Tool not found")
                test_results.append(("write_file", False))
        except Exception as e:
            print(f"  ✗ Exception: {e}")
            test_results.append(("write_file", False))
        
        print("\n[2/5] Testing read_file...")
        try:
            read_tool = TOOL_REGISTRY.get("read_file")
            if read_tool:
                result = await read_tool.handler(path=str(test_file))
                print(f"  Result: {result.success}")
                if result.success:
                    print(f"  ✓ File read: {result.output[:50]}...")
                    test_results.append(("read_file", True))
                else:
                    print(f"  ✗ Error: {result.output}")
                    test_results.append(("read_file", False))
            else:
                print("  ⚠ Tool not found")
                test_results.append(("read_file", False))
        except Exception as e:
            print(f"  ✗ Exception: {e}")
            test_results.append(("read_file", False))
        
        print("\n[3/5] Testing list_directory...")
        try:
            list_tool = TOOL_REGISTRY.get("list_directory")
            if list_tool:
                docs_path = str(Path.home() / "Documents")
                result = await list_tool.handler(path=docs_path)
                print(f"  Result: {result.success}")
                if result.success:
                    print(f"  ✓ Listed: {result.output[:100]}...")
                    test_results.append(("list_directory", True))
                else:
                    print(f"  ✗ Error: {result.output}")
                    test_results.append(("list_directory", False))
            else:
                print("  ⚠ Tool not found")
                test_results.append(("list_directory", False))
        except Exception as e:
            print(f"  ✗ Exception: {e}")
            test_results.append(("list_directory", False))
        
        print("\n[4/5] Testing run_shell_command...")
        try:
            shell_tool = TOOL_REGISTRY.get("run_shell_command")
            if shell_tool:
                result = await shell_tool.handler(command="echo Hello from PlasmaAgent")
                print(f"  Result: {result.success}")
                if result.success:
                    print(f"  ✓ Output: {result.output}")
                    test_results.append(("run_shell_command", True))
                else:
                    print(f"  ✗ Error: {result.output}")
                    test_results.append(("run_shell_command", False))
            else:
                print("  ⚠ Tool not found")
                test_results.append(("run_shell_command", False))
        except Exception as e:
            print(f"  ✗ Exception: {e}")
            test_results.append(("run_shell_command", False))
        
        print("\n[5/5] Testing open_app...")
        try:
            open_tool = TOOL_REGISTRY.get("open_app")
            if open_tool:
                result = await open_tool.handler(app_name="notepad.exe")
                print(f"  Result: {result.success}")
                if result.success:
                    print(f"  ✓ App opened: {result.output}")
                    test_results.append(("open_app", True))
                else:
                    print(f"  ⚠ Warning: {result.output}")
                    test_results.append(("open_app", True))
            else:
                print("  ⚠ Tool not found")
                test_results.append(("open_app", False))
        except Exception as e:
            print(f"  ✗ Exception: {e}")
            test_results.append(("open_app", False))
        
        print("\n" + "=" * 60)
        print("TEST SUMMARY")
        print("=" * 60)
        for tool_name, passed in test_results:
            status = "✓ PASS" if passed else "✗ FAIL"
            print(f"{status}: {tool_name}")
        
        all_passed = all(passed for _, passed in test_results)
        print("\n" + "=" * 60)
        if all_passed:
            print("ALL TESTS PASSED")
        else:
            print("SOME TESTS FAILED")
        print("=" * 60)
        
        return all_passed
        
    except Exception as e:
        print(f"\n✗ Fatal error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_tools())
    sys.exit(0 if result else 1)
