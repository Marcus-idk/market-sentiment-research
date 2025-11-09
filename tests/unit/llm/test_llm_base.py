"""LLM provider base class contracts and exceptions."""

import pytest

from llm.base import LLMError, LLMProvider


class TestLLMProviderInitialization:
    """Test LLMProvider.__init__ config storage"""

    def test_llmprovider_stores_config_kwargs(self):
        """Test that __init__ stores arbitrary kwargs in config"""

        class ConcreteLLM(LLMProvider):
            async def generate(self, prompt: str) -> str:
                return "test"

            async def validate_connection(self) -> bool:
                return True

        provider = ConcreteLLM(model="gpt-4", temperature=0.7, max_tokens=100)

        assert provider.config == {"model": "gpt-4", "temperature": 0.7, "max_tokens": 100}


class TestAbstractMethodEnforcement:
    """Test that abstract methods are properly enforced"""

    def test_llmprovider_cannot_instantiate(self):
        """Test that LLMProvider ABC cannot be instantiated directly"""
        with pytest.raises(TypeError, match="Can't instantiate abstract class LLMProvider"):
            LLMProvider()  # type: ignore[reportAbstractUsage]

    def test_llmprovider_requires_generate(self):
        """Test that subclass without generate() cannot be instantiated"""
        with pytest.raises(TypeError, match="Can't instantiate abstract class.*generate"):

            class IncompleteProvider(LLMProvider):
                async def validate_connection(self) -> bool:
                    return True

            IncompleteProvider()  # type: ignore[reportAbstractUsage]

    def test_llmprovider_requires_validate_connection(self):
        """Test that subclass without validate_connection() cannot be instantiated"""
        with pytest.raises(
            TypeError, match="Can't instantiate abstract class.*validate_connection"
        ):

            class IncompleteProvider(LLMProvider):
                async def generate(self, prompt: str) -> str:
                    return "test"

            IncompleteProvider()  # type: ignore[reportAbstractUsage]

    def test_concrete_implementation_works(self):
        """Test that complete implementation can be instantiated"""

        class CompleteLLM(LLMProvider):
            async def generate(self, prompt: str) -> str:
                return f"Generated: {prompt}"

            async def validate_connection(self) -> bool:
                return True

        provider = CompleteLLM(model="test-model")
        assert provider.config == {"model": "test-model"}


class TestExceptionHierarchy:
    """Test LLMError exception hierarchy"""

    def test_llm_error_inheritance(self):
        """Test that LLMError inherits from Exception"""
        assert issubclass(LLMError, Exception)

        error = LLMError("Test error")
        assert isinstance(error, LLMError)
        assert isinstance(error, Exception)
