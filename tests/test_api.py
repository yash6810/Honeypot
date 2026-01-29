"""
Test suite for the FastAPI application API endpoints.
Covers API authentication, scam detection, multi-turn conversations, and callback logic.
"""
import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock
import os
import json
from datetime import datetime, timedelta

# Adjust path for importing modules when running tests directly or via pytest
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.main import app
from api.models import IncomingMessage, MessageContent
from config import settings # Import global settings

# --- Fixtures ---

@pytest.fixture(scope="session")
def anyio_backend():
    """Configures anyio for pytest-asyncio."""
    return "asyncio"

@pytest.fixture(name="client")
async def client_fixture():
    """Provides an asynchronous test client for the FastAPI app."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture(name="valid_api_key")
def valid_api_key_fixture():
    """Returns a valid API key for testing."""
    # Ensure a test API key is set in the environment or mock it
    os.environ["API_SECRET_KEY"] = "test-api-secret"
    settings.API_SECRET_KEY = "test-api-secret" # Update runtime setting
    return os.environ["API_SECRET_KEY"]

@pytest.fixture(name="mock_orchestrator")
def mock_orchestrator_fixture():
    """Mocks the orchestrator for controlled testing of API logic."""
    with patch("api.main.orchestrator") as mock_orch:
        mock_orch.process_message = AsyncMock()
        mock_orch.session_manager = AsyncMock() # Mock session_manager for callback
        yield mock_orch

@pytest.fixture(name="mock_send_final_callback")
def mock_send_final_callback_fixture():
    """Mocks the send_final_callback function."""
    with patch("api.main.send_final_callback") as mock_callback:
        mock_callback.return_value = True
        yield mock_callback

# --- Test Data ---

def create_incoming_message(
    session_id: str,
    text: str,
    conversation_history: Optional[List[Dict[str, str]]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> IncomingMessage:
    """Helper to create an IncomingMessage instance."""
    if conversation_history is None:
        conversation_history = []
    if metadata is None:
        metadata = {"channel": "test", "language": "en"}

    return IncomingMessage(
        sessionId=session_id,
        message=MessageContent(sender="scammer", text=text, timestamp=datetime.now().isoformat()),
        conversationHistory=[MessageContent(**msg) for msg in conversation_history],
        metadata=metadata
    )

# --- Tests ---

@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    """Verify the health check endpoint returns OK."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert "timestamp" in response.json()

@pytest.mark.asyncio
async def test_invalid_api_key_returns_403(client: AsyncClient):
    """Ensure requests with invalid API key are rejected."""
    message = create_incoming_message("test-session-1", "Hello, is this tech support?")
    response = await client.post("/analyze", headers={"x-api-key": "wrong-key"}, json=message.model_dump())
    assert response.status_code == 403
    assert "Invalid API Key" in response.json()["detail"]

@pytest.mark.asyncio
async def test_missing_api_key_returns_403(client: AsyncClient):
    """Ensure requests without API key are rejected."""
    message = create_incoming_message("test-session-1", "Hello, is this tech support?")
    response = await client.post("/analyze", json=message.model_dump())
    assert response.status_code == 403
    assert "Not authenticated" in response.json()["detail"]

