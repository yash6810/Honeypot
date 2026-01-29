"""
API key authentication module.
"""
import os
import logging
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the API key header scheme
api_key_header = APIKeyHeader(name="x-api-key", auto_error=True)

async def get_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Dependency to validate the API key provided in the 'x-api-key' header.

    Args:
        api_key: The API key extracted from the 'x-api-key' header by FastAPI.

    Returns:
        The validated API key string.

    Raises:
        HTTPException: If the API key is missing or invalid.
    """
    expected_api_key = os.getenv("API_SECRET_KEY")

    if not expected_api_key:
        logger.error("API_SECRET_KEY environment variable is not set. API authentication cannot proceed.")
        # In a production environment, you might want to raise an internal server error
        # rather than exposing this configuration issue directly to the client.
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Server configuration error: API key not set."
        )

    if api_key == expected_api_key:
        logger.debug("API Key validated successfully.")
        return api_key
    else:
        logger.warning(f"Invalid API key received: {api_key}")
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Could not validate credentials. Invalid API Key."
        )

# Example of how to use it in a FastAPI path operation:
# @app.post("/analyze")
# async def analyze_scam_message(
#     data: IncomingMessage,
#     api_key: str = Depends(get_api_key)
# ):
#     # Your logic here, api_key is now validated
#     return {"message": "Authenticated successfully"}
