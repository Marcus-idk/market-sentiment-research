"""
Configuration settings for Finnhub API provider
"""
from dataclasses import dataclass
import os
from typing import Optional, Mapping

@dataclass(frozen=True)
class FinnhubSettings:
    """Configuration settings for Finnhub API integration"""
    
    api_key: str
    base_url: str = "https://finnhub.io/api/v1"
    timeout_seconds: int = 30
    max_retries: int = 3
    
    @staticmethod
    def from_env(env: Optional[Mapping[str, str]] = None) -> 'FinnhubSettings':
        """
        Create FinnhubSettings from environment variables
        
        Args:
            env: Optional environment dict (defaults to os.environ)
            
        Returns:
            FinnhubSettings instance
            
        Raises:
            ValueError: If FINNHUB_API_KEY is not found or empty
        """
        if env is None:
            env = os.environ
            
        api_key = env.get('FINNHUB_API_KEY')
        if not api_key:
            raise ValueError("FINNHUB_API_KEY environment variable not found or empty")
        
        api_key = api_key.strip()
        if not api_key:
            raise ValueError("FINNHUB_API_KEY environment variable is empty or whitespace")
            
        return FinnhubSettings(api_key=api_key)
