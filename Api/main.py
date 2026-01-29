"""
FastAPI server for the Honeypot Scam Detection Agent.
"""
import asyncio # Import asyncio for background tasks
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.status import HTTP_500_INTERNAL_SERVER_ERROR
# from dotenv import load_dotenv # No longer needed, config.py handles this

# Load environment variables from .env file
# load_dotenv() # No longer needed, config.py handles this

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Import Core Components ---
from agents.detector_agent import DetectorAgent
from agents.actor_agent import ActorAgent
from agents.investigator_agent import InvestigatorAgent
from agents.session_manager import SessionManager
from agents.orchestrator import Orchestrator

# --- Import API Components ---
from api.models import IncomingMessage, ApiResponse, ExtractedIntelligence, EngagementMetrics, MessageContent
from api.auth import get_api_key
from api.callback import send_final_callback

# --- Import and initialize configuration ---
from config import settings # Import the global settings object

# --- Configuration from Environment Variables ---
# These are now accessed via the settings object
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # No longer directly accessed here
# AI_PROVIDER = os.getenv("AI_PROVIDER", "gemini") # No longer directly accessed here
# MAX_CONVERSATION_TURNS = int(os.getenv("MAX_CONVERSATION_TURNS", "20")) # No longer directly accessed here
# MIN_INTELLIGENCE_THRESHOLD = int(os.getenv("MIN_INTELLIGENCE_THRESHOLD", "2")) # No longer directly accessed here
# STALE_CONVERSATION_THRESHOLD = int(os.getenv("STALE_CONVERSATION_THRESHOLD", "5")) # No longer directly accessed here

# --- FastAPI Application Lifecycle ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup and shutdown events for the FastAPI application.
    Initializes agents and the orchestrator.
    """
    global orchestrator # Use global to make it accessible to path operations

    # Validate API key for Gemini at startup (using settings)
    if not settings.get_ai_api_key():
        logger.critical("GEMINI_API_KEY environment variable is not set. Exiting.")
        raise ValueError("GEMINI_API_KEY is not set.")

    # Initialize agents
    try:
        current_ai_api_key = settings.get_ai_api_key()
        current_ai_model_name = settings.get_ai_model_name()

        detector_agent = DetectorAgent(api_key=current_ai_api_key, model_name=current_ai_model_name)
        actor_agent = ActorAgent(api_key=current_ai_api_key, model_name=current_ai_model_name)
        investigator_agent = InvestigatorAgent()
        session_manager = SessionManager(
            max_conversation_turns=settings.MAX_CONVERSATION_TURNS,
            min_intelligence_threshold=settings.MIN_INTELLIGENCE_THRESHOLD,
            stale_conversation_threshold=settings.STALE_CONVERSATION_THRESHOLD
        )
        orchestrator = Orchestrator(detector_agent, actor_agent, investigator_agent, session_manager)
        logger.info("All agents and Orchestrator initialized successfully.")
    except Exception as e:
        logger.critical(f"Failed to initialize agents or Orchestrator: {e}", exc_info=True)
        raise RuntimeError("Application failed to start due to agent initialization error.") from e

    yield # Application starts here

    # --- Shutdown Events (if any) ---
    logger.info("FastAPI application shutting down.")

app = FastAPI(
    title="Honeypot Scam Detection Agent API",
    description="An AI-powered system to detect scam messages, engage scammers, and extract intelligence.",
    version="1.0.0",
    lifespan=lifespan
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins for development. Restrict in production.
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# --- Global Orchestrator Instance ---
orchestrator: Orchestrator # Type hint for the global variable

# --- Health Check Endpoint ---
@app.get("/health", summary="Health Check", tags=["Monitoring"])
async def health_check():
    """
    Returns the current status of the API.
    """
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

# --- Main Analysis Endpoint ---
@app.post(
    "/analyze",
    response_model=ApiResponse,
    summary="Analyze Scam Message",
    tags=["Scam Detection"]
)
async def analyze_scam_message(
    request: IncomingMessage,
    x_api_key: str = Depends(get_api_key) # API Key authentication dependency
):
    """
    Receives an incoming message, analyzes it for scam intent, engages the scammer,
    extracts intelligence, and manages conversation state.
    """
    request_start_time = datetime.now()
    session_id = request.sessionId
    logger.info(f"Received /analyze request for session: {session_id}, message: {request.message.text[:50]}...")

    try:
        # Process the message through the orchestrator
        # The orchestrator is initialized in the lifespan context
        response_data = await orchestrator.process_message(
            session_id=request.sessionId,
            message=request.message.model_dump(), # Convert Pydantic model to dict
            conversation_history=[msg.model_dump() for msg in request.conversationHistory], # Convert list of Pydantic models to list of dicts
            metadata=request.metadata
        )

        # If the conversation should end, trigger the final callback
        if not response_data["continueConversation"]:
            logger.info(f"Conversation {session_id} ended. Triggering final callback.")
            session_summary = orchestrator.session_manager.get_session_summary(session_id)
            
            # Prepare payload for GUVI callback
            callback_payload = {
                "sessionId": session_summary["sessionId"],
                "scamDetected": session_summary["scamDetected"],
                "totalMessagesExchanged": session_summary["turnCount"], # Total messages = turns
                "extractedIntelligence": session_summary["extractedIntelligence"],
                "agentNotes": f"Conversation engaged with persona '{session_summary['personaUsed']}'. "
                              f"Total turns: {session_summary['turnCount']}. "
                              f"Intelligence types found: {sum(1 for v in session_summary['extractedIntelligence'].values() if v)}."
            }
            # Execute callback in the background
            asyncio.create_task(send_final_callback(session_id, callback_payload))
            
            # Optional: Remove session data from memory if conversation truly concluded
            # This would depend on whether we need to query past sessions.
            # For now, let's keep it in memory for potential post-mortem analysis.

        logger.info(f"Finished /analyze request for session: {session_id}. Status: {response_data['status']}")
        return ApiResponse(**response_data) # Return Pydantic ApiResponse model

    except ValueError as e:
        logger.error(f"Validation error for session {session_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"An unexpected error occurred during /analyze for session {session_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}"
        )

