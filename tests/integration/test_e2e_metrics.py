import asyncio
from decimal import Decimal

from plasmaagent.core.database import get_database
from plasmaagent.services.task_generator import TaskGeneratorService
from plasmaagent.services.template_metrics_service import TemplateMetricsService


async def test_end_to_end():
    db = get_database()
    await db.connect()

    try:
        generator = TaskGeneratorService(db)
        metrics_service = TemplateMetricsService(db)

        test_cases = [
            "backup database postgresql plasmaagent",
            "backup mysql database mydb",
            "cleanup old files in C:\\Temp",
            "check disk space on D:",
            "git commit changes",
            "show system info",
        ]

        print("=" * 60)
        print("END-TO-END TEST: Generate → Record Metrics → Verify")
        print("=" * 60)

        for i, input_text in enumerate(test_cases, 1):
            print(f"\n[{i}/6] Generating: '{input_text}'")
            
            response = await generator.generate_from_natural_language(input_text)
            
            if response.tasks:
                task = response.tasks[0]
                print(f"  Template: {task.template_used}")
                print(f"  Confidence: {task.confidence:.0%}")
                print(f"  Time: {response.total_time_ms:.2f}ms")
                
                metric = await metrics_service.get_by_name(task.template_used)
                if metric:
                    print(f"  [DB] Usage count: {metric.usage_count}")
                    print(f"  [DB] Avg confidence: {metric.avg_confidence}")
                else:
                    print(f"  [DB] Metric NOT FOUND!")
            else:
                print(f"  No match found")

        print("\n" + "=" * 60)
        print("AGGREGATE STATS")
        print("=" * 60)
        
        stats = await metrics_service.get_aggregate_stats()
        print(f"Total templates: {stats['total_templates']}")
        print(f"Total usage: {stats['total_usage']}")
        print(f"Total success: {stats['total_success']}")
        print(f"Global avg confidence: {stats['global_avg_confidence']}")
        print(f"Avg generation time: {stats['avg_generation_time_ms']}ms")

        print("\n" + "=" * 60)
        print("TOP TEMPLATES BY USAGE")
        print("=" * 60)
        
        top_templates = await metrics_service.get_top_by_usage(limit=5)
        for t in top_templates:
            success_rate = t.success_count / max(t.usage_count, 1)
            print(f"  {t.template_name}: {t.usage_count} uses, {success_rate:.0%} success")

        print("\n" + "=" * 60)
        print("END-TO-END TEST: COMPLETE")
        print("=" * 60)

    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(test_end_to_end())
