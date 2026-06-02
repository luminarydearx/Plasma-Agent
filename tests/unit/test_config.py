"""Unit tests for configuration module."""

import os

import pytest

from plasmaagent.core.config import Settings, get_settings


class TestSettings:
    """Test configuration settings."""

    def test_default_settings(self):
        """Test default settings values."""
        settings = Settings()
        assert settings.app_name == "PlasmaAgent"
        assert settings.app_version == "0.1.0"
        assert settings.debug is False
        assert settings.log_level == "INFO"
        assert settings.database_pool_size == 10

    def test_database_url_default(self):
        """Test default database URL."""
        settings = Settings()
        assert "postgresql" in settings.database_url
        assert "plasmaagent" in settings.database_url

    def test_is_debug_property(self):
        """Test is_debug property."""
        settings = Settings(debug=True)
        assert settings.is_debug is True

        settings = Settings(debug=False)
        assert settings.is_debug is False

    def test_environment_override(self, monkeypatch):
        """Test environment variable override."""
        monkeypatch.setenv("APP_NAME", "TestApp")
        monkeypatch.setenv("DEBUG", "true")
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        settings = Settings()
        assert settings.app_name == "TestApp"
        assert settings.debug is True
        assert settings.log_level == "DEBUG"


def test_get_settings_cached():
    """Test that get_settings returns cached instance."""
    settings1 = get_settings()
    settings2 = get_settings()
    assert settings1 is settings2
