import asyncio
from plasmaagent.ai.providers import get_provider
from plasmaagent.ai.models import TaskGenerationRequest


def test_generation_only():
    print("=" * 70)
    print("GENERATION ONLY TEST (No Database)")
    print("=" * 70)
    
    provider = get_provider("rule_based")
    
    test_cases = [
        "backup database postgresql plasmaagent",
        "clean temp files in C:\\Temp",
        "check disk space",
        "git commit changes",
        "show system info",
    ]
    
    for i, test_input in enumerate(test_cases, 1):
        print(f"\n[{i}/{len(test_cases)}] Input: {test_input}")
        print("-" * 70)
        
        request = TaskGenerationRequest(
            natural_language=test_input,
            context={},
        )
        
        response = provider.generate_tasks(request)
        
        if response.tasks:
            task = response.tasks[0]
            print(f"✅ Name: {task.name}")
            print(f"   Template: {task.template_used}")
            print(f"   Confidence: {task.confidence:.0%}")
            print(f"   Commands ({len(task.commands)}):")
            for j, cmd in enumerate(task.commands, 1):
                print(f"     {j}. {cmd[:80]}")
        else:
            print("❌ No task generated")
        
        print(f"   Time: {response.total_time_ms:.2f}ms")
    
    print("\n" + "=" * 70)
    print("✅ GENERATION TEST COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    test_generation_only()
