"""
Test suite for the individual agent components: DetectorAgent, ActorAgent, and SessionManager.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import os
import json
from datetime import datetime, timedelta

# Adjust path for importing modules when running tests directly or via pytest
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from agents.detector_agent import DetectorAgent
from agents.actor_agent import ActorAgent
from agents.session_manager import SessionManager
from agents.prompts import DETECTOR_PROMPT, get_actor_prompt

# --- Fixtures ---

@pytest.fixture(scope="session")
def anyio_backend():
    """Configures anyio for pytest-asyncio."""
    return "asyncio"

@pytest.fixture(name="mock_gemini_api")
def mock_gemini_api_fixture():
    """Mocks the google.generativeai.GenerativeModel for agent tests."""
    with patch("google.generativeai.GenerativeModel") as mock_model_class:
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model
        mock_model.generate_content = AsyncMock()
        yield mock_model.generate_content

@pytest.fixture(name="gemini_api_key")
def gemini_api_key_fixture():
    """Provides a dummy API key for agent initialization."""
    return "dummy-api-key"

# --- DetectorAgent Tests ---

@pytest.mark.asyncio
async def test_detector_agent_init(gemini_api_key: str):
    """Test DetectorAgent initialization."""
    detector = DetectorAgent(api_key=gemini_api_key)
    assert detector.api_key == gemini_api_key
    assert detector.model_name == "gemini-1.5-flash"

@pytest.mark.asyncio
async def test_detector_agent_detect_scam_true(mock_gemini_api: AsyncMock, gemini_api_key: str):
    """Test scam detection returning true."""
    detector = DetectorAgent(api_key=gemini_api_key)
    
    mock_gemini_api.return_value.text = json.dumps({
        "is_scam": True,
        "confidence": 0.9,
        "reason": "Contains phishing link and urgency.",
        "indicators": ["phishing link", "urgency"]
    })

    result = await detector.detect_scam("URGENT! Click this link: http://bad.com")
    assert result["is_scam"] is True
    assert result["confidence"] == 0.9
    assert "phishing link" in result["indicators"]
    mock_gemini_api.assert_called_once()

@pytest.mark.asyncio
async def test_detector_agent_detect_scam_false(mock_gemini_api: AsyncMock, gemini_api_key: str):
    """Test scam detection returning false."""
    detector = DetectorAgent(api_key=gemini_api_key)
    
    mock_gemini_api.return_value.text = json.dumps({
        "is_scam": False,
        "confidence": 0.1,
        "reason": "Normal conversation.",
        "indicators": []
    })

    result = await detector.detect_scam("Hello, how are you?")
    assert result["is_scam"] is False
    assert result["confidence"] == 0.1
    mock_gemini_api.assert_called_once()

@pytest.mark.asyncio
async def test_detector_agent_empty_message(gemini_api_key: str):
    """Test detector agent with an empty message."""
    detector = DetectorAgent(api_key=gemini_api_key)
    result = await detector.detect_scam("")
    assert result["is_scam"] is False
    assert result["confidence"] == 0.0
    assert result["reason"] == "Message was empty."

@pytest.mark.asyncio
async def test_detector_agent_api_error_retry(mock_gemini_api: AsyncMock, gemini_api_key: str):
    """Test detector agent handles API errors with retries."""
    detector = DetectorAgent(api_key=gemini_api_key)
    
    # Simulate API raising an exception twice, then succeeding
    mock_gemini_api.side_effect = [
        Exception("API temporary error 1"),
        Exception("API temporary error 2"),
        MagicMock(text=json.dumps({"is_scam": True, "confidence": 0.8, "reason": "ok", "indicators": []}))
    ]

    result = await detector.detect_scam("Test message with API error")
    assert result["is_scam"] is True
    assert result["confidence"] == 0.8
    assert mock_gemini_api.call_count == 3 # 1 initial + 2 retries

@pytest.mark.asyncio
async def test_detector_agent_api_error_max_retries(mock_gemini_api: AsyncMock, gemini_api_key: str):
    """Test detector agent returns default response after max retries."""
    detector = DetectorAgent(api_key=gemini_api_key)
    
    # Simulate API consistently failing
    mock_gemini_api.side_effect = Exception("API persistent error")

    result = await detector.detect_scam("Test message for persistent API error")
    assert result["is_scam"] is False
    assert result["confidence"] == 0.5
    assert mock_gemini_api.call_count == 3 # 1 initial + 2 retries


# --- ActorAgent Tests ---

@pytest.mark.asyncio
async def test_actor_agent_init(gemini_api_key: str):
    """Test ActorAgent initialization."""
    actor = ActorAgent(api_key=gemini_api_key)
    assert actor.api_key == gemini_api_key
    assert actor.model_name == "gemini-1.5-flash"

@pytest.mark.asyncio
async def test_actor_agent_generate_response(mock_gemini_api: AsyncMock, gemini_api_key: str):
    """Test actor agent generates a response for elderly persona."""
    actor = ActorAgent(api_key=gemini_api_key)
    
    mock_gemini_api.return_value.text = "Oh dear, I don't understand!"

    result = await actor.generate_response(
        message="Send me your bank details.",
        persona="elderly",
        history=[]
    )
    assert result == "Oh dear, I don't understand!"
    mock_gemini_api.assert_called_once()
    args, kwargs = mock_gemini_api.call_args
    # Check that the prompt contains parts specific to the elderly persona
    assert "68-year-old retiree" in args[0]

@pytest.mark.asyncio
async def test_actor_agent_generate_response_invalid_persona(mock_gemini_api: AsyncMock, gemini_api_key: str):
    """Test actor agent defaults to novice for invalid persona."""
    actor = ActorAgent(api_key=gemini_api_key)
    
    mock_gemini_api.return_value.text = "OMG, what do I do?"

    result = await actor.generate_response(
        message="Send me your bank details.",
        persona="invalid-persona", # Should default to novice
        history=[]
    )
    assert result == "OMG, what do I do?"
    mock_gemini_api.assert_called_once()
    args, kwargs = mock_gemini_api.call_args
    # Check that the prompt contains parts specific to the novice persona
    assert "Tech-confused" in args[0]


# --- SessionManager Tests ---

@pytest.fixture(name="session_manager")
def session_manager_fixture():
    """Provides a SessionManager instance for testing."""
    return SessionManager(
        max_conversation_turns=5,
        min_intelligence_threshold=2,
        stale_conversation_threshold=2
    )

def test_session_manager_get_or_create_session(session_manager: SessionManager):
    """Test creating and retrieving sessions."""
    session_id = "test-session-new"
    session = session_manager.get_or_create_session(session_id)
    assert session["session_id"] == session_id
    assert session["turn_count"] == 0

    retrieved_session = session_manager.get_or_create_session(session_id)
    assert retrieved_session == session

def test_session_manager_update_intelligence(session_manager: SessionManager):
    """Test updating and accumulating intelligence."""
    session_id = "test-session-intel"
    session_manager.get_or_create_session(session_id)
    session_manager.increment_turn(session_id, {"sender": "scammer", "text": "...", "timestamp": ""}) # turn 1

    new_intel_1 = {
        "phoneNumbers": ["+911234567890"],
        "suspiciousKeywords": ["urgent"]
    }
    session_manager.update_intelligence(session_id, new_intel_1)
    summary = session_manager.get_session_summary(session_id)
    assert "+911234567890" in summary["extractedIntelligence"]["phoneNumbers"]
    assert "urgent" in summary["extractedIntelligence"]["suspiciousKeywords"]
    assert summary["lastIntelligenceTurn"] == 1

    new_intel_2 = {
        "phoneNumbers": ["+911234567890", "+919876543210"], # Add another phone, keep old
        "upiIds": ["user@paytm"] # Add new type
    }
    session_manager.increment_turn(session_id, {"sender": "scammer", "text": "...", "timestamp": ""}) # turn 2
    session_manager.update_intelligence(session_id, new_intel_2)
    summary = session_manager.get_session_summary(session_id)
    assert len(summary["extractedIntelligence"]["phoneNumbers"]) == 2
    assert "user@paytm" in summary["extractedIntelligence"]["upiIds"]
    assert summary["lastIntelligenceTurn"] == 2 # Last intelligence was updated

def test_session_manager_increment_turn(session_manager: SessionManager):
    """Test incrementing turn count."""
    session_id = "test-session-turn"
    session_manager.get_or_create_session(session_id)
    
    initial_turn = session_manager.get_session_summary(session_id)["turnCount"]
    session_manager.increment_turn(session_id, {"sender": "scammer", "text": "msg1", "timestamp": ""})
    assert session_manager.get_session_summary(session_id)["turnCount"] == initial_turn + 1
    assert session_manager.get_session_summary(session_id)["conversationHistory"][-1]["text"] == "msg1"

def test_session_manager_should_end_max_turns(session_manager: SessionManager):
    """Test conversation ending due to max turns."""
    session_id = "test-end-max-turns"
    session_manager.get_or_create_session(session_id)
    for _ in range(session_manager.max_conversation_turns):
        session_manager.increment_turn(session_id, {"sender": "scammer", "text": "...", "timestamp": ""})
    
    assert session_manager.should_end_conversation(session_id) is True
    assert session_manager.get_session_summary(session_id)["conversationActive"] is False

def test_session_manager_should_end_min_intelligence(session_manager: SessionManager):
    """Test conversation ending due to minimum intelligence threshold."""
    session_id = "test-end-min-intel"
    session_manager.get_or_create_session(session_id)
    session_manager.increment_turn(session_id, {"sender": "scammer", "text": "...", "timestamp": ""}) # turn 1

    # Add 2 types of intelligence
    session_manager.update_intelligence(session_id, {"phoneNumbers": ["+91123"], "upiIds": ["a@b"]})
    
    assert session_manager.should_end_conversation(session_id) is True
    assert session_manager.get_session_summary(session_id)["conversationActive"] is False


def test_session_manager_should_end_stale_conversation(session_manager: SessionManager):
    """Test conversation ending due to staleness."""
    session_id = "test-end-stale"
    session_manager.get_or_create_session(session_id)
    
    session_manager.increment_turn(session_id, {"sender": "scammer", "text": "...", "timestamp": ""}) # turn 1
    session_manager.update_intelligence(session_id, {"suspiciousKeywords": ["first intel"]}) # intel at turn 1

    session_manager.increment_turn(session_id, {"sender": "scammer", "text": "...", "timestamp": ""}) # turn 2, no new intel
    assert session_manager.should_end_conversation(session_id) is False # stale_conversation_threshold is 2

    session_manager.increment_turn(session_id, {"sender": "scammer", "text": "...", "timestamp": ""}) # turn 3, no new intel
    assert session_manager.should_end_conversation(session_id) is True # Now 2 turns since last intel (turn 1 to turn 3)
    assert session_manager.get_session_summary(session_id)["conversationActive"] is False

def test_session_manager_should_not_end_prematurely(session_manager: SessionManager):
    """Test conversation does not end if conditions are not met."""
    session_id = "test-no-end"
    session_manager.get_or_create_session(session_id)
    session_manager.increment_turn(session_id, {"sender": "scammer", "text": "...", "timestamp": ""}) # turn 1
    session_manager.update_intelligence(session_id, {"phoneNumbers": ["+91123"]}) # Only 1 intel type
    
    assert session_manager.should_end_conversation(session_id) is False # Not enough intel types
    session_manager.increment_turn(session_id, {"sender": "scammer", "text": "...", "timestamp": ""}) # turn 2
    assert session_manager.should_end_conversation(session_id) is False # Not stale yet, not enough intel
    assert session_manager.get_session_summary(session_id)["conversationActive"] is True