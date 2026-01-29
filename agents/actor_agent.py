"""
Component 2: Actor Agent
"""
import os
import json
import time
import logging
from typing import Dict, List, Any, Optional

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from agents.prompts import get_actor_prompt

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ActorAgent:
    """
    Generates believable human-like responses to engage scammers,
    maintaining a consistent persona.

    Attributes:
        api_key (str): The Google Gemini API key.
        model_name (str): The name of the Gemini model to use.
        client: The configured Gemini API client.
    """

    def __init__(self, api_key: str, model_name: str = "gemini-flash-latest"):
        """
        Initializes the ActorAgent.

        Args:
            api_key: The Google Gemini API key.
            model_name: The Gemini model to use for response generation.

        Raises:
            ValueError: If the API key is not provided.
        """
        if not api_key:
            raise ValueError("Google Gemini API key cannot be empty.")
            
        self.api_key = api_key
        self.model_name = model_name
        self.client = self._initialize_client()
        logger.info(f"ActorAgent initialized with model: {self.model_name}")

    def _initialize_client(self) -> genai.GenerativeModel:
        """Initializes the Gemini API client."""
        genai.configure(api_key=self.api_key)
        return genai.GenerativeModel(self.model_name)

    def generate_response(self, message: str, persona: str, history: Optional[List[Dict]]) -> str:
        """
        Generates a human-like response based on the given message, persona, and conversation history.

        Args:
            message: The latest scammer message.
            persona: The persona to adopt ("elderly", "professional", "novice").
            history: Optional list of previous conversation messages for context.

        Returns:
            A string containing the generated human-like response.
        """
        if not message or not message.strip():
            logger.warning("Attempted to generate response for an empty message.")
            return "..." # Return a minimal response for an empty input

        if persona not in ["elderly", "professional", "novice"]:
            logger.warning(f"Invalid persona '{persona}' provided. Defaulting to 'novice'.")
            persona = "novice"

        history = history or []
        # The prompt expects history as a JSON string for formatting
        history_str = json.dumps(history, indent=2)
        prompt = get_actor_prompt(persona, history_str, message)
        
        retries = 2
        delay = 1  # seconds

        for attempt in range(retries + 1):
            try:
                response = self.client.generate_content(prompt)
                
                if response and response.text:
                    # Clean up the response from any markdown or extra formatting Gemini might add
                    clean_response = response.text.strip()
                    if clean_response.startswith("```") and clean_response.endswith("```"):
                        clean_response = clean_response.strip("`").strip()
                    logger.info(f"ActorAgent generated response (persona: {persona}): {clean_response}")
                    return clean_response
                else:
                    logger.warning("Received an empty response from Gemini API for ActorAgent.")
                    # Continue to retry if response is empty

            except google_exceptions.ResourceExhausted as e:
                logger.error(f"Gemini API rate limit exceeded for ActorAgent: {e}")
                if attempt < retries:
                    time.sleep(delay * (2 ** attempt)) # Exponential backoff
                continue
            except Exception as e:
                logger.error(f"An unexpected error occurred during response generation for ActorAgent: {e}", exc_info=True)
                if attempt < retries:
                    time.sleep(delay)
                continue
        
        logger.error("All retry attempts failed for ActorAgent. Returning generic response.")
        return "I'm not sure what to say about that." # Generic fallback response

if __name__ == '__main__':
    # Simple test block for ActorAgent
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set the GEMINI_API_KEY environment variable to run this test.")
    else:
        actor = ActorAgent(api_key=api_key)

        print("\n--- Testing Elderly Persona ---")
        elderly_response = actor.generate_response(
            message="You need to send me your bank details to unlock your account.",
            persona="elderly",
            history=[]
        )
        print(f"Elderly Persona: {elderly_response}")

        print("\n--- Testing Professional Persona ---")
        professional_response = actor.generate_response(
            message="Act fast! Your investment opportunity is closing in 24 hours.",
            persona="professional",
            history=[
                {"sender": "scammer", "text": "Urgent investment opportunity!"},
                {"sender": "user", "text": "What are the projected returns?"}
            ]
        )
        print(f"Professional Persona: {professional_response}")

        print("\n--- Testing Novice Persona ---")
        novice_response = actor.generate_response(
            message="Click this link to update your payment information: bit.ly/fakelink",
            persona="novice",
            history=[
                {"sender": "scammer", "text": "Your Netflix account is suspended."},
                {"sender": "user", "text": "OMG! What do I do?"}
            ]
        )
        print(f"Novice Persona: {novice_response}")

        print("\n--- Testing Invalid Persona (should default to novice) ---")
        invalid_persona_response = actor.generate_response(
            message="Send me 1000 dollars please.",
            persona="robot", # Invalid persona
            history=[]
        )
        print(f"Invalid Persona (defaults to novice): {invalid_persona_response}")
