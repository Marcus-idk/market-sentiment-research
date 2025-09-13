"""
Tests for GeminiSettings configuration.
Tests environment variable loading and validation.
"""

import pytest
from config.llm.gemini import GeminiSettings
from config.retry import DEFAULT_LLM_RETRY

class TestGeminiSettings:
    """Test GeminiSettings.from_env() method"""
    
    def test_from_env_success(self, monkeypatch):
        """Test successful loading when GEMINI_API_KEY is set"""
        monkeypatch.setenv('GEMINI_API_KEY', 'AIzaSyTest123456789')
        
        settings = GeminiSettings.from_env()
        
        assert settings.api_key == 'AIzaSyTest123456789'
        assert settings.retry_config == DEFAULT_LLM_RETRY
    
    def test_from_env_missing_key(self, monkeypatch):
        """Test raises ValueError when GEMINI_API_KEY is not set"""
        monkeypatch.delenv('GEMINI_API_KEY', raising=False)
        
        with pytest.raises(ValueError) as exc_info:
            GeminiSettings.from_env()
        
        assert 'GEMINI_API_KEY environment variable not found or empty' in str(exc_info.value)
    
    def test_from_env_empty_key(self, monkeypatch):
        """Test raises ValueError when GEMINI_API_KEY is empty string"""
        monkeypatch.setenv('GEMINI_API_KEY', '')
        
        with pytest.raises(ValueError) as exc_info:
            GeminiSettings.from_env()
        
        assert 'GEMINI_API_KEY environment variable not found or empty' in str(exc_info.value)
    
    def test_from_env_whitespace_key(self, monkeypatch):
        """Test raises ValueError when GEMINI_API_KEY is only whitespace"""
        monkeypatch.setenv('GEMINI_API_KEY', '   ')
        
        with pytest.raises(ValueError) as exc_info:
            GeminiSettings.from_env()
        
        assert 'GEMINI_API_KEY environment variable not found or empty' in str(exc_info.value)
    
    def test_from_env_strips_whitespace(self, monkeypatch):
        """Test that whitespace is stripped from API key (no case changes)"""
        monkeypatch.setenv('GEMINI_API_KEY', '  key-with-spaces  ')

        settings = GeminiSettings.from_env()

        assert settings.api_key == 'key-with-spaces'
    
    def test_from_env_custom_env_dict(self):
        """Test using custom environment dictionary instead of os.environ"""
        custom_env = {'GEMINI_API_KEY': 'AIza-custom-key'}
        
        settings = GeminiSettings.from_env(env=custom_env)
        
        assert settings.api_key == 'AIza-custom-key'
        assert settings.retry_config == DEFAULT_LLM_RETRY
