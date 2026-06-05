import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from plasmaagent.agent.config_manager import (
    get_default_model,
    set_default_model,
    get_config_value,
    set_config_value,
    get_full_config,
)


class TestConfigManager:
    @pytest.fixture
    def temp_config(self, tmp_path):
        config_file = tmp_path / "config.json"
        with patch("plasmaagent.agent.config_manager._CONFIG_FILE", config_file):
            yield config_file

    def test_get_default_model_no_file(self, temp_config):
        assert get_default_model() is None

    def test_set_and_get_default_model(self, temp_config):
        set_default_model("qwen2.5-coder:7b")
        assert get_default_model() == "qwen2.5-coder:7b"

    def test_overwrite_default_model(self, temp_config):
        set_default_model("model-a")
        set_default_model("model-b")
        assert get_default_model() == "model-b"

    def test_set_config_value(self, temp_config):
        set_config_value("ollama_url", "http://localhost:11434")
        assert get_config_value("ollama_url") == "http://localhost:11434"

    def test_get_config_value_default(self, temp_config):
        assert get_config_value("nonexistent", "default") == "default"

    def test_get_full_config(self, temp_config):
        set_default_model("test-model")
        set_config_value("key1", "value1")
        config = get_full_config()
        assert config["default_model"] == "test-model"
        assert config["key1"] == "value1"

    def test_corrupted_config_returns_empty(self, temp_config):
        temp_config.parent.mkdir(parents=True, exist_ok=True)
        temp_config.write_text("not valid json{{{", encoding="utf-8")
        assert get_default_model() is None
        assert get_full_config() == {}

    def test_persistence_across_calls(self, temp_config):
        set_default_model("persistent-model")
        assert get_default_model() == "persistent-model"
        assert get_default_model() == "persistent-model"
        set_config_value("counter", 42)
        assert get_config_value("counter") == 42
