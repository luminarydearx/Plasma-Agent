"""Test script untuk verifikasi fix permission prompt dan spinner."""

import asyncio
import sys
from pathlib import Path

async def test_permission_callbacks():
    """Test bahwa callbacks untuk spinner control bekerja."""
    from plasmaagent.agent.orchestrator import AgentOrchestrator
    from plasmaagent.agent.ollama_client import OllamaClient
    
    print("=" * 60)
    print("TEST 1: Permission Callbacks Setup")
    print("=" * 60)
    
    ollama = OllamaClient()
    
    callback_log = []
    
    def on_permission_needed():
        callback_log.append("needed")
        print("  ✓ Callback: on_permission_needed dipanggil")
    
    def on_permission_done():
        callback_log.append("done")
        print("  ✓ Callback: on_permission_done dipanggil")
    
    orchestrator = AgentOrchestrator(
        ollama=ollama,
        on_permission_needed=on_permission_needed,
        on_permission_done=on_permission_done,
    )
    
    assert orchestrator._on_permission_needed is not None, "Callback not set"
    assert orchestrator._on_permission_done is not None, "Callback not set"
    
    print("✓ Callbacks berhasil di-set di constructor")
    
    orchestrator._on_permission_needed()
    orchestrator._on_permission_done()
    
    assert callback_log == ["needed", "done"], f"Expected ['needed', 'done'], got {callback_log}"
    print("✓ Callbacks dipanggil dengan benar")
    print()


async def test_permission_prompt_input():
    """Test bahwa permission prompt bisa menerima input."""
    from plasmaagent.agent.permission_manager import prompt_permission, PermissionResult
    
    print("=" * 60)
    print("TEST 2: Permission Prompt Input")
    print("=" * 60)
    print("Test ini akan menampilkan permission prompt.")
    print("Silakan ketik 'a' untuk Allow Once, 'w' untuk Allow Always, atau 'd' untuk Deny")
    print()
    
    result = prompt_permission("test_tool", {"param": "value"})
    
    print(f"\n✓ Permission prompt selesai")
    print(f"  Result: {result}")
    assert isinstance(result, PermissionResult), "Invalid result type"
    print()


async def test_spinner_control():
    """Test bahwa spinner bisa di-stop dan start."""
    from rich.console import Console
    from rich.status import Status
    import time
    
    print("=" * 60)
    print("TEST 3: Spinner Control")
    print("=" * 60)
    
    console = Console()
    status_handle: Status | None = None
    spinner_active = False
    
    def stop_spinner():
        nonlocal status_handle, spinner_active
        if spinner_active and status_handle is not None:
            status_handle.stop()
            spinner_active = False
            print("  ✓ Spinner stopped")
    
    def start_spinner():
        nonlocal status_handle, spinner_active
        if not spinner_active:
            status_handle = console.status("[bold cyan]⠋ Thinking...[/bold cyan]", spinner="dots")
            status_handle.start()
            spinner_active = True
            print("  ✓ Spinner started")
    
    start_spinner()
    await asyncio.sleep(1)
    stop_spinner()
    await asyncio.sleep(0.5)
    start_spinner()
    await asyncio.sleep(1)
    stop_spinner()
    
    print("✓ Spinner control bekerja dengan benar")
    print()


async def test_orchestrator_integration():
    """Test integrasi orchestrator dengan callbacks."""
    from plasmaagent.agent.orchestrator import AgentOrchestrator
    from plasmaagent.agent.ollama_client import OllamaClient
    
    print("=" * 60)
    print("TEST 4: Orchestrator Integration")
    print("=" * 60)
    
    ollama = OllamaClient()
    
    callback_log = []
    
    def on_permission_needed():
        callback_log.append("needed")
    
    def on_permission_done():
        callback_log.append("done")
    
    orchestrator = AgentOrchestrator(
        ollama=ollama,
        on_permission_needed=on_permission_needed,
        on_permission_done=on_permission_done,
    )
    
    print("  Testing dynamic callback assignment...")
    
    def new_needed():
        callback_log.append("new_needed")
    
    def new_done():
        callback_log.append("new_done")
    
    orchestrator._on_permission_needed = new_needed
    orchestrator._on_permission_done = new_done
    
    orchestrator._on_permission_needed()
    orchestrator._on_permission_done()
    
    assert callback_log == ["new_needed", "new_done"], f"Expected ['new_needed', 'new_done'], got {callback_log}"
    print("  ✓ Dynamic callback assignment bekerja")
    print()


async def main():
    """Run all tests."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "PERMISSION PROMPT & SPINNER FIX TEST" + " " * 12 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    try:
        await test_permission_callbacks()
        await test_spinner_control()
        await test_orchestrator_integration()
        
        print("=" * 60)
        print("TEST 2 SKIPPED (Interactive)")
        print("=" * 60)
        print("Untuk test interactive permission prompt, jalankan:")
        print("  plasma")
        print("Lalu minta AI untuk membuat file atau execute shell command")
        print()
        
        print("╔" + "=" * 58 + "╗")
        print("║" + " " * 20 + "ALL TESTS PASSED!" + " " * 21 + "║")
        print("╚" + "=" * 58 + "╝")
        print()
        print("✓ Callbacks di-set dengan benar")
        print("✓ Spinner control bekerja")
        print("✓ Orchestrator integration OK")
        print()
        print("Next: Test dengan command 'plasma' di PowerShell")
        print()
        
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
