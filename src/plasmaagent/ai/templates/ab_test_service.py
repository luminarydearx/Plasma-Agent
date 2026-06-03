import math
import random
from datetime import datetime, timezone
from typing import Optional, List
from plasmaagent.core.database import Database
from plasmaagent.ai.templates.ab_testing import (
    ABTest, ABTestCreate, ABTestResult, ABTestStats, ABTestAnalysis
)


class ABTestService:
    def __init__(self, db: Database):
        self._db = db

    async def create_test(self, test: ABTestCreate) -> ABTest:
        async with self._db.transaction() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO ab_tests (template_name, version_a_id, version_b_id, 
                                     confidence_threshold, min_samples, status)
                VALUES (%s, %s, %s, %s, %s, 'active')
                RETURNING id, template_name, version_a_id, version_b_id, status,
                         started_at, ended_at, winner_version_id, 
                         confidence_threshold, min_samples
                """,
                (test.template_name, test.version_a_id, test.version_b_id,
                 test.confidence_threshold, test.min_samples)
            )
            row = await cursor.fetchone()
            return self._row_to_test(row)

    async def serve_version(self, test_id: int) -> Optional[int]:
        test = await self.get_test(test_id)
        if not test or test.status != 'active':
            return None
        return test.version_a_id if random.random() < 0.5 else test.version_b_id

    async def record_result(
        self,
        ab_test_id: int,
        version_id: int,
        success: bool,
        execution_time_ms: int
    ) -> ABTestResult:
        async with self._db.transaction() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO ab_test_results (ab_test_id, version_id, success, execution_time_ms)
                VALUES (%s, %s, %s, %s)
                RETURNING id, ab_test_id, version_id, success, execution_time_ms, created_at
                """,
                (ab_test_id, version_id, success, execution_time_ms)
            )
            row = await cursor.fetchone()
            return self._row_to_result(row)

    async def get_test(self, test_id: int) -> Optional[ABTest]:
        async with self._db.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, template_name, version_a_id, version_b_id, status,
                       started_at, ended_at, winner_version_id, 
                       confidence_threshold, min_samples
                FROM ab_tests
                WHERE id = %s
                """,
                (test_id,)
            )
            row = await cursor.fetchone()
            return self._row_to_test(row) if row else None

    async def list_active_tests(self, limit: int = 50, offset: int = 0) -> List[ABTest]:
        async with self._db.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, template_name, version_a_id, version_b_id, status,
                       started_at, ended_at, winner_version_id, 
                       confidence_threshold, min_samples
                FROM ab_tests
                WHERE status = 'active'
                ORDER BY started_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset)
            )
            rows = await cursor.fetchall()
            return [self._row_to_test(row) for row in rows]

    async def get_version_stats(self, ab_test_id: int, version_id: int) -> ABTestStats:
        async with self._db.connection() as conn:
            cursor = await conn.execute(
                """
                SELECT 
                    COUNT(*) as total_samples,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes,
                    SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failures,
                    AVG(execution_time_ms) as avg_execution_time_ms
                FROM ab_test_results
                WHERE ab_test_id = %s AND version_id = %s
                """,
                (ab_test_id, version_id)
            )
            row = await cursor.fetchone()
            
            total = row['total_samples'] or 0
            successes = row['successes'] or 0
            failures = row['failures'] or 0
            success_rate = successes / total if total > 0 else 0.0
            avg_time = float(row['avg_execution_time_ms'] or 0.0)
            
            confidence_interval = self._calculate_confidence_interval(successes, total)
            
            return ABTestStats(
                version_id=version_id,
                total_samples=total,
                successes=successes,
                failures=failures,
                success_rate=success_rate,
                avg_execution_time_ms=avg_time,
                confidence_interval=confidence_interval
            )

    async def analyze_test(self, test_id: int) -> Optional[ABTestAnalysis]:
        test = await self.get_test(test_id)
        if not test:
            return None
        
        stats_a = await self.get_version_stats(test_id, test.version_a_id)
        stats_b = await self.get_version_stats(test_id, test.version_b_id)
        
        winner_id = None
        confidence = 0.0
        is_significant = False
        recommendation = "Insufficient data"
        
        if stats_a.total_samples >= test.min_samples and stats_b.total_samples >= test.min_samples:
            z_score = self._calculate_z_score(
                stats_a.successes, stats_a.total_samples,
                stats_b.successes, stats_b.total_samples
            )
            confidence = self._z_to_confidence(z_score)
            is_significant = confidence >= test.confidence_threshold
            
            if is_significant:
                if stats_a.success_rate > stats_b.success_rate:
                    winner_id = test.version_a_id
                    recommendation = f"Version A wins with {stats_a.success_rate:.2%} success rate"
                else:
                    winner_id = test.version_b_id
                    recommendation = f"Version B wins with {stats_b.success_rate:.2%} success rate"
            else:
                recommendation = f"Continue testing (confidence: {confidence:.2%})"
        
        return ABTestAnalysis(
            ab_test_id=test_id,
            template_name=test.template_name,
            version_a_stats=stats_a,
            version_b_stats=stats_b,
            winner_version_id=winner_id,
            confidence=confidence,
            is_significant=is_significant,
            recommendation=recommendation
        )

    async def auto_complete_if_significant(self, test_id: int) -> Optional[ABTest]:
        analysis = await self.analyze_test(test_id)
        if not analysis or not analysis.is_significant or not analysis.winner_version_id:
            return None
        return await self.complete_test(test_id, analysis.winner_version_id)

    async def complete_test(self, test_id: int, winner_version_id: int) -> Optional[ABTest]:
        async with self._db.transaction() as conn:
            cursor = await conn.execute(
                """
                UPDATE ab_tests
                SET status = 'completed', 
                    ended_at = NOW(),
                    winner_version_id = %s
                WHERE id = %s AND status = 'active'
                RETURNING id, template_name, version_a_id, version_b_id, status,
                         started_at, ended_at, winner_version_id, 
                         confidence_threshold, min_samples
                """,
                (winner_version_id, test_id)
            )
            row = await cursor.fetchone()
            return self._row_to_test(row) if row else None

    async def cancel_test(self, test_id: int) -> Optional[ABTest]:
        async with self._db.transaction() as conn:
            cursor = await conn.execute(
                """
                UPDATE ab_tests
                SET status = 'cancelled', ended_at = NOW()
                WHERE id = %s AND status = 'active'
                RETURNING id, template_name, version_a_id, version_b_id, status,
                         started_at, ended_at, winner_version_id, 
                         confidence_threshold, min_samples
                """,
                (test_id,)
            )
            row = await cursor.fetchone()
            return self._row_to_test(row) if row else None

    def _calculate_confidence_interval(self, successes: int, total: int) -> float:
        if total == 0:
            return 0.0
        p = successes / total
        z = 1.96
        margin = z * math.sqrt((p * (1 - p)) / total)
        return margin

    def _calculate_z_score(
        self,
        successes_a: int, total_a: int,
        successes_b: int, total_b: int
    ) -> float:
        if total_a == 0 or total_b == 0:
            return 0.0
        
        p_a = successes_a / total_a
        p_b = successes_b / total_b
        p_pool = (successes_a + successes_b) / (total_a + total_b)
        
        se = math.sqrt(p_pool * (1 - p_pool) * (1/total_a + 1/total_b))
        
        if se == 0:
            return 0.0
        
        return abs(p_a - p_b) / se

    def _z_to_confidence(self, z: float) -> float:
        if z >= 3.29:
            return 0.999
        elif z >= 2.58:
            return 0.99
        elif z >= 1.96:
            return 0.95
        elif z >= 1.64:
            return 0.90
        elif z >= 1.28:
            return 0.80
        else:
            return 0.50 + (z * 0.20)

    def _row_to_test(self, row) -> ABTest:
        return ABTest(
            id=row['id'],
            template_name=row['template_name'],
            version_a_id=row['version_a_id'],
            version_b_id=row['version_b_id'],
            status=row['status'],
            started_at=row['started_at'],
            ended_at=row['ended_at'],
            winner_version_id=row['winner_version_id'],
            confidence_threshold=row['confidence_threshold'],
            min_samples=row['min_samples']
        )

    def _row_to_result(self, row) -> ABTestResult:
        return ABTestResult(
            id=row['id'],
            ab_test_id=row['ab_test_id'],
            version_id=row['version_id'],
            success=row['success'],
            execution_time_ms=row['execution_time_ms'],
            created_at=row['created_at']
        )
