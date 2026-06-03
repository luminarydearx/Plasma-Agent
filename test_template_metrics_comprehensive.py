import asyncio
from decimal import Decimal
from uuid import uuid4

from plasmaagent.core.database import get_database
from plasmaagent.services.template_metrics_service import TemplateMetricsService
from plasmaagent.models.template_metrics import TemplateMetricsCreate, TemplateMetricsUpdate


async def test_comprehensive():
    print("=== Template Metrics Service - Comprehensive Test ===\n")
    
    db = get_database()
    await db.connect()
    service = TemplateMetricsService(db)
    
    created_ids = []
    
    try:
        print("[Test 1] Create metric (backup_database)...")
        data1 = TemplateMetricsCreate(
            template_name="backup_database",
            pattern=r"backup postgresql (\w+)",
            usage_count=5,
            success_count=4,
            failure_count=1,
            avg_confidence=Decimal("0.9200"),
            total_generation_time_ms=150,
        )
        metric1 = await service.create_metric(data1)
        created_ids.append(metric1.id)
        print(f"  OK Created: {metric1.template_name} (ID: {metric1.id})")
        
        print("[Test 2] Create metric (cleanup_files)...")
        data2 = TemplateMetricsCreate(
            template_name="cleanup_files",
            pattern=r"clean temp files in (.+)",
            usage_count=10,
            success_count=9,
            failure_count=1,
            avg_confidence=Decimal("0.8800"),
            total_generation_time_ms=200,
        )
        metric2 = await service.create_metric(data2)
        created_ids.append(metric2.id)
        print(f"  OK Created: {metric2.template_name} (ID: {metric2.id})")
        
        print("[Test 3] Duplicate create (should fail with unique constraint)...")
        try:
            await service.create_metric(data1)
            print("  FAIL Should have raised error")
        except Exception as e:
            print(f"  OK Correctly rejected: {type(e).__name__}")
        
        print("[Test 4] Get by name...")
        found = await service.get_by_name("backup_database")
        assert found is not None
        assert found.template_name == "backup_database"
        print(f"  OK Found: {found.template_name} (usage: {found.usage_count})")
        
        print("[Test 5] Get by name (non-existent)...")
        not_found = await service.get_by_name("non_existent_template")
        assert not_found is None
        print("  OK Correctly returned None")
        
        print("[Test 6] Get by name and pattern...")
        found2 = await service.get_by_name_and_pattern(
            "backup_database", r"backup postgresql (\w+)"
        )
        assert found2 is not None
        print(f"  OK Found: {found2.template_name} with pattern")
        
        print("[Test 7] Get by ID...")
        found3 = await service.get_by_id(metric1.id)
        assert found3 is not None
        assert found3.id == metric1.id
        print(f"  OK Found by ID: {found3.template_name}")
        
        print("[Test 8] Record usage (success)...")
        updated = await service.record_usage(
            template_name="backup_database",
            pattern=r"backup postgresql (\w+)",
            confidence=Decimal("0.9500"),
            generation_time_ms=120,
            success=True,
        )
        assert updated.usage_count == 6
        assert updated.success_count == 5
        print(f"  OK Usage: {updated.usage_count}, Success: {updated.success_count}")
        
        print("[Test 9] Record usage (failure)...")
        updated2 = await service.record_usage(
            template_name="backup_database",
            pattern=r"backup postgresql (\w+)",
            confidence=Decimal("0.8800"),
            generation_time_ms=200,
            success=False,
        )
        assert updated2.usage_count == 7
        assert updated2.failure_count == 2
        print(f"  OK Usage: {updated2.usage_count}, Failure: {updated2.failure_count}")
        
        print("[Test 10] Record usage (new pattern - should create)...")
        updated3 = await service.record_usage(
            template_name="git_operations",
            pattern=r"git commit (.+)",
            confidence=Decimal("0.8500"),
            generation_time_ms=50,
            success=True,
        )
        assert updated3.usage_count == 1
        print(f"  OK Created new: {updated3.template_name} (usage: {updated3.usage_count})")
        created_ids.append(updated3.id)
        
        print("[Test 11] Update metric...")
        update_data = TemplateMetricsUpdate(
            usage_count=100,
            success_count=95,
            avg_confidence=Decimal("0.9500"),
        )
        updated4 = await service.update_metric(metric1.id, update_data)
        assert updated4 is not None
        assert updated4.usage_count == 100
        print(f"  OK Updated: usage={updated4.usage_count}, confidence={updated4.avg_confidence}")
        
        print("[Test 12] Update metric (empty update)...")
        empty_update = TemplateMetricsUpdate()
        updated5 = await service.update_metric(metric1.id, empty_update)
        assert updated5 is not None
        assert updated5.usage_count == 100
        print("  OK Empty update handled correctly")
        
        print("[Test 13] List all...")
        all_metrics = await service.list_all(limit=10, offset=0)
        assert len(all_metrics) >= 2
        print(f"  OK Listed {len(all_metrics)} metrics")
        
        print("[Test 14] Get top by usage...")
        top_usage = await service.get_top_by_usage(limit=5)
        assert len(top_usage) >= 2
        assert top_usage[0].usage_count >= top_usage[1].usage_count
        print(f"  OK Top by usage: {[m.template_name for m in top_usage]}")
        
        print("[Test 15] Get top by success rate...")
        top_success = await service.get_top_by_success_rate(limit=5)
        assert len(top_success) >= 2
        print(f"  OK Top by success: {[m.template_name for m in top_success]}")
        
        print("[Test 16] Get low performing...")
        low_perf = await service.get_low_performing(min_usage=5, max_success_rate=0.5)
        print(f"  OK Low performing: {len(low_perf)} templates")
        
        print("[Test 17] Aggregate stats...")
        stats = await service.get_aggregate_stats()
        assert stats["total_templates"] >= 3
        assert stats["total_usage"] >= 100
        print(f"  OK Stats: templates={stats['total_templates']}, usage={stats['total_usage']}")
        
        print("[Test 18] Delete by name and pattern...")
        deleted1 = await service.delete_by_name_and_pattern(
            "git_operations", r"git commit (.+)"
        )
        assert deleted1 is True
        print("  OK Deleted by name and pattern")
        
        print("[Test 19] Delete by name (multiple)...")
        await service.create_metric(
            TemplateMetricsCreate(
                template_name="test_delete",
                pattern="pattern1",
                usage_count=1,
                success_count=1,
                failure_count=0,
                avg_confidence=Decimal("1.0000"),
                total_generation_time_ms=10,
            )
        )
        await service.create_metric(
            TemplateMetricsCreate(
                template_name="test_delete",
                pattern="pattern2",
                usage_count=1,
                success_count=1,
                failure_count=0,
                avg_confidence=Decimal("1.0000"),
                total_generation_time_ms=10,
            )
        )
        deleted2 = await service.delete_by_name("test_delete")
        assert deleted2 == 2
        print(f"  OK Deleted {deleted2} metrics by name")
        
        print("[Test 20] Delete by ID...")
        deleted3 = await service.delete_metric(metric2.id)
        assert deleted3 is True
        print("  OK Deleted by ID")
        
        print("[Test 21] Delete non-existent...")
        deleted4 = await service.delete_metric(uuid4())
        assert deleted4 is False
        print("  OK Correctly returned False")
        
        print("[Test 22] SQL injection attempt (should be safe)...")
        malicious_name = "backup_database'; DROP TABLE template_metrics; --"
        not_found2 = await service.get_by_name(malicious_name)
        assert not_found2 is None
        print("  OK SQL injection safely handled")
        
        print("\n" + "=" * 50)
        print("ALL 22 TESTS PASSED")
        print("=" * 50)
        
    except Exception as e:
        print(f"\n FAIL Test failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        for metric_id in created_ids:
            try:
                await service.delete_metric(metric_id)
            except Exception:
                pass
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(test_comprehensive())
