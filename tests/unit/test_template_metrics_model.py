import sys
from datetime import datetime
from decimal import Decimal
from uuid import uuid4, UUID

from pydantic import ValidationError

sys.path.insert(0, "src")

from plasmaagent.models.template_metrics import (
    TemplateMetrics,
    TemplateMetricsBase,
    TemplateMetricsCreate,
    TemplateMetricsUpdate,
)


def test_base_creation_with_all_fields():
    data = {
        "template_name": "backup_database",
        "pattern": r"backup\s+(postgresql|mysql|sqlite)",
        "usage_count": 10,
        "success_count": 8,
        "failure_count": 2,
        "avg_confidence": Decimal("0.95"),
        "total_generation_time_ms": 250,
        "last_used_at": datetime.now(),
    }
    base = TemplateMetricsBase(**data)
    assert base.template_name == "backup_database"
    assert base.usage_count == 10
    assert base.success_count == 8
    assert base.failure_count == 2
    assert base.avg_confidence == Decimal("0.95")
    assert base.total_generation_time_ms == 250
    assert base.last_used_at is not None
    print("  test_base_creation_with_all_fields PASSED")


def test_base_creation_with_defaults():
    data = {
        "template_name": "test_template",
        "pattern": r"test\s+pattern",
    }
    base = TemplateMetricsBase(**data)
    assert base.usage_count == 0
    assert base.success_count == 0
    assert base.failure_count == 0
    assert base.avg_confidence == Decimal("0.00")
    assert base.total_generation_time_ms == 0
    assert base.last_used_at is None
    print("  test_base_creation_with_defaults PASSED")


def test_base_missing_required_fields():
    try:
        TemplateMetricsBase(template_name="test")
        print("  test_base_missing_required_fields FAILED - should raise")
        return False
    except ValidationError as e:
        assert "pattern" in str(e)
        print("  test_base_missing_required_fields PASSED")
        return True


def test_negative_usage_count():
    try:
        TemplateMetricsBase(
            template_name="test",
            pattern="test",
            usage_count=-1,
        )
        print("  test_negative_usage_count FAILED - should raise")
        return False
    except ValidationError:
        print("  test_negative_usage_count PASSED")
        return True


def test_negative_success_count():
    try:
        TemplateMetricsBase(
            template_name="test",
            pattern="test",
            success_count=-1,
        )
        print("  test_negative_success_count FAILED - should raise")
        return False
    except ValidationError:
        print("  test_negative_success_count PASSED")
        return True


def test_negative_failure_count():
    try:
        TemplateMetricsBase(
            template_name="test",
            pattern="test",
            failure_count=-5,
        )
        print("  test_negative_failure_count FAILED - should raise")
        return False
    except ValidationError:
        print("  test_negative_failure_count PASSED")
        return True


def test_confidence_below_zero():
    try:
        TemplateMetricsBase(
            template_name="test",
            pattern="test",
            avg_confidence=Decimal("-0.01"),
        )
        print("  test_confidence_below_zero FAILED - should raise")
        return False
    except ValidationError:
        print("  test_confidence_below_zero PASSED")
        return True


def test_confidence_above_one():
    try:
        TemplateMetricsBase(
            template_name="test",
            pattern="test",
            avg_confidence=Decimal("1.01"),
        )
        print("  test_confidence_above_one FAILED - should raise")
        return False
    except ValidationError:
        print("  test_confidence_above_one PASSED")
        return True


def test_confidence_boundary_values():
    base_zero = TemplateMetricsBase(
        template_name="test",
        pattern="test",
        avg_confidence=Decimal("0.00"),
    )
    assert base_zero.avg_confidence == Decimal("0.00")
    
    base_one = TemplateMetricsBase(
        template_name="test",
        pattern="test",
        avg_confidence=Decimal("1.00"),
    )
    assert base_one.avg_confidence == Decimal("1.00")
    
    base_mid = TemplateMetricsBase(
        template_name="test",
        pattern="test",
        avg_confidence=Decimal("0.50"),
    )
    assert base_mid.avg_confidence == Decimal("0.50")
    print("  test_confidence_boundary_values PASSED")


def test_template_name_max_length():
    long_name = "x" * 255
    base = TemplateMetricsBase(
        template_name=long_name,
        pattern="test",
    )
    assert base.template_name == long_name
    
    try:
        too_long = "x" * 256
        TemplateMetricsBase(
            template_name=too_long,
            pattern="test",
        )
        print("  test_template_name_max_length FAILED - should raise")
        return False
    except ValidationError:
        print("  test_template_name_max_length PASSED")
        return True


def test_pattern_max_length():
    long_pattern = "x" * 500
    base = TemplateMetricsBase(
        template_name="test",
        pattern=long_pattern,
    )
    assert base.pattern == long_pattern
    
    try:
        too_long = "x" * 501
        TemplateMetricsBase(
            template_name="test",
            pattern=too_long,
        )
        print("  test_pattern_max_length FAILED - should raise")
        return False
    except ValidationError:
        print("  test_pattern_max_length PASSED")
        return True


def test_create_model():
    create = TemplateMetricsCreate(
        template_name="backup_db",
        pattern=r"backup\s+\w+",
        usage_count=5,
    )
    assert create.template_name == "backup_db"
    assert create.usage_count == 5
    print("  test_create_model PASSED")


def test_update_model_partial():
    update = TemplateMetricsUpdate(usage_count=10)
    assert update.usage_count == 10
    assert update.success_count is None
    assert update.failure_count is None
    print("  test_update_model_partial PASSED")


