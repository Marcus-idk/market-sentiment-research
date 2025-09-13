"""
Tests for OpenAISettings configuration.
Tests environment variable loading and validation.
"""

import pytest
from config.llm.openai import OpenAISettings
from config.retry import DEFAULT_LLM_RETRY


class TestOpenAISettings:
    """Test OpenAISettings.from_env() method"""
    
    def test_from_env_success(self, monkeypatch):
        """Test successful loading when OPENAI_API_KEY is set"""
        monkeypatch.setenv('OPENAI_API_KEY', 'sk-test123456789')
        
        settings = OpenAISettings.from_env()
        
        assert settings.api_key == 'sk-test123456789'
        assert settings.retry_config == DEFAULT_LLM_RETRY
    
    def test_from_env_missing_key(self, monkeypatch):
        """Test raises ValueError when OPENAI_API_KEY is not set"""
        monkeypatch.delenv('OPENAI_API_KEY', raising=False)
        
        with pytest.raises(ValueError) as exc_info:
            OpenAISettings.from_env()
        
        assert 'OPENAI_API_KEY environment variable not found or empty' in str(exc_info.value)
    
    def test_from_env_empty_key(self, monkeypatch):
        """Test raises ValueError when OPENAI_API_KEY is empty string"""
        monkeypatch.setenv('OPENAI_API_KEY', '')
        
        with pytest.raises(ValueError) as exc_info:
            OpenAISettings.from_env()
        
        assert 'OPENAI_API_KEY environment variable not found or empty' in str(exc_info.value)
    
    def test_from_env_whitespace_key(self, monkeypatch):
        """Test raises ValueError when OPENAI_API_KEY is only whitespace"""
        monkeypatch.setenv('OPENAI_API_KEY', '   ')
        
        with pytest.raises(ValueError) as exc_info:
            OpenAISettings.from_env()
        
        assert 'OPENAI_API_KEY environment variable not found or empty' in str(exc_info.value)
    
    def test_from_env_strips_whitespace(self, monkeypatch):
        """Test that whitespace is stripped from API key"""
        monkeypatch.setenv('OPENAI_API_KEY', '  sk-key-with-spaces  ')
        
        settings = OpenAISettings.from_env()
        
        assert settings.api_key == 'sk-key-with-spaces'
    
    def test_from_env_custom_env_dict(self):
        """Test using custom environment dictionary instead of os.environ"""
        custom_env = {'OPENAI_API_KEY': 'sk-custom-key'}
        
        settings = OpenAISettings.from_env(env=custom_env)
        
        assert settings.api_key == 'sk-custom-key'
        assert settings.retry_config == DEFAULT_LLM_RETRY