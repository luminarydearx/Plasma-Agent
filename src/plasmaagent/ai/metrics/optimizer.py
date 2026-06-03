from typing import Any

from plasmaagent.ai.metrics.tracker import ExecutionMetricsTracker


class TemplateOptimizer:
    """Analyze execution metrics and suggest template improvements."""

    def __init__(self, tracker: ExecutionMetricsTracker):
        self._tracker = tracker

    async def analyze_template(self, template_name: str) -> dict[str, Any]:
        stats = await self._tracker.get_template_stats(template_name)
        
        if stats["total_executions"] == 0:
            return {
                "template_name": template_name,
                "status": "no_data",
                "message": "No execution data available",
                "recommendations": [],
            }

        patterns = await self._tracker.get_failure_patterns(template_name, limit=5)
        slow_executions = await self._tracker.get_slow_executions(
            threshold_ms=10000, limit=5
        )

        recommendations = self._generate_recommendations(stats, patterns, slow_executions)

        return {
            "template_name": template_name,
            "status": "analyzed",
            "stats": stats,
            "top_failures": patterns[:3],
            "slow_executions_count": len(slow_executions),
            "recommendations": recommendations,
        }

    def _generate_recommendations(
        self,
        stats: dict[str, Any],
        patterns: list[dict[str, Any]],
        slow_executions: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        recommendations = []

        if stats["success_rate"] < 0.5 and stats["total_executions"] >= 5:
            recommendations.append({
                "type": "critical",
                "issue": f"Low success rate: {stats['success_rate'] * 100:.1f}%",
                "suggestion": "Review template commands and error handling",
            })
        elif stats["success_rate"] < 0.8 and stats["total_executions"] >= 5:
            recommendations.append({
                "type": "warning",
                "issue": f"Below-average success rate: {stats['success_rate'] * 100:.1f}%",
                "suggestion": "Consider improving error handling or adding validation",
            })

        if patterns:
            top_error = patterns[0]
            recommendations.append({
                "type": "error_pattern",
                "issue": f"Common error: '{top_error['error_message']}' ({top_error['occurrence_count']}x)",
                "suggestion": "Add specific error handling for this error type",
            })

        if stats["avg_execution_time_ms"] > 30000:
            recommendations.append({
                "type": "performance",
                "issue": f"Slow execution: {stats['avg_execution_time_ms']}ms average",
                "suggestion": "Consider optimizing commands or breaking into smaller tasks",
            })

        if slow_executions:
            recommendations.append({
                "type": "performance",
                "issue": f"{len(slow_executions)} executions over 10 seconds",
                "suggestion": "Review slow executions for optimization opportunities",
            })

        if stats["total_executions"] >= 10 and stats["success_rate"] >= 0.95:
            recommendations.append({
                "type": "success",
                "issue": "High reliability template",
                "suggestion": "Template is performing well, consider as reference for others",
            })

        return recommendations

    async def get_optimization_report(self) -> dict[str, Any]:
        all_stats = await self._tracker.get_all_template_stats()
        
        if not all_stats:
            return {
                "status": "no_data",
                "message": "No execution metrics available",
                "templates": [],
            }

        problematic = []
        well_performing = []
        
        for stats in all_stats:
            if stats["total_executions"] < 3:
                continue

            analysis = await self.analyze_template(stats["template_name"])
            
            if stats["success_rate"] < 0.7 or stats["avg_execution_time_ms"] > 30000:
                problematic.append(analysis)
            elif stats["success_rate"] >= 0.9 and stats["avg_execution_time_ms"] < 10000:
                well_performing.append(analysis)

        return {
            "status": "analyzed",
            "total_templates": len(all_stats),
            "problematic_templates": problematic,
            "well_performing_templates": well_performing,
            "summary": {
                "needs_attention": len(problematic),
                "performing_well": len(well_performing),
            },
        }