def test_update_model_all_fields():
    update = TemplateMetricsUpdate(
        usage_count=100,
        success_count=90,
        failure_count=10,
        avg_confidence=Decimal("0.90"),
        total_generation_time_ms=5000,
        last_used_at=datetime.now(),
    )
    assert update.usage_count == 100
    assert update.success_count == 90
    assert update.failure_count == 10
    print("  test_update_model_all_fields PASSED")


def test_full_model():
    test_id = uuid4()
    now = datetime.now()
    full = TemplateMetrics(
        id=test_id,
        template_name="full_test",
        pattern=r"full\s+test",
        usage_count=50,
        success_count=45,
        failure_count=5,
        avg_confidence=Decimal("0.88"),
        total_generation_time_ms=1500,
        last_used_at=now,
        created_at=now,
        updated_at=now,
    )
    assert full.id == test_id
    assert full.template_name == "full_test"
    assert full.created_at == now
    print("  test_full_model PASSED")


def test_full_model_from_dict():
    test_id = uuid4()
    now = datetime.now()
    data = {
        "id": test_id,
        "template_name": "from_dict",
        "pattern": r"from\s+dict",
        "usage_count": 10,
        "success_count": 8,
        "failure_count": 2,
        "avg_confidence": Decimal("0.80"),
        "total_generation_time_ms": 300,
        "last_used_at": now,
        "created_at": now,
        "updated_at": now,
    }
    full = TemplateMetrics.model_validate(data)
    assert full.id == test_id
    assert full.template_name == "from_dict"
    print("  test_full_model_from_dict PASSED")


def test_full_model_missing_required():
    try:
        TemplateMetrics(
            template_name="test",
            pattern="test",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        print("  test_full_model_missing_required FAILED - should raise (id missing)")
        return False
    except ValidationError as e:
        assert "id" in str(e)
        print("  test_full_model_missing_required PASSED")
        return True


def test_serialization():
    test_id = uuid4()
    now = datetime.now()
    full = TemplateMetrics(
        id=test_id,
        template_name="serialize_test",
        pattern=r"serialize",
        usage_count=1,
        success_count=1,
        failure_count=0,
        avg_confidence=Decimal("1.00"),
        total_generation_time_ms=10,
        created_at=now,
        updated_at=now,
    )
    
    json_str = full.model_dump_json()
    assert "serialize_test" in json_str
    assert str(test_id) in json_str
    
    restored = TemplateMetrics.model_validate_json(json_str)
    assert restored.id == test_id
    assert restored.template_name == "serialize_test"
    print("  test_serialization PASSED")


def test_dict_dump():
    test_id = uuid4()
    now = datetime.now()
    full = TemplateMetrics(
        id=test_id,
        template_name="dict_test",
        pattern=r"dict",
        created_at=now,
        updated_at=now,
    )
    
    data = full.model_dump()
    assert isinstance(data, dict)
    assert data["template_name"] == "dict_test"
    assert data["id"] == test_id
    assert data["usage_count"] == 0
    print("  test_dict_dump PASSED")


def test_empty_strings():
    try:
        TemplateMetricsBase(template_name="", pattern="")
        print("  test_empty_strings: accepted empty (depends on Field constraints)")
    except ValidationError:
        print("  test_empty_strings: rejected empty")


def test_unicode_values():
    base = TemplateMetricsBase(
        template_name="テスト_テンプレート",
        pattern=r"テスト\s+\w+",
    )
    assert base.template_name == "テスト_テンプレート"
    print("  test_unicode_values PASSED")


def test_special_chars_in_pattern():
    complex_pattern = r"backup\s+(postgresql|mysql|sqlite)(?:\s+(\w+))?(?:\s+to\s+(.+))?"
    base = TemplateMetricsBase(
        template_name="complex_backup",
        pattern=complex_pattern,
    )
    assert base.pattern == complex_pattern
    print("  test_special_chars_in_pattern PASSED")


def test_very_large_counts():
    base = TemplateMetricsBase(
        template_name="large",
        pattern="large",
        usage_count=2**31 - 1,
        success_count=2**31 - 1,
        failure_count=2**31 - 1,
    )
    assert base.usage_count == 2**31 - 1
    print("  test_very_large_counts PASSED")


def test_negative_generation_time():
    try:
        TemplateMetricsBase(
            template_name="test",
            pattern="test",
            total_generation_time_ms=-100,
        )
        print("  test_negative_generation_time FAILED - should raise")
        return False
    except ValidationError:
        print("  test_negative_generation_time PASSED")
        return True


if __name__ == "__main__":
    print("=== TemplateMetrics Model Comprehensive Tests ===\n")
    
    tests = [
        test_base_creation_with_all_fields,
        test_base_creation_with_defaults,
        test_base_missing_required_fields,
        test_negative_usage_count,
        test_negative_success_count,
        test_negative_failure_count,
        test_confidence_below_zero,
        test_confidence_above_one,
        test_confidence_boundary_values,
        test_template_name_max_length,
        test_pattern_max_length,
        test_create_model,
        test_update_model_partial,
        test_update_model_all_fields,
        test_full_model,
        test_full_model_from_dict,
        test_full_model_missing_required,
        test_serialization,
        test_dict_dump,
        test_empty_strings,
        test_unicode_values,
        test_special_chars_in_pattern,
        test_very_large_counts,
        test_negative_generation_time,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            result = test()
            if result is False:
                failed += 1
            else:
                passed += 1
        except Exception as e:
            print(f"  {test.__name__} EXCEPTION: {e}")
            failed += 1
    
    print(f"\n=== Results: {passed}/{passed + failed} passed ===")
    sys.exit(0 if failed == 0 else 1)
