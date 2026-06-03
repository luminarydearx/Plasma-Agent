import pytest
from uuid import uuid4, UUID
from datetime import datetime, timezone, timedelta

from plasmaagent.ai.suggestions.models import (
    SuggestionType,
    Priority,
    Recommendation,
    SimilarTask,
    AnomalyReport,
    PerformanceHint,
    SuggestionRequest,
    SuggestionBundle,
)


class TestSuggestionModels:
    def test_suggestion_type_enum(self):
        assert SuggestionType.NEXT_ACTION == "next_action"
        assert SuggestionType.SIMILAR_TASK == "similar_task"
        assert SuggestionType.ANOMALY == "anomaly"
        assert SuggestionType.PERFORMANCE == "performance"

    def test_priority_enum(self):
        assert Priority.LOW == "low"
        assert Priority.MEDIUM == "medium"
        assert Priority.HIGH == "high"
        assert Priority.CRITICAL == "critical"

    def test_recommendation_valid(self):
        rec = Recommendation(
            id=uuid4(),
            suggestion_type=SuggestionType.NEXT_ACTION,
            priority=Priority.HIGH,
            title="Test",
            description="Test description",
            confidence=0.9,
            created_at=datetime.now(timezone.utc),
        )
        assert rec.confidence == 0.9

    def test_recommendation_frozen(self):
        rec = Recommendation(
            id=uuid4(),
            suggestion_type=SuggestionType.NEXT_ACTION,
            priority=Priority.HIGH,
            title="Test",
            description="Test",
            confidence=0.9,
            created_at=datetime.now(timezone.utc),
        )
        with pytest.raises(Exception):
            rec.title = "changed"

    def test_recommendation_invalid_confidence_high(self):
        with pytest.raises(Exception):
            Recommendation(
                id=uuid4(),
                suggestion_type=SuggestionType.NEXT_ACTION,
                priority=Priority.HIGH,
                title="Test",
                description="Test",
                confidence=1.5,
                created_at=datetime.now(timezone.utc),
            )

    def test_recommendation_invalid_confidence_low(self):
        with pytest.raises(Exception):
            Recommendation(
                id=uuid4(),
                suggestion_type=SuggestionType.NEXT_ACTION,
                priority=Priority.HIGH,
                title="Test",
                description="Test",
                confidence=-0.1,
                created_at=datetime.now(timezone.utc),
            )

    def test_recommendation_empty_title_rejected(self):
        with pytest.raises(Exception):
            Recommendation(
                id=uuid4(),
                suggestion_type=SuggestionType.NEXT_ACTION,
                priority=Priority.HIGH,
                title="",
                description="Test",
                confidence=0.5,
                created_at=datetime.now(timezone.utc),
            )

    def test_recommendation_long_title_rejected(self):
        with pytest.raises(Exception):
            Recommendation(
                id=uuid4(),
                suggestion_type=SuggestionType.NEXT_ACTION,
                priority=Priority.HIGH,
                title="x" * 201,
                description="Test",
                confidence=0.5,
                created_at=datetime.now(timezone.utc),
            )

    def test_recommendation_metadata_too_large(self):
        with pytest.raises(Exception):
            Recommendation(
                id=uuid4(),
                suggestion_type=SuggestionType.NEXT_ACTION,
                priority=Priority.HIGH,
                title="Test",
                description="Test",
                confidence=0.5,
                metadata={"big": "x" * 15000},
                created_at=datetime.now(timezone.utc),
            )

    def test_similar_task_valid(self):
        st = SimilarTask(
            task_id=uuid4(),
            task_name="Similar",
            similarity_score=0.75,
            common_commands=5,
            last_executed=datetime.now(timezone.utc),
        )
        assert st.similarity_score == 0.75

    def test_similar_task_invalid_score(self):
        with pytest.raises(Exception):
            SimilarTask(
                task_id=uuid4(),
                task_name="Test",
                similarity_score=1.5,
                common_commands=1,
            )

    def test_anomaly_report_valid(self):
        report = AnomalyReport(
            task_id=uuid4(),
            anomaly_type="slow",
            severity=Priority.MEDIUM,
            description="Slow command",
            baseline_value=100.0,
            observed_value=500.0,
            deviation_factor=5.0,
            recommendations=["optimize"],
        )
        assert report.deviation_factor == 5.0

    def test_anomaly_report_negative_deviation_rejected(self):
        with pytest.raises(Exception):
            AnomalyReport(
                task_id=uuid4(),
                anomaly_type="test",
                severity=Priority.LOW,
                description="Test",
                baseline_value=100.0,
                observed_value=50.0,
                deviation_factor=-1.0,
            )

    def test_anomaly_report_too_many_recommendations(self):
        with pytest.raises(Exception):
            AnomalyReport(
                task_id=uuid4(),
                anomaly_type="test",
                severity=Priority.LOW,
                description="Test",
                baseline_value=100.0,
                observed_value=200.0,
                deviation_factor=2.0,
                recommendations=[f"rec_{i}" for i in range(25)],
            )

    def test_anomaly_report_long_recommendation_rejected(self):
        with pytest.raises(Exception):
            AnomalyReport(
                task_id=uuid4(),
                anomaly_type="test",
                severity=Priority.LOW,
                description="Test",
                baseline_value=100.0,
                observed_value=200.0,
                deviation_factor=2.0,
                recommendations=["x" * 501],
            )

    def test_performance_hint_valid(self):
        hint = PerformanceHint(
            task_id=uuid4(),
            hint_type="slow",
            description="Slow command",
            estimated_savings_ms=500,
            confidence=0.8,
            affected_commands=[1, 2, 3],
        )
        assert hint.estimated_savings_ms == 500

    def test_performance_hint_negative_savings_rejected(self):
        with pytest.raises(Exception):
            PerformanceHint(
                task_id=uuid4(),
                hint_type="test",
                description="Test",
                estimated_savings_ms=-100,
                confidence=0.5,
            )

    def test_suggestion_request_defaults(self):
        req = SuggestionRequest()
        assert req.include_next_actions is True
        assert req.include_similar is True
        assert req.include_anomalies is True
        assert req.include_performance is True
        assert req.max_similar == 5
        assert req.anomaly_threshold == 2.0

    def test_suggestion_request_invalid_max_similar(self):
        with pytest.raises(Exception):
            SuggestionRequest(max_similar=100)

    def test_suggestion_request_invalid_threshold(self):
        with pytest.raises(Exception):
            SuggestionRequest(anomaly_threshold=0.5)

    def test_suggestion_bundle_valid(self):
        bundle = SuggestionBundle(
            total_suggestions=0,
            generated_at=datetime.now(timezone.utc),
        )
        assert bundle.total_suggestions == 0
        assert bundle.recommendations == []

    def test_suggestion_bundle_negative_total_rejected(self):
        with pytest.raises(Exception):
            SuggestionBundle(
                total_suggestions=-1,
                generated_at=datetime.now(timezone.utc),
            )

    def test_recommendation_boundary_confidence(self):
        rec_zero = Recommendation(
            id=uuid4(),
            suggestion_type=SuggestionType.NEXT_ACTION,
            priority=Priority.LOW,
            title="T",
            description="D",
            confidence=0.0,
            created_at=datetime.now(timezone.utc),
        )
        rec_one = Recommendation(
            id=uuid4(),
            suggestion_type=SuggestionType.NEXT_ACTION,
            priority=Priority.LOW,
            title="T",
            description="D",
            confidence=1.0,
            created_at=datetime.now(timezone.utc),
        )
        assert rec_zero.confidence == 0.0
        assert rec_one.confidence == 1.0