@pytest.mark.asyncio
async def test_analyze_detects_scam(
    client: AsyncClient,
    valid_api_key: str,
    mock_orchestrator,
    mock_send_final_callback
):
    """Test that a clear scam message is detected and processed."""
    session_id = "test-session-scam"
    scam_message_text = "URGENT! Your account is blocked. Click here to verify: http://bit.ly/scamlink"
    message = create_incoming_message(session_id, scam_message_text)

    # Configure mock orchestrator response for a detected scam
    mock_orchestrator.process_message.return_value = {
        "status": "success",
        "scamDetected": True,
        "agentResponse": "Oh dear, I'm worried! What should I do?",
        "extractedIntelligence": {
            "bankAccounts": [],
            "upiIds": [],
            "phishingLinks": ["http://bit.ly/scamlink"],
            "phoneNumbers": [],
            "suspiciousKeywords": ["urgent", "blocked", "verify"]
        },
        "engagementMetrics": {
            "conversationTurn": 1,
            "responseTimeMs": 150,
            "totalIntelligenceItems": 3,
            "confidenceScore": 0.95
        },
        "continueConversation": True,
        "agentNotes": "High confidence scam: urgency and phishing link."
    }

    response = await client.post(
        "/analyze",
        headers={"x-api-key": valid_api_key},
        json=message.model_dump()
    )

    assert response.status_code == 200
    response_json = response.json()
    assert response_json["scamDetected"] is True
    assert "http://bit.ly/scamlink" in response_json["extractedIntelligence"]["phishingLinks"]
    assert response_json["continueConversation"] is True
    mock_orchestrator.process_message.assert_called_once()
    mock_send_final_callback.assert_not_called()

@pytest.mark.asyncio
async def test_analyze_multi_turn_maintains_context_and_accumulates_intel(
    client: AsyncClient,
    valid_api_key: str,
    mock_orchestrator,
    mock_send_final_callback
):
    """Test that intelligence accumulates and context is maintained across turns."""
    session_id = "test-multi-turn"
    
    # --- Turn 1: Scammer sends initial scam message ---
    message_1_text = "Hello, your bank account is compromised. Call this number: +919876543210"
    message_1 = create_incoming_message(session_id, message_1_text)

    mock_orchestrator.process_message.return_value = {
        "status": "success",
        "scamDetected": True,
        "agentResponse": "Oh my, a phone number! What should I do?",
        "extractedIntelligence": {
            "bankAccounts": [], "upiIds": [], "phishingLinks": [],
            "phoneNumbers": ["+919876543210"], "suspiciousKeywords": ["compromised"]
        },
        "engagementMetrics": {"conversationTurn": 1, "responseTimeMs": 100, "totalIntelligenceItems": 2, "confidenceScore": 0.8},
        "continueConversation": True,
        "agentNotes": "Phone number detected."
    }

    response_1 = await client.post(
        "/analyze",
        headers={"x-api-key": valid_api_key},
        json=message_1.model_dump()
    )
    assert response_1.status_code == 200
    assert "+919876543210" in response_1.json()["extractedIntelligence"]["phoneNumbers"]
    mock_orchestrator.process_message.assert_called_once()
    mock_orchestrator.process_message.reset_mock() # Reset mock call count

    # --- Turn 2: Scammer sends more intel after agent response ---
    agent_response_1 = response_1.json()["agentResponse"]
    message_2_text = "Just transfer money to this UPI ID: scammer@paytm. It's urgent."
    
    # Simulate API's conversationHistory with previous scammer message + agent's response
    conversation_history_for_turn_2 = [
        {"sender": "scammer", "text": message_1_text, "timestamp": datetime.now().isoformat()},
        {"sender": "honeypot-agent", "text": agent_response_1, "timestamp": (datetime.now() + timedelta(seconds=1)).isoformat()}
    ]
    message_2 = create_incoming_message(session_id, message_2_text, conversation_history_for_turn_2)

    # Mock orchestrator response for second turn, accumulating intelligence
    mock_orchestrator.process_message.return_value = {
        "status": "success",
        "scamDetected": True,
        "agentResponse": "UPI ID? What is that? I don't understand these things.",
        "extractedIntelligence": {
            "bankAccounts": [], "upiIds": ["scammer@paytm"], "phishingLinks": [],
            "phoneNumbers": ["+919876543210"], # Should still have intel from previous turn
            "suspiciousKeywords": ["compromised", "urgent"]
        },
        "engagementMetrics": {"conversationTurn": 2, "responseTimeMs": 120, "totalIntelligenceItems": 4, "confidenceScore": 0.9},
        "continueConversation": True,
        "agentNotes": "UPI ID and phone number detected."
    }

    response_2 = await client.post(
        "/analyze",
        headers={"x-api-key": valid_api_key},
        json=message_2.model_dump()
    )

    assert response_2.status_code == 200
    response_json_2 = response_2.json()
    assert "scammer@paytm" in response_json_2["extractedIntelligence"]["upiIds"]
    assert "+919876543210" in response_json_2["extractedIntelligence"]["phoneNumbers"] # Check accumulation
    assert response_json_2["engagementMetrics"]["conversationTurn"] == 2
    assert response_json_2["continueConversation"] is True
    mock_orchestrator.process_message.assert_called_once()
    mock_send_final_callback.assert_not_called()


