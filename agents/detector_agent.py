"""
Component 1: Detector Agent
"""
import os
import re
import json
import time
import logging
from typing import Dict, List, Any, Optional

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from agents.prompts import DETECTOR_PROMPT

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DetectorAgent:
    """
    Scam detection agent using the Google Gemini API.

    This agent analyzes incoming messages to classify them as scams or legitimate,
    providing a confidence score and a reason for its classification.

    Attributes:
        api_key (str): The Google Gemini API key.
        model_name (str): The name of the Gemini model to use.
        client: The configured Gemini API client.
    """

    def __init__(self, api_key: str, model_name: str = "gemini-flash-latest"):
        """
        Initializes the DetectorAgent.

        Args:
            api_key: The Google Gemini API key.
            model_name: The Gemini model to use for detection.

        Raises:
            ValueError: If the API key is not provided.
        """
        if not api_key:
            raise ValueError("Google Gemini API key cannot be empty.")
            
        self.api_key = api_key
        self.model_name = model_name
        self.client = self._initialize_client()
        logger.info(f"DetectorAgent initialized with model: {self.model_name}")

    def _initialize_client(self) -> genai.GenerativeModel:
        """Initializes the Gemini API client."""
        genai.configure(api_key=self.api_key)
        return genai.GenerativeModel(self.model_name)

    def _default_response(self) -> Dict[str, Any]:
        """Returns a default response in case of errors."""
        return {
            "is_scam": False,
            "confidence": 0.5,
            "reason": "Unable to analyze the message due to an internal error.",
            "indicators": []
        }

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """
        Safely parses the JSON response from the Gemini API.
        The response might be enclosed in markdown ```json ... ``` tags.
        """
        # Find the JSON block within the markdown
        match = re.search(r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            # If no markdown, assume the whole text is a JSON string
            json_str = response_text

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Malformed JSON string: {json_str}")
            return self._default_response()

    def detect_scam(self, message: str, history: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Detects if a given message is a scam with retry logic.

        Args:
            message: The message text to analyze.
            history: Optional list of previous conversation messages for context.

        Returns:
            A dictionary containing the scam analysis result.
        """
        if not message or not message.strip():
            logger.warning("Attempted to analyze an empty message.")
            return {
                "is_scam": False,
                "confidence": 0.0,
                "reason": "Message was empty.",
                "indicators": []
            }

        history = history or []
        prompt = DETECTOR_PROMPT.format(history=json.dumps(history, indent=2), message=message)
        
        retries = 2
        delay = 1  # seconds

        for attempt in range(retries + 1):
            try:
                response = self.client.generate_content(prompt)
                
                if response and response.text:
                    result = self._parse_response(response.text)
                    logger.info(f"Scam detection successful: is_scam={result.get('is_scam')}, confidence={result.get('confidence')}")
                    return result
                else:
                    logger.warning("Received an empty response from Gemini API.")
                    # Continue to retry if response is empty

            except google_exceptions.ResourceExhausted as e:
                logger.error(f"Gemini API rate limit exceeded: {e}")
                if attempt < retries:
                    time.sleep(delay * (2 ** attempt)) # Exponential backoff
                continue
            except Exception as e:
                logger.error(f"An unexpected error occurred during scam detection: {e}", exc_info=True)
                if attempt < retries:
                    time.sleep(delay)
                continue
        
        logger.error("All retry attempts failed for scam detection.")
        return self._default_response()

if __name__ == '__main__':
    # This is a simple test block that runs when the script is executed directly.
    # It requires the GEMINI_API_KEY environment variable to be set.
    
    # You would typically run this from your terminal like so:
    # $ export GEMINI_API_KEY="your_api_key_here"
    # $ python agents/detector_agent.py
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set the GEMINI_API_KEY environment variable to run this test.")
    else:
        detector = DetectorAgent(api_key=api_key)
        
        # Example 1: A clear scam message
        test_message_scam = "URGENT! Your bank account has been locked due to suspicious activity. Click here to verify your identity now: http://bit.ly/2fakebank"
        print(f"--- Analyzing scam message ---")
        result_scam = detector.detect_scam(test_message_scam)
        print(json.dumps(result_scam, indent=2))
        
        # Example 2: A legitimate message
        test_message_legit = "Hi, are we still on for dinner at 7 PM tonight? Let me know."
        print(f"\n--- Analyzing legitimate message ---")
        result_legit = detector.detect_scam(test_message_legit)
        print(json.dumps(result_legit, indent=2))

        # Example 3: A message with history
        history = [
            {"sender": "scammer", "text": "Hello, I'm from tech support. Your computer is at risk."},
            {"sender": "user", "text": "Oh really? What's wrong?"}
        ]
        test_message_context = "I need you to install this software to fix it. Just go to sketchy-download.com"
        print(f"\n--- Analyzing message with history ---")
        result_context = detector.detect_scam(test_message_context, history=history)
        print(json.dumps(result_context, indent=2))
