import pytest
from pydantic import ValidationError
from plasmaagent.ai.conditional import (
    Condition,
    ConditionOperator,
    ConditionEvaluator,
    ConditionalStep,
)


class TestConditionEvaluatorBasic:
    def test_init_default(self):
        evaluator = ConditionEvaluator()
        assert evaluator._max_string_length == 10000
    
    def test_init_custom(self):
        evaluator = ConditionEvaluator(max_string_length=5000)
        assert evaluator._max_string_length == 5000
    
    def test_evaluate_eq_true(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="status", operator=ConditionOperator.EQ, value="success")
        context = {"status": "success"}
        assert evaluator.evaluate(condition, context) is True
    
    def test_evaluate_eq_false(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="status", operator=ConditionOperator.EQ, value="success")
        context = {"status": "failed"}
        assert evaluator.evaluate(condition, context) is False
    
    def test_evaluate_ne(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="status", operator=ConditionOperator.NE, value="failed")
        context = {"status": "success"}
        assert evaluator.evaluate(condition, context) is True
    
    def test_evaluate_lt(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="exit_code", operator=ConditionOperator.LT, value=1)
        context = {"exit_code": 0}
        assert evaluator.evaluate(condition, context) is True
    
    def test_evaluate_le(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="exit_code", operator=ConditionOperator.LE, value=0)
        context = {"exit_code": 0}
        assert evaluator.evaluate(condition, context) is True
    
    def test_evaluate_gt(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="count", operator=ConditionOperator.GT, value=5)
        context = {"count": 10}
        assert evaluator.evaluate(condition, context) is True
    
    def test_evaluate_ge(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="count", operator=ConditionOperator.GE, value=10)
        context = {"count": 10}
        assert evaluator.evaluate(condition, context) is True
    
    def test_evaluate_contains(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="output", operator=ConditionOperator.CONTAINS, value="error")
        context = {"output": "An error occurred"}
        assert evaluator.evaluate(condition, context) is True
    
    def test_evaluate_not_contains(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="output", operator=ConditionOperator.NOT_CONTAINS, value="error")
        context = {"output": "Success"}
        assert evaluator.evaluate(condition, context) is True
    
    def test_evaluate_starts_with(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="output", operator=ConditionOperator.STARTS_WITH, value="Error")
        context = {"output": "Error: file not found"}
        assert evaluator.evaluate(condition, context) is True
    
    def test_evaluate_ends_with(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="output", operator=ConditionOperator.ENDS_WITH, value="found")
        context = {"output": "Error: file not found"}
        assert evaluator.evaluate(condition, context) is True


class TestConditionEvaluatorNegate:
    def test_negate_eq(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="status", operator=ConditionOperator.EQ, value="success", negate=True)
        context = {"status": "success"}
        assert evaluator.evaluate(condition, context) is False
    
    def test_negate_ne(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="status", operator=ConditionOperator.NE, value="failed", negate=True)
        context = {"status": "success"}
        assert evaluator.evaluate(condition, context) is False


class TestConditionEvaluatorNestedVariables:
    def test_nested_dict(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="result.exit_code", operator=ConditionOperator.EQ, value=0)
        context = {"result": {"exit_code": 0}}
        assert evaluator.evaluate(condition, context) is True
    
    def test_deeply_nested(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="task.result.status", operator=ConditionOperator.EQ, value="done")
        context = {"task": {"result": {"status": "done"}}}
        assert evaluator.evaluate(condition, context) is True
    
    def test_nested_missing_key(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="result.exit_code", operator=ConditionOperator.EQ, value=0)
        context = {"result": {}}
        with pytest.raises(KeyError):
            evaluator.evaluate(condition, context)
    
    def test_nested_attribute(self):
        evaluator = ConditionEvaluator()
        
        class Result:
            exit_code = 0
        
        condition = Condition(variable="result.exit_code", operator=ConditionOperator.EQ, value=0)
        context = {"result": Result()}
        assert evaluator.evaluate(condition, context) is True


class TestConditionEvaluatorEdgeCases:
    def test_invalid_context_type(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="status", operator=ConditionOperator.EQ, value="success")
        with pytest.raises(TypeError, match="Context must be a dictionary"):
            evaluator.evaluate(condition, "not a dict")
    
    def test_empty_variable_name_validation(self):
        with pytest.raises(ValidationError, match="at least 1 character"):
            Condition(variable="", operator=ConditionOperator.EQ, value="success")
    
    def test_variable_too_long_validation(self):
        long_var = "a" * 201
        with pytest.raises(ValidationError, match="at most 200 characters"):
            Condition(variable=long_var, operator=ConditionOperator.EQ, value="success")
    
    def test_variable_path_too_deep(self):
        evaluator = ConditionEvaluator()
        deep_path = ".".join(["level"] * 12)
        condition = Condition(variable=deep_path, operator=ConditionOperator.EQ, value="value")
        context = {"level": {"level": {"level": {"level": {"level": {"level": {"level": {"level": {"level": {"level": {"level": {"level": "value"}}}}}}}}}}}}
        with pytest.raises(ValueError, match="too deep"):
            evaluator.evaluate(condition, context)
    
    def test_contains_on_non_iterable(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="count", operator=ConditionOperator.CONTAINS, value="5")
        context = {"count": 5}
        with pytest.raises(TypeError, match="Cannot check contains"):
            evaluator.evaluate(condition, context)
    
    def test_numeric_comparison_with_strings(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="count", operator=ConditionOperator.LT, value="10")
        context = {"count": "5"}
        assert evaluator.evaluate(condition, context) is True
    
    def test_string_truncation(self):
        evaluator = ConditionEvaluator(max_string_length=10)
        condition = Condition(variable="output", operator=ConditionOperator.CONTAINS, value="test")
        context = {"output": "a" * 100 + "test"}
        assert evaluator.evaluate(condition, context) is False
    
    def test_bool_comparison(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="enabled", operator=ConditionOperator.EQ, value=True)
        context = {"enabled": True}
        assert evaluator.evaluate(condition, context) is True
    
    def test_float_comparison(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="score", operator=ConditionOperator.GE, value=9.5)
        context = {"score": 9.7}
        assert evaluator.evaluate(condition, context) is True


