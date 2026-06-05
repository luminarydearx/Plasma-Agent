import asyncio
from plasmaagent.agent.ollama_client import OllamaClient


async def test():
    client = OllamaClient()
    print("=== OLLAMA LIVE TEST ===\n")

    # Test 1: Health check
    print("[1] Health Check...")
    healthy = await client.health_check()
    status = "✅ OK" if healthy else "❌ FAIL"
    print(f"    Status: {status}\n")

    if not healthy:
        print("❌ Ollama tidak running. Start dengan: ollama serve")
        return

    # Test 2: List models
    print("[2] List Models...")
    models = await client.list_models()
    print(f"    Found {len(models)} model(s):")
    for m in models:
        size_gb = m.get("size", 0) / 1e9
        print(f"      - {m['name']} ({size_gb:.1f} GB)")
    print()

    # Test 3: Simple generate
    print("[3] Generate Response...")
    response = await client.generate(
        prompt="Say hello in 5 words",
        system="You are PlasmaAgent, a helpful AI assistant.",
        temperature=0.3
    )
    print(f"    Response: {response[:100]}...\n")

    # Test 4: Chat with context
    print("[4] Chat with Context...")
    messages = [
        {"role": "user", "content": "My name is Dearly"},
        {"role": "assistant", "content": "Hello Dearly! Nice to meet you."},
        {"role": "user", "content": "What is my name?"}
    ]
    chat_response = await client.chat(messages, temperature=0.3)
    print(f"    Response: {chat_response}\n")

    # Test 5: Code generation
    print("[5] Code Generation Test...")
    code_response = await client.generate(
        prompt="Write a Python function to calculate fibonacci numbers. Only code, no explanation.",
        system="You are a senior Python engineer. Write clean, typed code.",
        temperature=0.2
    )
    print(f"    Response (first 300 chars):\n{code_response[:300]}...\n")

    # Test 6: Tool awareness
    print("[6] Tool Awareness Test...")
    tool_response = await client.generate(
        prompt="I need to remember that my favorite color is blue. What would you do?",
        system="""You are PlasmaAgent with memory capabilities.
Available tools:
- store_memory(content, type, metadata): Save information to long-term memory
- search_memories(query): Search for relevant memories
- get_conversation_context(): Get recent conversation history

When appropriate, mention which tool you would use.""",
        temperature=0.3
    )
    print(f"    Response: {tool_response[:400]}...\n")

    print("=== ALL TESTS COMPLETE ===")


if __name__ == "__main__":
    asyncio.run(test())
