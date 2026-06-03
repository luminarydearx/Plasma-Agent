from typing import Any, Optional
from .models import Condition, ConditionOperator, ConditionalStep


class ConditionEvaluator:
    def __init__(self, max_string_length: int = 10000):
        self._max_string_length = max_string_length
    
    def evaluate(self, condition: Condition, context: dict[str, Any]) -> bool:
        if not isinstance(context, dict):
            raise TypeError("Context must be a dictionary")
        
        var_value = self._resolve_variable(condition.variable, context)
        expected_value = condition.value
        
        result = self._compare(var_value, expected_value, condition.operator)
        
        return not result if condition.negate else result
    
    def _resolve_variable(self, variable: str, context: dict[str, Any]) -> Any:
        if not variable or not isinstance(variable, str):
            raise ValueError("Variable name must be a non-empty string")
        
        if len(variable) > 200:
            raise ValueError(f"Variable name too long: {len(variable)} > 200")
        
        parts = variable.split(".")
        current = context
        
        for i, part in enumerate(parts):
            if not part or not isinstance(part, str):
                raise ValueError(f"Invalid variable path: {variable}")
            
            if i > 10:
                raise ValueError(f"Variable path too deep: {variable}")
            
            if isinstance(current, dict):
                if part not in current:
                    raise KeyError(f"Variable not found: {variable} (missing key: {part})")
                current = current[part]
            else:
                if not hasattr(current, part):
                    raise AttributeError(f"Variable not found: {variable} (missing attribute: {part})")
                current = getattr(current, part)
        
        return current
    
    def _compare(self, actual: Any, expected: Any, operator: ConditionOperator) -> bool:
        if operator == ConditionOperator.EQ:
            return self._safe_eq(actual, expected)
        elif operator == ConditionOperator.NE:
            return not self._safe_eq(actual, expected)
        elif operator == ConditionOperator.LT:
            return self._safe_lt(actual, expected)
        elif operator == ConditionOperator.LE:
            return self._safe_le(actual, expected)
        elif operator == ConditionOperator.GT:
            return self._safe_gt(actual, expected)
        elif operator == ConditionOperator.GE:
            return self._safe_ge(actual, expected)
        elif operator == ConditionOperator.CONTAINS:
            return self._safe_contains(actual, expected)
        elif operator == ConditionOperator.NOT_CONTAINS:
            return not self._safe_contains(actual, expected)
        elif operator == ConditionOperator.STARTS_WITH:
            return self._safe_starts_with(actual, expected)
        elif operator == ConditionOperator.ENDS_WITH:
            return self._safe_ends_with(actual, expected)
        else:
            raise ValueError(f"Unknown operator: {operator}")
    
    def _safe_eq(self, actual: Any, expected: Any) -> bool:
        if actual is None or expected is None:
            return actual == expected
        
        if isinstance(actual, str):
            actual = self._truncate(actual)
        if isinstance(expected, str):
            expected = self._truncate(expected)
        
        try:
            return actual == expected
        except (TypeError, ValueError):
            return str(actual) == str(expected)
    
    def _safe_lt(self, actual: Any, expected: Any) -> bool:
        try:
            actual_num = self._to_number(actual)
            expected_num = self._to_number(expected)
            return actual_num < expected_num
        except (TypeError, ValueError):
            return str(actual) < str(expected)
    
    def _safe_le(self, actual: Any, expected: Any) -> bool:
        try:
            actual_num = self._to_number(actual)
            expected_num = self._to_number(expected)
            return actual_num <= expected_num
        except (TypeError, ValueError):
            return str(actual) <= str(expected)
    
    def _safe_gt(self, actual: Any, expected: Any) -> bool:
        try:
            actual_num = self._to_number(actual)
            expected_num = self._to_number(expected)
            return actual_num > expected_num
        except (TypeError, ValueError):
            return str(actual) > str(expected)
    
    def _safe_ge(self, actual: Any, expected: Any) -> bool:
        try:
            actual_num = self._to_number(actual)
            expected_num = self._to_number(expected)
            return actual_num >= expected_num
        except (TypeError, ValueError):
            return str(actual) >= str(expected)
    
    def _safe_contains(self, actual: Any, expected: Any) -> bool:
        if not isinstance(actual, (str, list, tuple, set)):
            raise TypeError(f"Cannot check contains on type: {type(actual)}")
        
        actual_str = str(actual) if not isinstance(actual, str) else actual
        expected_str = str(expected)
        
        if len(actual_str) > self._max_string_length:
            actual_str = actual_str[:self._max_string_length]
        if len(expected_str) > self._max_string_length:
            expected_str = expected_str[:self._max_string_length]
        
        return expected_str in actual_str
    
    def _safe_starts_with(self, actual: Any, expected: Any) -> bool:
        actual_str = str(actual)
        expected_str = str(expected)
        
        if len(actual_str) > self._max_string_length:
            actual_str = actual_str[:self._max_string_length]
        if len(expected_str) > self._max_string_length:
            expected_str = expected_str[:self._max_string_length]
        
        return actual_str.startswith(expected_str)
    
    def _safe_ends_with(self, actual: Any, expected: Any) -> bool:
        actual_str = str(actual)
        expected_str = str(expected)
        
        if len(actual_str) > self._max_string_length:
            actual_str = actual_str[:self._max_string_length]
        if len(expected_str) > self._max_string_length:
            expected_str = expected_str[:self._max_string_length]
        
        return actual_str.endswith(expected_str)
    
    def _to_number(self, value: Any) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            value = value.strip()
            try:
                return float(value)
            except ValueError:
                raise ValueError(f"Cannot convert to number: {value}")
        
        raise TypeError(f"Cannot convert {type(value)} to number")
    
    def _truncate(self, s: str) -> str:
        return s[:self._max_string_length] if len(s) > self._max_string_length else s
    
    def evaluate_step(self, step: ConditionalStep, context: dict[str, Any]) -> tuple[str, Optional[str]]:
        if not isinstance(step, ConditionalStep):
            raise TypeError("Step must be a ConditionalStep instance")
        
        condition_met = self.evaluate(step.condition, context)
        
        if condition_met:
            return step.then_action, None
        else:
            if step.else_action:
                return step.else_action, step.else_step_id
            return "skip", None
