import re
from pathlib import Path

file_path = Path(r"C:\Users\Dearly Febriano\Documents\PlasmaAgent\src\plasmaagent\agent\tools.py")
content = file_path.read_text(encoding="utf-8")

old_code = '''async def clipboard_get() -> ToolResult:
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["powershell", "-Command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=5,
            )
            return ToolResult(True, result.stdout.strip(), {"content": result.stdout.strip()})
        else:
            result = subprocess.run(["xclip", "-selection", "clipboard", "-o"], capture_output=True, text=True, timeout=5)
            return ToolResult(True, result.stdout.strip(), {"content": result.stdout.strip()})
    except Exception as e:
        return ToolResult(False, f"Clipboard read failed: {e}")'''

new_code = '''async def clipboard_get() -> ToolResult:
    try:
        if sys.platform == "win32":
            result = subprocess.run(
                ["powershell", "-Command", "Get-Clipboard"],
                capture_output=True, text=True, timeout=5,
            )
            content = (result.stdout or "").strip()
            if not content:
                return ToolResult(True, "(clipboard is empty)", {"content": ""})
            return ToolResult(True, content, {"content": content})
        else:
            result = subprocess.run(["xclip", "-selection", "clipboard", "-o"], capture_output=True, text=True, timeout=5)
            content = (result.stdout or "").strip()
            if not content:
                return ToolResult(True, "(clipboard is empty)", {"content": ""})
            return ToolResult(True, content, {"content": content})
    except Exception as e:
        return ToolResult(False, f"Clipboard read failed: {e}")'''

content = content.replace(old_code, new_code)
file_path.write_text(content, encoding="utf-8")
print("✓ Fixed clipboard_get function")
