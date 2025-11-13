"""Configuration management for the application."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""
    
    # LLM Provider Configuration
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "gemini").lower()  # "gemini" or "openai"
    
    # Gemini Configuration (required for embedding, optional for LLM)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # OpenAI Configuration (required if LLM_PROVIDER=openai)
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Pinecone Configuration
    PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
    PINECONE_ENVIRONMENT: str = os.getenv("PINECONE_ENVIRONMENT", "")
    PINECONE_INDEX_NAME: str = os.getenv("PINECONE_INDEX_NAME", "")
    
    # API Configuration
    API_TITLE: str = os.getenv("API_TITLE", "AI Menu Suggestion API")
    API_VERSION: str = os.getenv("API_VERSION", "1.0.0")
    API_DESCRIPTION: str = os.getenv(
        "API_DESCRIPTION",
        "AI-powered menu suggestion system using LangGraph and Pinecone"
    )
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    
    @classmethod
    def validate(cls) -> None:
        """Validate that all required configuration is present."""
        # GEMINI_API_KEY is always required for embedding
        if not cls.GEMINI_API_KEY:
            raise ValueError("Missing GEMINI_API_KEY (required for embedding)")
        
        # Validate LLM provider specific keys
        if cls.LLM_PROVIDER == "openai":
            if not cls.OPENAI_API_KEY:
                raise ValueError("Missing OPENAI_API_KEY (required when LLM_PROVIDER=openai)")
        elif cls.LLM_PROVIDER == "gemini":
            if not cls.GEMINI_API_KEY:
                raise ValueError("Missing GEMINI_API_KEY (required when LLM_PROVIDER=gemini)")
        else:
            raise ValueError(f"Invalid LLM_PROVIDER: {cls.LLM_PROVIDER}. Must be 'gemini' or 'openai'")
        
        if not cls.PINECONE_API_KEY:
            raise ValueError("Missing PINECONE_API_KEY")
        
        if not cls.PINECONE_INDEX_NAME:
            raise ValueError("Missing PINECONE_INDEX_NAME")


config = Config()

