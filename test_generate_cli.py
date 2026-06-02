import asyncio
from plasmaagent.core.database import get_database
from plasmaagent.services.task_generator import TaskGeneratorService
from plasmaagent.core.asyncio_compat import run_async

async def test_generate_and_create():
    print("[1/4] Connecting to database...")
    db = get_database()
    await db.connect()
    print("✅ Connected")
    
    print("[2/4] Creating TaskGeneratorService...")
    service = TaskGeneratorService(db)
    print("✅ Service created")
    
    print("[3/4] Generating task from natural language...")
    response = await service.generate_from_natural_language(
        natural_language="check disk space",
        provider_name="rule_based",
        context={},
    )
    print(f"✅ Generated {len(response.tasks)} task(s)")
    
    if response.tasks:
        print("[4/4] Creating task in database...")
        task_id = await service.create_task_from_generation(response.tasks[0])
        print(f"✅ Task created with ID: {task_id}")
    else:
        print("❌ No tasks generated")
    
    await db.disconnect()
    print("✅ Disconnected")

if __name__ == "__main__":
    run_async(test_generate_and_create())
