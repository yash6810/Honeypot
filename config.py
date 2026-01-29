"""
Configuration Manager for Honeypot Agent
=========================================

This module loads and validates all configuration from environment variables.
It provides a centralized settings object used throughout the application.

Usage:
    from config import settings
    
    api_key = settings.GEMINI_API_KEY
    max_turns = settings.MAX_CONVERSATION_TURNS

Environment Variables:
    All configuration is loaded from .env file or environment.
    See .env.example for complete list of available settings.

Author: Honeypot Agent Team
Date: January 2026
"""

import os
import sys
from typing import Literal, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
# This must happen before we try to access any environment variables
load_dotenv()


class Settings:
    """
    Application settings loaded from environment variables.
    
    This class provides type-safe access to all configuration values
    with validation and helpful error messages.
    
    Attributes:
        AI_PROVIDER: Which AI service to use ("gemini" or "groq")
        GEMINI_API_KEY: Google Gemini API key
        GROQ_API_KEY: Groq API key  
        API_SECRET_KEY: Secret key for authenticating incoming requests
        GUVI_CALLBACK_URL: URL to send final results
        ENVIRONMENT: Current environment (development/production)
        DEBUG: Enable debug mode
        LOG_LEVEL: Logging level
        MAX_CONVERSATION_TURNS: Max turns before ending conversation
        MIN_INTELLIGENCE_THRESHOLD: Min intelligence pieces needed
        API_TIMEOUT: Request timeout in seconds
    """
    
    def __init__(self):
        """Initialize settings by loading environment variables."""
        
        # =================================================================
        # AI Provider Configuration
        # =================================================================
        
        self.AI_PROVIDER: Literal["gemini", "groq"] = os.getenv(
            "AI_PROVIDER", "gemini"
        ).lower()
        
        self.GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
        self.GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
        
        # =================================================================
        # API Security
        # =================================================================
        
        self.API_SECRET_KEY: str = os.getenv(
            "API_SECRET_KEY",
            "CHANGE-THIS-TO-A-STRONG-RANDOM-STRING"
        )
        
        # =================================================================
        # GUVI Integration
        # =================================================================
        
        self.GUVI_CALLBACK_URL: str = os.getenv(
            "GUVI_CALLBACK_URL",
            "https://hackathon.guvi.in/api/updateHoneyPotFinalResult"
        )
        
        # =================================================================
        # Application Settings
        # =================================================================
        
        self.ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
        self.DEBUG: bool = os.getenv("DEBUG", "true").lower() in ("true", "1", "yes")
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
        
        # =================================================================
        # Agent Behavior
        # =================================================================
        
        self.MAX_CONVERSATION_TURNS: int = int(
            os.getenv("MAX_CONVERSATION_TURNS", "20")
        )
        
        self.MIN_INTELLIGENCE_THRESHOLD: int = int(
            os.getenv("MIN_INTELLIGENCE_THRESHOLD", "2")
        )
        
        self.STALE_CONVERSATION_THRESHOLD: int = int(
            os.getenv("STALE_CONVERSATION_THRESHOLD", "5")
        )
        
        # =================================================================
        # Performance Settings
        # =================================================================
        
        self.API_TIMEOUT: int = int(os.getenv("API_TIMEOUT", "30"))
        self.MAX_REQUESTS_PER_MINUTE: int = int(
            os.getenv("MAX_REQUESTS_PER_MINUTE", "60")
        )
        self.ENABLE_CACHING: bool = os.getenv(
            "ENABLE_CACHING", "true"
        ).lower() in ("true", "1", "yes")
        self.CACHE_TTL: int = int(os.getenv("CACHE_TTL", "300"))
        
        # =================================================================
        # Testing
        # =================================================================
        
        self.TEST_MODE: bool = os.getenv(
            "TEST_MODE", "false"
        ).lower() in ("true", "1", "yes")
        self.VERBOSE_LOGGING: bool = os.getenv(
            "VERBOSE_LOGGING", "false"
        ).lower() in ("true", "1", "yes")
        
        # Validate configuration after loading
        self._validate()
    
    def _validate(self):
        """
        Validate that all required configuration is present and correct.
        
        Raises:
            ValueError: If configuration is invalid or missing required values
        """
        errors = []
        warnings = []
        
        # ============================================================
        # Critical Validations (will cause startup failure)
        # ============================================================
        
        # Check AI provider is valid
        if self.AI_PROVIDER not in ["gemini", "groq"]:
            errors.append(
                f"❌ AI_PROVIDER must be 'gemini' or 'groq', got '{self.AI_PROVIDER}'"
            )
        
        # Check that the selected provider has an API key
        if self.AI_PROVIDER == "gemini" and not self.GEMINI_API_KEY:
            errors.append(
                "❌ GEMINI_API_KEY is required when AI_PROVIDER='gemini'\n"
                "   Get your free key from: https://aistudio.google.com/app/apikey"
            )
        
        if self.AI_PROVIDER == "groq" and not self.GROQ_API_KEY:
            errors.append(
                "❌ GROQ_API_KEY is required when AI_PROVIDER='groq'\n"
                "   Get your free key from: https://console.groq.com"
            )
        
        # Check API secret key was changed from default
        if self.API_SECRET_KEY == "CHANGE-THIS-TO-A-STRONG-RANDOM-STRING":
            errors.append(
                "❌ API_SECRET_KEY must be changed from the default value\n"
                "   Generate a strong key with:\n"
                "   python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        
        # ============================================================
        # Warning Validations (won't stop startup but should fix)
        # ============================================================
        
        # Warn if API secret key is too short
        if len(self.API_SECRET_KEY) < 20:
            warnings.append(
                "⚠️  API_SECRET_KEY is short (< 20 characters)\n"
                "   Consider using a longer, more secure key"
            )
        
        # Warn if no backup AI provider configured
        if self.AI_PROVIDER == "gemini" and not self.GROQ_API_KEY:
            warnings.append(
                "⚠️  No backup AI provider configured\n"
                "   Consider adding GROQ_API_KEY as fallback"
            )
        
        # Warn if timeout is very high
        if self.API_TIMEOUT > 60:
            warnings.append(
                f"⚠️  API_TIMEOUT is high ({self.API_TIMEOUT}s)\n"
                "   This may cause slow responses. Consider reducing to 30s"
            )
        
        # Warn if max turns is very high
        if self.MAX_CONVERSATION_TURNS > 30:
            warnings.append(
                f"⚠️  MAX_CONVERSATION_TURNS is high ({self.MAX_CONVERSATION_TURNS})\n"
                "   Long conversations may be inefficient. Consider 15-20 turns"
            )
        
        # ============================================================
        # Print Results
        # ============================================================
        
        # If there are errors, print them and exit
        if errors:
            print("\n" + "="*70)
            print("🚨 CONFIGURATION ERRORS - Cannot Start Application")
            print("="*70)
            for error in errors:
                print(f"\n{error}")
            print("\n" + "="*70)
            print("\n💡 Fix these issues in your .env file, then try again.\n")
            print("If .env doesn't exist, create it from .env.example:")
            print("   cp .env.example .env")
            print("="*70 + "\n")
            sys.exit(1)
        
        # If there are warnings, print them but continue
        if warnings:
            print("\n" + "="*70)
            print("⚠️  CONFIGURATION WARNINGS")
            print("="*70)
            for warning in warnings:
                print(f"\n{warning}")
            print("\n" + "="*70)
            print("\n💡 Application will start, but consider fixing these.\n")
    
    def get_ai_api_key(self) -> str:
        """
        Get the API key for the currently configured AI provider.
        
        Returns:
            str: The API key for the active provider
            
        Raises:
            ValueError: If provider is invalid or key is missing
        """
        if self.AI_PROVIDER == "gemini":
            return self.GEMINI_API_KEY
        elif self.AI_PROVIDER == "groq":
            return self.GROQ_API_KEY
        else:
            raise ValueError(f"Unknown AI provider: {self.AI_PROVIDER}")
    
    def get_ai_model_name(self) -> str:
        """
        Get the model name for the currently configured AI provider.
        
        Returns:
            str: Model identifier string
        """
        if self.AI_PROVIDER == "gemini":
            return "gemini-flash-latest"  # Fast and free
        elif self.AI_PROVIDER == "groq":
            return "llama3-70b-8192"  # Groq's Llama 3 70B model
        else:
            return "unknown"
    
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT.lower() == "production"
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT.lower() == "development"


# =================================================================
# Create Global Settings Instance
# =================================================================

# This settings object is imported throughout the application
# Configuration is loaded and validated once at startup
settings = Settings()


# =================================================================
# Helper Functions
# =================================================================

def print_config_summary(show_secrets: bool = False):
    """
    Print a summary of current configuration.
    
    Args:
        show_secrets: If True, show actual API keys (for debugging only!)
    """
    print("\n" + "="*70)
    print("🛡️  Honeypot Agent Configuration Summary")
    print("="*70)
    
    print(f"\n📍 Environment:")
    print(f"   Mode: {settings.ENVIRONMENT}")
    print(f"   Debug: {settings.DEBUG}")
    print(f"   Log Level: {settings.LOG_LEVEL}")
    
    print(f"\n🤖 AI Provider:")
    print(f"   Active Provider: {settings.AI_PROVIDER}")
    print(f"   Model: {settings.get_ai_model_name()}")
    
    if show_secrets:
        print(f"   API Key: {settings.get_ai_api_key()[:20]}...")
    else:
        print(f"   Gemini API: {'✓ Configured' if settings.GEMINI_API_KEY else 'Not configured'}")
        print(f"   Groq API: {'✓ Configured' if settings.GROQ_API_KEY else 'Not configured'}")