"""
GUVI Callback Handler module.
Responsible for sending the final intelligence summary to the GUVI evaluation endpoint.
"""
import os
import httpx
import asyncio
import logging
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# GUVI callback URL from environment variables
GUVI_CALLBACK_URL = os.getenv("GUVI_CALLBACK_URL", "https://hackathon.guvi.in/api/updateHoneyPotFinalResult")

async def send_final_callback(session_id: str, final_data: Dict[str, Any]) -> bool:
    """
    Sends the final intelligence summary to the GUVI evaluation endpoint.
    Includes retry logic with exponential backoff.

    Args:
        session_id: The unique identifier for the conversation session.
        final_data: A dictionary containing the complete intelligence summary and other metadata.

    Returns:
        True if the callback was sent successfully, False otherwise after all retries.
    """
    
    if not GUVI_CALLBACK_URL:
        logger.error("GUVI_CALLBACK_URL environment variable is not set. Cannot send callback.")
        return False

    max_attempts = 3
    base_delay = 2  # seconds

    # Ensure final_data has sessionId
    if "sessionId" not in final_data:
        final_data["sessionId"] = session_id

    for attempt in range(max_attempts):
        try:
            logger.info(f"Attempt {attempt + 1}/{max_attempts} to send callback for session {session_id} to {GUVI_CALLBACK_URL}")
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    GUVI_CALLBACK_URL,
                    json=final_data,
                    timeout=10 # 10 seconds timeout per attempt
                )
                response.raise_for_status() # Raises an exception for 4xx/5xx responses

            logger.info(f"Callback for session {session_id} sent successfully. Response: {response.status_code}")
            return True

        except httpx.RequestError as e:
            logger.error(f"Request error sending callback for session {session_id} (Attempt {attempt + 1}): {e}")
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error sending callback for session {session_id} (Attempt {attempt + 1}): {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logger.error(f"An unexpected error occurred while sending callback for session {session_id} (Attempt {attempt + 1}): {e}", exc_info=True)

        if attempt < max_attempts - 1:
            delay = base_delay * (2 ** attempt) # Exponential backoff
            logger.info(f"Retrying callback for session {session_id} in {delay} seconds...")
            await asyncio.sleep(delay)

    logger.error(f"Failed to send callback for session {session_id} after {max_attempts} attempts.")
    return False

if __name__ == '__main__':
    # Simple test block for send_final_callback
    async def test_callback_function():
        test_session_id = "test_callback_123"
        test_final_data = {
            "sessionId": test_session_id,
            "scamDetected": True,
            "totalMessagesExchanged": 5,
            "extractedIntelligence": {
                "bankAccounts": ["1234567890123456"],
                "upiIds": ["test@paytm"],
                "phishingLinks": ["http://fake-scam.com"],
                "phoneNumbers": ["+919876543210"],
                "suspiciousKeywords": ["urgent", "OTP"]
            },
            "agentNotes": "Scammer tried to get OTP and bank details."
        }
        
        print(f"Testing callback for session: {test_session_id}")
        success = await send_final_callback(test_session_id, test_final_data)
        print(f"Callback successful: {success}")

        # Simulate a failed callback (e.g., if URL is wrong or server is down)
        os.environ["GUVI_CALLBACK_URL"] = "http://localhost:9999/nonexistent-endpoint" # Intentionally set wrong URL
        print("\nTesting failed callback (due to wrong URL/no server)...")
        success_fail = await send_final_callback("fail_session_456", test_final_data)
        print(f"Callback successful (expected False): {success_fail}")
        del os.environ["GUVI_CALLBACK_URL"] # Clean up env var

    # To run the async test function
    asyncio.run(test_callback_function())
