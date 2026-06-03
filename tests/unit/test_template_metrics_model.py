import sys
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest
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


def test_base_missing_required_fields():
    with pytest.raises(ValidationError) as exc_info:
        TemplateMetricsBase(template_name="test")
    assert "pattern" in str(exc_info.value)


def test_negative_usage_count():
    with pytest.raises(ValidationError):
        TemplateMetricsBase(
            template_name="test",
            pattern="test",
            usage_count=-1,
        )


def test_negative_success_count():
    with pytest.raises(ValidationError):
        TemplateMetricsBase(
            template_name="test",
            pattern="test",
            success_count=-1,
        )


def test_negative_failure_count():
    with pytest.raises(ValidationError):
        TemplateMetricsBase(
            template_name="test",
            pattern="test",
            failure_count=-5,
        )


def test_confidence_below_zero():
    with pytest.raises(ValidationError):
        TemplateMetricsBase(
            template_name="test",
            pattern="test",
            avg_confidence=Decimal("-0.01"),
        )


def test_confidence_above_one():
    with pytest.raises(ValidationError):
        TemplateMetricsBase(
            template_name="test",
            pattern="test",
            avg_confidence=Decimal("1.01"),
        )


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


def test_template_name_max_length():
    long_name = "x" * 255
    base = TemplateMetricsBase(
        template_name=long_name,
        pattern="test",
    )
    assert base.template_name == long_name
    with pytest.raises(ValidationError):
        TemplateMetricsBase(
            template_name="x" * 256,
            pattern="test",
        )


def test_pattern_max_length():
    long_pattern = "x" * 500
    base = TemplateMetricsBase(
        template_name="test",
        pattern=long_pattern,
    )
    assert base.pattern == long_pattern
    with pytest.raises(ValidationError):
        TemplateMetricsBase(
            template_name="test",
            pattern="x" * 501,
        )


def test_create_model():
    create = TemplateMetricsCreate(
        template_name="backup_db",
        pattern=r"backup\s+\w+",
        usage_count=5,
    )
    assert create.template_name == "backup_db"
    assert create.usage_count == 5


def test_update_model_partial():
    update = TemplateMetricsUpdate(usage_count=10)
    assert update.usage_count == 10
    assert update.success_count is None
    assert update.failure_count is None


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


def test_full_model_missing_required():
    with pytest.raises(ValidationError) as exc_info:
        TemplateMetrics(
            template_name="test",
            pattern="test",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
    assert "id" in str(exc_info.value)


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


def test_empty_strings():
    try:
        TemplateMetricsBase(template_name="", pattern="")
    except ValidationError:
        pass


def test_unicode_values():
    base = TemplateMetricsBase(
        template_name="テスト_テンプレート",
        pattern=r"テスト\s+\w+",
    )
    assert base.template_name == "テスト_テンプレート"


def test_special_chars_in_pattern():
    complex_pattern = r"backup\s+(postgresql|mysql|sqlite)(?:\s+(\w+))?(?:\s+to\s+(.+))?"
    base = TemplateMetricsBase(
        template_name="complex_backup",
        pattern=complex_pattern,
    )
    assert base.pattern == complex_pattern


def test_very_large_counts():
    base = TemplateMetricsBase(
        template_name="large",
        pattern="large",
        usage_count=2**31 - 1,
        success_count=2**31 - 1,
        failure_count=2**31 - 1,
    )
    assert base.usage_count == 2**31 - 1


def test_negative_generation_time():
    with pytest.raises(ValidationError):
        TemplateMetricsBase(
            template_name="test",
            pattern="test",
            total_generation_time_ms=-100,
        )
