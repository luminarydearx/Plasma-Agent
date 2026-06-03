import asyncio
import sys
import time
from decimal import Decimal

if sys.platform == "win32":
    import selectors
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, "src")

from plasmaagent.core.database import Database
from plasmaagent.services.template_metrics_service import TemplateMetricsService


async def main():
    db = Database()
    await db.connect()
    service = TemplateMetricsService(db)
    
    name = f"rolling_debug_{int(time.time() * 1000000)}"
    print(f"Test name: {name}")
    
    try:
        print("Step 1: First record_usage (0.95)")
        m1 = await service.record_usage(
            template_name=name, pattern=r"precision",
            confidence=Decimal("0.95"), generation_time_ms=10, success=True,
        )
        print(f"  After 1: usage={m1.usage_count}, avg={m1.avg_confidence}")
        
        for i in range(9):
            print(f"Step {i+2}: record_usage (0.85)")
            m = await service.record_usage(
                template_name=name, pattern=r"precision",
                confidence=Decimal("0.85"), generation_time_ms=10, success=True,
            )
            print(f"  After {i+2}: usage={m.usage_count}, avg={m.avg_confidence}")
        
        print("\nFinal fetch:")
        metric = await service.get_by_name(name)
        if metric is None:
            print("  ERROR: metric is None!")
        else:
            print(f"  usage_count = {metric.usage_count}")
            print(f"  avg_confidence = {metric.avg_confidence}")
            print(f"  type = {type(metric.avg_confidence)}")
            
            expected = (Decimal("0.95") + (Decimal("0.85") * Decimal("9"))) / Decimal("10")
            print(f"  expected = {expected}")
            print(f"  diff = {abs(metric.avg_confidence - expected)}")
        
        await service.delete_by_name(name)
        print("\nTest completed successfully")
    except Exception as e:
        print(f"EXCEPTION: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
