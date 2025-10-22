"""
Unified shared behavior tests for all settings classes (data providers + LLM providers).

These tests verify that all settings (Finnhub, Polygon, OpenAI, Gemini)
follow the same environment loading and validation behavior.

To add a new provider: add its spec to the settings_spec fixture params below.
"""

import pytest
from config.providers.finnhub import FinnhubSettings
from config.providers.polygon import PolygonSettings
from config.llm.openai import OpenAISettings
from config.llm.gemini import GeminiSettings
from config.retry import DEFAULT_DATA_RETRY, DEFAULT_LLM_RETRY

# Unified parametrization for all 4 providers (2 data + 2 LLM)
@pytest.fixture(params=[
    pytest.param(
        ('finnhub', FinnhubSettings, 'FINNHUB_API_KEY', DEFAULT_DATA_RETRY, {'base_url': 'https://finnhub.io/api/v1'}, 'is empty or whitespace'),
        id='finnhub'
    ),
    pytest.param(
        ('polygon', PolygonSettings, 'POLYGON_API_KEY', DEFAULT_DATA_RETRY, {'base_url': 'https://api.polygon.io'}, 'is empty or whitespace'),
        id='polygon'
    ),
    pytest.param(
        ('openai', OpenAISettings, 'OPENAI_API_KEY', DEFAULT_LLM_RETRY, {}, 'not found or empty'),
        id='openai'
    ),
    pytest.param(
        ('gemini', GeminiSettings, 'GEMINI_API_KEY', DEFAULT_LLM_RETRY, {}, 'not found or empty'),
        id='gemini'
    )
])

def settings_spec(request):
    """Fixture providing specs for each provider (data + LLM)"""
    name, settings_cls, env_var, default_retry, expected_fields, whitespace_err = request.param
    return {
        'name': name,
        'settings_cls': settings_cls,
        'env_var_name': env_var,
        'default_retry': default_retry,
        'expected_fields': expected_fields,
        'whitespace_err': whitespace_err
    }


class TestSettingsShared:
    """Unified shared behavior tests for all settings classes"""

    def test_from_env_success(self, settings_spec, monkeypatch):
        """Test successful loading when API key is set"""
        monkeypatch.setenv(settings_spec['env_var_name'], 'test_key_123')

        settings = settings_spec['settings_cls'].from_env()

        assert settings.api_key == 'test_key_123'
        assert settings.retry_config == settings_spec['default_retry']

        # Check expected fields (like base_url for data providers)
        for field_name, expected_value in settings_spec['expected_fields'].items():
            assert getattr(settings, field_name) == expected_value

    def test_from_env_missing_key(self, settings_spec, monkeypatch):
        """Test raises ValueError when API key is not set"""
        monkeypatch.delenv(settings_spec['env_var_name'], raising=False)

        with pytest.raises(ValueError) as exc_info:
            settings_spec['settings_cls'].from_env()

        assert f'{settings_spec["env_var_name"]} environment variable not found or empty' in str(exc_info.value)

    def test_from_env_empty_key(self, settings_spec, monkeypatch):
        """Test raises ValueError when API key is empty string"""
        monkeypatch.setenv(settings_spec['env_var_name'], '')

        with pytest.raises(ValueError) as exc_info:
            settings_spec['settings_cls'].from_env()

        assert f'{settings_spec["env_var_name"]} environment variable not found or empty' in str(exc_info.value)

    def test_from_env_whitespace_key(self, settings_spec, monkeypatch):
        """Test raises ValueError when API key is only whitespace"""
        monkeypatch.setenv(settings_spec['env_var_name'], '   ')

        with pytest.raises(ValueError) as exc_info:
            settings_spec['settings_cls'].from_env()

        assert f'{settings_spec["env_var_name"]} environment variable {settings_spec["whitespace_err"]}' in str(exc_info.value)

    def test_from_env_strips_whitespace(self, settings_spec, monkeypatch):
        """Test that whitespace is stripped from API key"""
        monkeypatch.setenv(settings_spec['env_var_name'], '  test_key_with_spaces  ')

        settings = settings_spec['settings_cls'].from_env()

        assert settings.api_key == 'test_key_with_spaces'

    def test_from_env_custom_env_dict(self, settings_spec):
        """Test using custom environment dictionary instead of os.environ"""
        custom_env = {settings_spec['env_var_name']: 'custom_key'}

        settings = settings_spec['settings_cls'].from_env(env=custom_env)

        assert settings.api_key == 'custom_key'
        assert settings.retry_config == settings_spec['default_retry']

        # Check expected fields
        for field_name, expected_value in settings_spec['expected_fields'].items():
            assert getattr(settings, field_name) == expected_value