class TestConditionEvaluatorStep:
    def test_evaluate_step_then(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="exit_code", operator=ConditionOperator.EQ, value=0)
        step = ConditionalStep(step_id="s1", condition=condition, then_action="execute")
        context = {"exit_code": 0}
        action, else_step = evaluator.evaluate_step(step, context)
        assert action == "execute"
        assert else_step is None
    
    def test_evaluate_step_else(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="exit_code", operator=ConditionOperator.EQ, value=0)
        step = ConditionalStep(
            step_id="s1",
            condition=condition,
            then_action="execute",
            else_action="skip",
            else_step_id="s2"
        )
        context = {"exit_code": 1}
        action, else_step = evaluator.evaluate_step(step, context)
        assert action == "skip"
        assert else_step == "s2"
    
    def test_evaluate_step_else_default_skip(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="exit_code", operator=ConditionOperator.EQ, value=0)
        step = ConditionalStep(step_id="s1", condition=condition, then_action="execute")
        context = {"exit_code": 1}
        action, else_step = evaluator.evaluate_step(step, context)
        assert action == "skip"
        assert else_step is None
    
    def test_evaluate_step_invalid_type(self):
        evaluator = ConditionEvaluator()
        with pytest.raises(TypeError, match="must be a ConditionalStep"):
            evaluator.evaluate_step("not a step", {})


class TestConditionModels:
    def test_condition_operator_enum(self):
        assert ConditionOperator.EQ.value == "eq"
        assert ConditionOperator.NE.value == "ne"
        assert ConditionOperator.LT.value == "lt"
        assert ConditionOperator.LE.value == "le"
        assert ConditionOperator.GT.value == "gt"
        assert ConditionOperator.GE.value == "ge"
        assert ConditionOperator.CONTAINS.value == "contains"
        assert ConditionOperator.NOT_CONTAINS.value == "not_contains"
        assert ConditionOperator.STARTS_WITH.value == "starts_with"
        assert ConditionOperator.ENDS_WITH.value == "ends_with"
    
    def test_condition_validation(self):
        condition = Condition(variable="status", operator=ConditionOperator.EQ, value="success")
        assert condition.variable == "status"
        assert condition.operator == ConditionOperator.EQ
        assert condition.value == "success"
        assert condition.negate is False
    
    def test_condition_frozen(self):
        condition = Condition(variable="status", operator=ConditionOperator.EQ, value="success")
        with pytest.raises(Exception):
            condition.variable = "other"
    
    def test_conditional_step_validation(self):
        condition = Condition(variable="status", operator=ConditionOperator.EQ, value="success")
        step = ConditionalStep(
            step_id="s1",
            condition=condition,
            then_action="execute",
            else_action="skip",
            else_step_id="s2"
        )
        assert step.step_id == "s1"
        assert step.condition == condition
        assert step.then_action == "execute"
        assert step.else_action == "skip"
        assert step.else_step_id == "s2"
    
    def test_conditional_step_defaults(self):
        condition = Condition(variable="status", operator=ConditionOperator.EQ, value="success")
        step = ConditionalStep(step_id="s1", condition=condition)
        assert step.then_action == "execute"
        assert step.else_action is None
        assert step.else_step_id is None


class TestConditionEvaluatorPerformance:
    def test_evaluate_performance(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="status", operator=ConditionOperator.EQ, value="success")
        context = {"status": "success"}
        
        import time
        start = time.time()
        for _ in range(1000):
            evaluator.evaluate(condition, context)
        elapsed = time.time() - start
        
        assert elapsed < 1.0, f"1000 evaluations took {elapsed:.2f}s"
    
    def test_large_context(self):
        evaluator = ConditionEvaluator()
        condition = Condition(variable="status", operator=ConditionOperator.EQ, value="success")
        context = {f"key_{i}": f"value_{i}" for i in range(10000)}
        context["status"] = "success"
        
        import time
        start = time.time()
        result = evaluator.evaluate(condition, context)
        elapsed = time.time() - start
        
        assert result is True
        assert elapsed < 0.1, f"Evaluation with large context took {elapsed:.2f}s"
