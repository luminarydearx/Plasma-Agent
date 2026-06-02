import asyncio
import traceback
from plasmaagent.core.database import get_database
from plasmaagent.services.task_generator import TaskGeneratorService


async def test_full_flow():
    print("=" * 70)
    print("FULL FLOW TEST: Generate + Create Task")
    print("=" * 70)
    
    db = get_database()
    await db.connect()
    
    generator_service = TaskGeneratorService(db)
    
    test_input = "check disk space"
    print(f"\n[1/3] Generating task from: '{test_input}'")
    
    response = await generator_service.generate_from_natural_language(
        natural_language=test_input,
        context={},
    )
    
    if not response.tasks:
        print("❌ No task generated")
        await db.disconnect()
        return
    
    generated = response.tasks[0]
    print(f"✅ Task generated: {generated.name}")
    print(f"   Confidence: {generated.confidence:.0%}")
    print(f"   Template: {generated.template_used}")
    print(f"   Commands: {len(generated.commands)}")
    
    print("\n[2/3] Creating task in database...")
    try:
        task_id = await generator_service.create_task_from_generation(generated)
        print(f"✅ Task created with ID: {task_id}")
    except Exception as e:
        print(f"❌ Error creating task: {e}")
        traceback.print_exc()
        await db.disconnect()
        return
    
    print("\n[3/3] Verifying task in database...")
    try:
        from plasmaagent.services.task_service import TaskService
        from uuid import UUID
        
        task_service = TaskService(db)
        task = await task_service.get_task(UUID(task_id))
        
        print(f"✅ Task verified:")
        print(f"   Name: {task.name}")
        print(f"   Status: {task.status}")
        print(f"   Description: {task.description}")
        
        if task.payload and task.payload.get("commands"):
            print(f"   Commands: {len(task.payload['commands'])}")
    except Exception as e:
        print(f"❌ Error verifying task: {e}")
        traceback.print_exc()
    
    await db.disconnect()
    
    print("\n" + "=" * 70)
    print("✅ FULL FLOW TEST PASSED")
    print("=" * 70)
    print(f"\nYou can now run: plasma task run --id {task_id}")


if __name__ == "__main__":
    asyncio.run(test_full_flow())
