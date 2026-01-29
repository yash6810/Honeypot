"""
Component 5: Orchestrator
"""
import logging
from typing import Dict, List, Any, Optional
import time

from agents.detector_agent import DetectorAgent
from agents.actor_agent import ActorAgent
from agents.investigator_agent import InvestigatorAgent
from agents.session_manager import SessionManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Orchestrator:
    """
    Coordinates the flow between DetectorAgent, ActorAgent, InvestigatorAgent,
    and SessionManager to process incoming messages, manage conversation state,
    and generate responses.
    """

    def __init__(self,
                 detector: DetectorAgent,
                 actor: ActorAgent,
                 investigator: InvestigatorAgent,
                 session_manager: SessionManager):
        """
        Initializes the Orchestrator with instances of all agents and the session manager.

        Args:
            detector: An instance of DetectorAgent.
            actor: An instance of ActorAgent.
            investigator: An instance of InvestigatorAgent.
            session_manager: An instance of SessionManager.
        """
        self.detector = detector
        self.actor = actor
        self.investigator = investigator
        self.session_manager = session_manager
        logger.info("Orchestrator initialized with Detector, Actor, Investigator, and SessionManager.")

    def _select_persona(self, session_id: str, metadata: Dict[str, Any]) -> str:
        """
        Selects an appropriate persona for the ActorAgent based on various factors.
        This is a placeholder for more sophisticated logic.

        Args:
            session_id: The ID of the current session.
            metadata: Additional metadata about the message (e.g., channel, language).

        Returns:
            The selected persona ("elderly", "professional", "novice").
        """
        # Placeholder for persona selection logic
        # For now, let's just default to 'elderly' or use a simple heuristic
        # In a real scenario, this could be based on initial scam analysis,
        # or metadata like message source.
        session_summary = self.session_manager.get_session_summary(session_id)
        if session_summary.get("personaUsed"):
            return session_summary["personaUsed"] # Maintain consistent persona
        
        # Simple heuristic for first interaction
        message_text = session_summary["conversationHistory"][-1]["text"] if session_summary["conversationHistory"] else ""
        if "bank" in message_text.lower() or "account" in message_text.lower():
            return "elderly" # Scams often target the vulnerable
        elif "business" in message_text.lower() or "investment" in message_text.lower():
            return "professional"
        else:
            return "novice"


    def process_message(
                        self, 
                        session_id: str,
                        message: Dict[str, str], # {"sender": "scammer", "text": "...", "timestamp": "..."}
                        conversation_history: List[Dict[str, str]], # Full history from request, will be merged
                        metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processes an incoming message, orchestrating the actions of various agents.

        Args:
            session_id: Unique identifier for the conversation session.
            message: The latest incoming message from the scammer.
            conversation_history: List of previous messages in the conversation provided by the API.
            metadata: Additional context/metadata related to the message (e.g., channel).

        Returns:
            A dictionary containing the agent's response, extracted intelligence, and other metrics.
        """
        start_time = time.time()

        # 1. Get or create session from session manager
        session = self.session_manager.get_or_create_session(session_id)
        
        # Update session's history with the new message and any provided historical messages
        # Note: conversation_history from API is *all* previous messages.
        # Our session.conversation_history only contains messages *processed by us*.
        # We need to ensure we have the full context for agents like detector.
        full_conversation_context = conversation_history + [message]

        # 2. Extract message text
        message_text = message.get("text", "")
        
        # 3. Call detector agent if first message or confidence was low before
        # The detector agent should always get the full history to make the best decision
        detector_result = self.detector.detect_scam(message_text, full_conversation_context)
        self.session_manager.set_scam_detected(session_id, detector_result["is_scam"])

        scam_detected = detector_result["is_scam"] and detector_result["confidence"] > 0.7

        agent_response = ""
        persona_used = session["persona_used"] # Try to maintain persona
        if scam_detected:
            # 4a. Select persona (if not already set, or if we want to adapt)
            if not persona_used:
                persona_used = self._select_persona(session_id, metadata)
                self.session_manager.set_persona_used(session_id, persona_used)
            
            # 4b. Call actor agent to generate response
            # Actor agent needs history of what *we* said too, not just scammer messages.
            # But its prompt only explicitly uses the "scammer" messages as input.
            # Here, we feed the full context for richer responses if the actor prompt allows.
            agent_response = self.actor.generate_response(message_text, persona_used, full_conversation_context)
        else:
            agent_response = "Thank you for your message. I will pass this along." # Default for non-scam or low confidence

        # 5. Call investigator agent to extract intelligence from scammer's message
        extracted_intel = self.investigator.extract_all(message_text)

        # 6. Update session with new intelligence
        self.session_manager.update_intelligence(session_id, extracted_intel)
        
        # Record the latest message (scammer's) and our response in the session history
        self.session_manager.increment_turn(session_id, message) # Scammer's message
        if agent_response:
             # Our response should also be part of the session's internal history
            self.session_manager.increment_turn(session_id, {
                "sender": "honeypot-agent",
                "text": agent_response,
                "timestamp": datetime.now().isoformat() # Need datetime.now() from somewhere
            })


        # 7. Check if conversation should end
        continue_conversation = not self.session_manager.should_end_conversation(session_id)
        if not continue_conversation:
            logger.info(f"Conversation {session_id} is ending.")
            # self.session_manager.end_session(session_id) # should_end_conversation already flags it

        # 8. Build and return response dict
        session_summary = self.session_manager.get_session_summary(session_id)
        
        end_time = time.time()
        response_time_ms = int((end_time - start_time) * 1000)
        
        # Flatten extractedIntelligence from sets to lists for output
        output_intelligence = {
            k: sorted(list(v)) for k, v in session_summary["extractedIntelligence"].items()
        }

        # Calculate total intelligence items
        total_intelligence_items = sum(len(v) for v in output_intelligence.values())

        return {
            "status": "success",
            "scamDetected": session_summary["scamDetected"],
            "agentResponse": agent_response,
            "extractedIntelligence": output_intelligence,
            "engagementMetrics": {
                "conversationTurn": session_summary["turnCount"],
                "responseTimeMs": response_time_ms,
                "totalIntelligenceItems": total_intelligence_items,
                "confidenceScore": detector_result["confidence"] # Add detector confidence here
            },
            "continueConversation": continue_conversation,
            "agentNotes": detector_result["reason"] # Using detector's reason as initial agent note
        }

if __name__ == '__main__':
    # Simple test block for Orchestrator
    # This block requires GEMINI_API_KEY to be set in environment variables

    import os
    from datetime import datetime

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set the GEMINI_API_KEY environment variable to run this Orchestrator test.")
    else:
        # Initialize agents
        detector_agent = DetectorAgent(api_key=api_key)
        actor_agent = ActorAgent(api_key=api_key)
        investigator_agent = InvestigatorAgent()
        session_manager = SessionManager(max_conversation_turns=5, min_intelligence_threshold=1, stale_conversation_threshold=2)

        orchestrator = Orchestrator(detector_agent, actor_agent, investigator_agent, session_manager)

        test_session_id = "orch_test_1"
        test_metadata = {"channel": "telegram", "language": "en"}
        
        print("\n--- Orchestrator Test: First Message (Scam) ---")
        message_1 = {"sender": "scammer", "text": "URGENT! Your bank account needs verification. Click here: http://bit.ly/fake-bank", "timestamp": datetime.now().isoformat()}
        response_1 = orchestrator.process_message(test_session_id, message_1, [], test_metadata)
        print(f"Response 1: {response_1}")
        print(f"Session Summary after 1: {session_manager.get_session_summary(test_session_id)}")

        print("\n--- Orchestrator Test: Second Message (User's response) ---")
        # In a real scenario, the API would send the user's message as the 'message' parameter
        # and previous messages (including our agent's response) as 'conversation_history'.
        # For this test, we simulate this by feeding our previous agent response into history
        # and a new scammer message.
        user_response_to_scammer = response_1["agentResponse"]
        # Simulate scammer's next message
        message_2 = {"sender": "scammer", "text": "Ok, just input your OTP on the page. Call +919988776655 if you have issues.", "timestamp": datetime.now().isoformat()}
        
        # The conversation_history passed to process_message should be the full history
        # from the API's perspective, which includes both scammer and agent messages.
        # For simplicity in this test, we'll build it manually.
        current_conversation_history = [
            message_1,
            {"sender": "honeypot-agent", "text": user_response_to_scammer, "timestamp": datetime.now().isoformat()}
        ]
        response_2 = orchestrator.process_message(test_session_id, message_2, current_conversation_history, test_metadata)
        print(f"Response 2: {response_2}")
        print(f"Session Summary after 2: {session_manager.get_session_summary(test_session_id)}")

        print("\n--- Orchestrator Test: Third Message (Ending Conversation) ---")
        message_3 = {"sender": "scammer", "text": "Are you there? If not, I'll close your account.", "timestamp": datetime.now().isoformat()}
        # For the third message, we assume the conversation history would now include message_1, agent_response_1, message_2, agent_response_2
        current_conversation_history.append(message_2)
        current_conversation_history.append({"sender": "honeypot-agent", "text": response_2["agentResponse"], "timestamp": datetime.now().isoformat()})
        
        response_3 = orchestrator.process_message(test_session_id, message_3, current_conversation_history, test_metadata)
        print(f"Response 3: {response_3}")
        print(f"Session Summary after 3: {session_manager.get_session_summary(test_session_id)}")
        print(f"Conversation still active? {response_3['continueConversation']}")

        # Simulate more turns to hit max_conversation_turns or stale_conversation_threshold
        print("\n--- Orchestrator Test: Hitting max turns (simulated) ---")
        orchestrator_max_turns = Orchestrator(detector_agent, actor_agent, investigator_agent, SessionManager(max_conversation_turns=3)) # New session manager
        session_id_max = "orch_test_max"
        
        for i in range(1, 5): # Will go over 3 turns
            msg = {"sender": "scammer", "text": f"Message {i} in max turns test. Some info: +918877665544", "timestamp": datetime.now().isoformat()}
            history_for_turn = [] # Simplify history for this quick test loop
            if i > 1:
                prev_summary = orchestrator_max_turns.session_manager.get_session_summary(session_id_max)
                history_for_turn = prev_summary["conversationHistory"]
            
            res = orchestrator_max_turns.process_message(session_id_max, msg, history_for_turn, test_metadata)
            print(f"Turn {i}, Continue: {res['continueConversation']}, Total intel: {res['engagementMetrics']['totalIntelligenceItems']}")
            if not res['continueConversation']:
                break
        print(f"Final session summary for max turns test: {orchestrator_max_turns.session_manager.get_session_summary(session_id_max)}")
