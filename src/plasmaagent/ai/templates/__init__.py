# Disabled modules that require psycopg (PostgreSQL-specific)
# from plasmaagent.ai.templates.learner import TemplateLearner
from plasmaagent.ai.templates.models import (
    LearnedTemplate,
    LearningReport,
    RollbackReport,
    TemplateCandidate,
    TemplateSource,
    TemplateVersion,
    TemplateVersionCreate,
)
# from plasmaagent.ai.templates.versioning import TemplateVersionService
from plasmaagent.ai.templates.ab_testing import (
    ABTest,
    ABTestCreate,
    ABTestResult,
    ABTestStats,
    ABTestAnalysis,
)
# from plasmaagent.ai.templates.ab_test_service import ABTestService
from plasmaagent.ai.templates.retirement import (
    TemplateRetirement,
    TemplateRetirementCreate,
    RetirementScanRequest,
    RetirementScanReport,
)
# from plasmaagent.ai.templates.retirement_service import RetirementService
from plasmaagent.ai.templates.auto_generator import (
    TemplateCandidateCreate,
    TemplateCandidate as AutoTemplateCandidate,
    CandidateDetectionRequest,
    CandidateDetectionReport,
)
# from plasmaagent.ai.templates.auto_generator_service import AutoTemplateGenerator

__all__ = [
    "LearnedTemplate",
    "LearningReport",
    "RollbackReport",
    "TemplateCandidate",
    "TemplateSource",
    "TemplateVersion",
    "TemplateVersionCreate",
    "ABTest",
    "ABTestCreate",
    "ABTestResult",
    "ABTestStats",
    "ABTestAnalysis",
    "TemplateRetirement",
    "TemplateRetirementCreate",
    "RetirementScanRequest",
    "RetirementScanReport",
    "TemplateCandidateCreate",
    "AutoTemplateCandidate",
    "CandidateDetectionRequest",
    "CandidateDetectionReport",
]