@pytest.mark.asyncio
async def test_conversation_ends_triggers_callback(
    client: AsyncClient,
    valid_api_key: str,
    mock_orchestrator,
    mock_send_final_callback
):
    """Test that when continueConversation is False, a callback is triggered."""
    session_id = "test-session-end"
    message_text = "I have all your details now, goodbye."
    message = create_incoming_message(session_id, message_text)

    # Mock orchestrator response indicating conversation should end
    mock_orchestrator.process_message.return_value = {
        "status": "success",
        "scamDetected": True,
        "agentResponse": "...",
        "extractedIntelligence": {
            "bankAccounts": ["1234567890123456"],
            "upiIds": ["scammer@paytm"],
            "phishingLinks": [],
            "phoneNumbers": [],
            "suspiciousKeywords": []
        },
        "engagementMetrics": {"conversationTurn": 5, "responseTimeMs": 200, "totalIntelligenceItems": 2, "confidenceScore": 0.85},
        "continueConversation": False, # KEY: Conversation ends
        "agentNotes": "Max intel reached."
    }
    
    # Mock session_manager.get_session_summary for the callback payload
    mock_orchestrator.session_manager.get_session_summary.return_value = {
        "sessionId": session_id,
        "scamDetected": True,
        "turnCount": 5,
        "personaUsed": "elderly",
        "extractedIntelligence": {
            "bankAccounts": ["1234567890123456"],
            "upiIds": ["scammer@paytm"],
            "phishingLinks": [],
            "phoneNumbers": [],
            "suspiciousKeywords": []
        },
        "conversationHistory": [], # Not relevant for this mock
        "conversationActive": False,
        "lastIntelligenceTurn": 4,
        "createdAt": datetime.now().isoformat()
    }


    response = await client.post(
        "/analyze",
        headers={"x-api-key": valid_api_key},
        json=message.model_dump()
    )

    assert response.status_code == 200
    response_json = response.json()
    assert response_json["continueConversation"] is False
    mock_orchestrator.process_message.assert_called_once()
    mock_send_final_callback.assert_called_once()
    
    # Verify callback payload structure
    callback_args, _ = mock_send_final_callback.call_args
    assert callback_args[0] == session_id
    callback_payload = callback_args[1]
    assert callback_payload["sessionId"] == session_id
    assert callback_payload["scamDetected"] is True
    assert callback_payload["totalMessagesExchanged"] == 5
    assert "bankAccounts" in callback_payload["extractedIntelligence"]
    assert "upiIds" in callback_payload["extractedIntelligence"]
    assert "agentNotes" in callback_payload

@pytest.mark.asyncio
async def test_internal_server_error_handling(
    client: AsyncClient,
    valid_api_key: str,
    mock_orchestrator,
    mock_send_final_callback
):
    """Test that internal server errors from orchestrator are handled gracefully."""
    session_id = "test-internal-error"
    message_text = "This message will cause an error."
    message = create_incoming_message(session_id, message_text)

    # Configure mock orchestrator to raise an exception
    mock_orchestrator.process_message.side_effect = Exception("Simulated internal error")

    response = await client.post(
        "/analyze",
        headers={"x-api-key": valid_api_key},
        json=message.model_dump()
    )

    assert response.status_code == 500
    assert "Internal server error" in response.json()["detail"]
    mock_orchestrator.process_message.assert_called_once()
    mock_send_final_callback.assert_not_called()

