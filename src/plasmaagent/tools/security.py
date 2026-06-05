"""Security audit tools for PlasmaAgent."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolResult:
    success: bool
    output: str
    data: Any = None


async def security_audit(project_path: str, file_extensions: list[str] | None = None) -> ToolResult:
    try:
        from plasmaagent.security.audit_tool import SecurityAuditor
        
        auditor = SecurityAuditor()
        report = await auditor.audit_project(project_path, file_extensions)
        
        report_dict = report.to_dict()
        
        output_lines = [
            f"🔍 Security Audit Report",
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"Project: {report.project_path}",
            f"Files Scanned: {report.total_files}",
            f"Security Score: {report.score}/100",
            f"Vulnerabilities Found: {len(report.vulnerabilities)}",
            f"",
            f"By Severity:",
            f"  • CRITICAL: {report_dict['by_severity']['critical']}",
            f"  • HIGH: {report_dict['by_severity']['high']}",
            f"  • MEDIUM: {report_dict['by_severity']['medium']}",
            f"  • LOW: {report_dict['by_severity']['low']}",
            f"",
        ]
        
        if report.vulnerabilities:
            output_lines.append("Top Vulnerabilities:")
            for i, vuln in enumerate(report.vulnerabilities[:10], 1):
                output_lines.extend([
                    f"",
                    f"{i}. [{vuln.severity}] {vuln.category}",
                    f"   File: {vuln.file}:{vuln.line}",
                    f"   {vuln.description[:100]}",
                    f"   → {vuln.recommendation}",
                ])
        
        return ToolResult(
            True,
            "\n".join(output_lines),
            report_dict,
        )
    except Exception as e:
        return ToolResult(False, f"Security audit failed: {e}")
