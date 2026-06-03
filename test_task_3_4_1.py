import asyncio
from decimal import Decimal
from datetime import datetime
from uuid import uuid4

from plasmaagent.models import (
    TemplateMetrics,
    TemplateMetricsCreate,
    TemplateMetricsUpdate,
)


def test_model_creation():
    print("[TEST 1] Model creation with defaults")
    try:
        metrics = TemplateMetricsCreate(
            template_name="backup_database",
            pattern=r"backup\s+(postgresql|mysql)",
        )
        assert metrics.template_name == "backup_database"
        assert metrics.usage_count == 0
        assert metrics.success_count == 0
        assert metrics.failure_count == 0
        assert metrics.avg_confidence == Decimal("0.00")
        assert metrics.total_generation_time_ms == 0
        assert metrics.last_used_at is None
        print("  ✅ PASSED")
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        return False
    return True


def test_model_with_values():
    print("[TEST 2] Model creation with explicit values")
    try:
        now = datetime.now()
        metrics = TemplateMetrics(
            id=uuid4(),
            template_name="cleanup_files",
            pattern=r"clean.*files",
            usage_count=10,
            success_count=8,
            failure_count=2,
            avg_confidence=Decimal("0.90"),
            total_generation_time_ms=150,
            last_used_at=now,
            created_at=now,
            updated_at=now,
        )
        assert metrics.usage_count == 10
        assert metrics.avg_confidence == Decimal("0.90")
        print("  ✅ PASSED")
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        return False
    return True


def test_model_update():
    print("[TEST 3] Model update")
    try:
        update = TemplateMetricsUpdate(
            usage_count=15,
            success_count=12,
        )
        assert update.usage_count == 15
        assert update.success_count == 12
        assert update.failure_count is None
        print("  ✅ PASSED")
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        return False
    return True


def test_validation_max_length():
    print("[TEST 4] Validation - max_length")
    try:
        try:
            TemplateMetricsCreate(
                template_name="x" * 300,
                pattern="test",
            )
            print("  ❌ FAILED: Should have raised validation error")
            return False
        except Exception:
            print("  ✅ PASSED (correctly rejected)")
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        return False
    return True


def test_validation_negative_values():
    print("[TEST 5] Validation - negative values")
    try:
        try:
            TemplateMetricsCreate(
                template_name="test",
                pattern="test",
                usage_count=-1,
            )
            print("  ❌ FAILED: Should have raised validation error")
            return False
        except Exception:
            print("  ✅ PASSED (correctly rejected)")
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        return False
    return True


def test_validation_confidence_range():
    print("[TEST 6] Validation - confidence range (0.00-1.00)")
    try:
        try:
            TemplateMetricsCreate(
                template_name="test",
                pattern="test",
                avg_confidence=Decimal("1.50"),
            )
            print("  ❌ FAILED: Should have raised validation error")
            return False
        except Exception:
            print("  ✅ PASSED (correctly rejected > 1.00)")
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        return False
    return True


async def test_database_operations():
    print("[TEST 7] Database CRUD operations")
    try:
        from plasmaagent.core.database import get_database
        from plasmaagent.core.config import get_settings

        settings = get_settings()
        db = get_database()
        await db.connect()

        test_id = uuid4()
        test_name = f"test_template_{test_id.hex[:8]}"

        async with db.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO template_metrics 
                (id, template_name, pattern, usage_count, success_count, failure_count, 
                 avg_confidence, total_generation_time_ms, last_used_at, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())
                """,
                test_id,
                test_name,
                r"test.*pattern",
                5,
                4,
                1,
                Decimal("0.85"),
                100,
                datetime.now(),
            )

        async with db.connection() as conn:
            result = await conn.fetchrow(
                "SELECT * FROM template_metrics WHERE id = $1",
                test_id,
            )
            assert result is not None
            assert result["template_name"] == test_name
            assert result["usage_count"] == 5

        async with db.transaction() as conn:
            await conn.execute(
                """
                UPDATE template_metrics 
                SET usage_count = usage_count + 1, updated_at = NOW()
                WHERE id = $1
                """,
                test_id,
            )

        async with db.connection() as conn:
            result = await conn.fetchrow(
                "SELECT usage_count FROM template_metrics WHERE id = $1",
                test_id,
            )
            assert result["usage_count"] == 6

        async with db.transaction() as conn:
            await conn.execute(
                "DELETE FROM template_metrics WHERE id = $1",
                test_id,
            )

        async with db.connection() as conn:
            result = await conn.fetchrow(
                "SELECT 1 FROM template_metrics WHERE id = $1",
                test_id,
            )
            assert result is None

        await db.disconnect()
        print("  ✅ PASSED (insert, select, update, delete)")
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        return False
    return True


def test_edge_cases():
    print("[TEST 8] Edge cases")
    try:
        metrics = TemplateMetricsCreate(
            template_name="edge_case",
            pattern=r"[^\w\s]+",
            usage_count=0,
            success_count=0,
            failure_count=0,
            avg_confidence=Decimal("0.00"),
            total_generation_time_ms=0,
        )
        assert metrics.usage_count == 0
        print("  ✅ PASSED (zero values)")

        metrics2 = TemplateMetricsCreate(
            template_name="large_values",
            pattern="x" * 500,
            usage_count=999999,
            success_count=999998,
            failure_count=1,
            avg_confidence=Decimal("1.00"),
            total_generation_time_ms=999999,
        )
        assert metrics2.usage_count == 999999
        print("  ✅ PASSED (large values)")
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        return False
    return True


def main():
    print("=" * 60)
    print("TASK 3.4.1 - Template Metrics Model Testing")
    print("=" * 60)
    print()

    results = []
    results.append(("Model creation defaults", test_model_creation()))
    results.append(("Model with values", test_model_with_values()))
    results.append(("Model update", test_model_update()))
    results.append(("Validation max_length", test_validation_max_length()))
    results.append(("Validation negative", test_validation_negative_values()))
    results.append(("Validation confidence", test_validation_confidence_range()))
    results.append(("Database CRUD", asyncio.run(test_database_operations())))
    results.append(("Edge cases", test_edge_cases()))

    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")

    print()
    print(f"Total: {passed}/{total} passed")
    print()

    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit(main())
