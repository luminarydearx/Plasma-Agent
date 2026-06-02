import pytest
from unittest.mock import Mock, AsyncMock
from plasmaagent.services.task_generator import TaskGeneratorService
from plasmaagent.ai.models import GeneratedTask, TaskComplexity
from plasmaagent.core.database import Database

class TestTaskGeneratorServiceInit:
    def test_init_with_database(self):
        mock_db = Mock(spec=Database)
        service = TaskGeneratorService(mock_db)
        assert service._db == mock_db

class TestTaskGeneratorServiceGeneration:
    @pytest.fixture
    def service(self):
        mock_db = Mock(spec=Database)
        return TaskGeneratorService(mock_db)

    @pytest.mark.asyncio
    async def test_generate_valid_input(self, service):
        response = await service.generate_from_natural_language("backup database postgresql mydb")
        assert response is not None
        assert len(response.tasks) > 0

    @pytest.mark.asyncio
    async def test_generate_empty_input(self, service):
        response = await service.generate_from_natural_language("")
        assert response is not None

    @pytest.mark.asyncio
    async def test_generate_no_pattern_match(self, service):
        response = await service.generate_from_natural_language("xyz123 random gibberish")
        assert response is not None

class TestTaskGeneratorServiceCreate:
    @pytest.fixture
    def service(self):
        mock_db = Mock(spec=Database)
        return TaskGeneratorService(mock_db)

    @pytest.mark.asyncio
    async def test_create_valid_generated_task(self, service):
        generated = GeneratedTask(
            name="Backup",
            description="Backup DB",
            commands=["pg_dump mydb > backup.sql"],
            complexity=TaskComplexity.SIMPLE,
            confidence=0.95,
        )
        import uuid
        mock_task = Mock()
        mock_task.id = uuid.uuid4()
        service._task_service.create_task = AsyncMock(return_value=mock_task)
        task_id = await service.create_task_from_generation(generated)
        assert task_id is not None

class TestTaskGeneratorServicePreview:
    @pytest.fixture
    def service(self):
        mock_db = Mock(spec=Database)
        return TaskGeneratorService(mock_db)

    def test_preview_simple_task(self, service):
        generated = GeneratedTask(
            name="Backup",
            description="Backup DB",
            commands=["pg_dump mydb"],
            complexity=TaskComplexity.SIMPLE,
            confidence=0.95,
        )
        preview = service.preview_task(generated)
        assert "Backup" in preview
        assert "pg_dump" in preview

class TestTaskGeneratorServiceProviders:
    @pytest.fixture
    def service(self):
        mock_db = Mock(spec=Database)
        return TaskGeneratorService(mock_db)

    def test_get_available_providers(self, service):
        providers = service.get_available_providers()
        assert isinstance(providers, list)
        assert "rule_based" in providers

class TestTaskGeneratorServicePerformance:
    @pytest.fixture
    def service(self):
        mock_db = Mock(spec=Database)
        return TaskGeneratorService(mock_db)

    @pytest.mark.asyncio
    async def test_generation_speed(self, service):
        import time
        start = time.time()
        response = await service.generate_from_natural_language("backup database postgresql mydb")
        elapsed = time.time() - start
        assert elapsed < 0.1
        assert response is not None
