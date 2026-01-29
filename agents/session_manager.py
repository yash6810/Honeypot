"Component 4: Session Manager"
import threading
import time
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SessionManager:
    """
    Manages the state and intelligence gathered for each conversation session.
    It tracks conversation turns, accumulated intelligence, and determines
    when a conversation should end based on predefined criteria.
    """

    def __init__(self, 
                 max_conversation_turns: int = 20,
                 min_intelligence_threshold: int = 2,
                 stale_conversation_threshold: int = 5):
        """
        Initializes the SessionManager.

        Args:
            max_conversation_turns: Maximum number of turns before ending a conversation.
            min_intelligence_threshold: Minimum types of intelligence to collect before considering ending.
            stale_conversation_threshold: Number of turns without new intelligence to consider conversation stale.
        """
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock() # For thread-safe operations on sessions
        self.max_conversation_turns = max_conversation_turns
        self.min_intelligence_threshold = min_intelligence_threshold
        self.stale_conversation_threshold = stale_conversation_threshold
        logger.info(f"SessionManager initialized with max_turns={max_conversation_turns}, "
                    f"min_intel={min_intelligence_threshold}, stale_turns={stale_conversation_threshold}.")

    def _create_new_session_state(self, session_id: str) -> Dict[str, Any]:
        """Creates and returns a new default session state."""
        return {
            "session_id": session_id,
            "turn_count": 0,
            "scam_detected": False, # Set to True once DetectorAgent confirms
            "persona_used": None,   # Will be set by Orchestrator
            "intelligence": {
                "bankAccounts": set(),
                "upiIds": set(),
                "phishingLinks": set(),
                "phoneNumbers": set(),
                "suspiciousKeywords": set()
            },
            "conversation_active": True,
            "last_intelligence_turn": 0, # Tracks turn when last new intel was found
            "created_at": datetime.now().isoformat(),
            "conversation_history": [] # Store messages as dicts {sender: str, text: str, timestamp: str}
        }

    def get_or_create_session(self, session_id: str) -> Dict[str, Any]:
        """
        Retrieves an existing session or creates a new one if it doesn't exist.

        Args:
            session_id: The unique identifier for the conversation session.

        Returns:
            The session state dictionary.
        """
        with self.lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = self._create_new_session_state(session_id)
                logger.info(f"Created new session: {session_id}")
            return self.sessions[session_id]

    def update_intelligence(self, session_id: str, new_intel: Dict[str, List[str]]) -> bool:
        """
        Updates the session's accumulated intelligence with new findings.

        Args:
            session_id: The unique identifier for the conversation session.
            new_intel: A dictionary of newly extracted intelligence.

        Returns:
            True if new intelligence was added, False otherwise.
        """
        with self.lock:
            session = self.sessions.get(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found for intelligence update.")
                return False

            new_intel_added = False
            current_turn = session["turn_count"]

            for intel_type, items in new_intel.items():
                # Convert list of new items to a set for efficient comparison and merging
                new_items_set = set(items)
                
                # Use .get() to safely access existing intelligence set or create an empty set
                current_intel_set = session["intelligence"].get(intel_type, set())
                
                if not new_items_set.issubset(current_intel_set):
                    # There are new items that were not in the current set
                    session["intelligence"][intel_type] = current_intel_set.union(new_items_set)
                    new_intel_added = True
                    logger.debug(f"Session {session_id}: Added new intelligence of type {intel_type}.")
                
            if new_intel_added:
                session["last_intelligence_turn"] = current_turn
                logger.info(f"Session {session_id}: New intelligence detected at turn {current_turn}.")
            
            return new_intel_added

    def increment_turn(self, session_id: str, message_dict: Dict[str, str]) -> int:
        """
        Increments the conversation turn count for a session and appends the message to history.

        Args:
            session_id: The unique identifier for the conversation session.
            message_dict: The message dict {sender, text, timestamp} to add to history.

        Returns:
            The new turn count.
        """
        with self.lock:
            session = self.sessions.get(session_id)
            if not session:
                logger.error(f"Session {session_id} not found for turn increment.")
                return -1 # Indicate error
            session["turn_count"] += 1
            session["conversation_history"].append(message_dict)
            logger.debug(f"Session {session_id}: Turn incremented to {session['turn_count']}.")
            return session["turn_count"]

    def set_scam_detected(self, session_id: str, is_scam: bool = True) -> None:
        """Sets the scam_detected flag for the session."""
        with self.lock:
            session = self.sessions.get(session_id)
            if session:
                session["scam_detected"] = is_scam
                logger.debug(f"Session {session_id}: Scam detected set to {is_scam}.")

    def set_persona_used(self, session_id: str, persona: str) -> None:
        """Sets the persona used for the session."""
        with self.lock:
            session = self.sessions.get(session_id)
            if session:
                session["persona_used"] = persona
                logger.debug(f"Session {session_id}: Persona set to {persona}.")

    def should_end_conversation(self, session_id: str) -> bool:
        """
        Determines if the conversation for a session should end based on predefined rules.

        Rules:
        1. Turn count exceeds MAX_CONVERSATION_TURNS.
        2. At least MIN_INTELLIGENCE_THRESHOLD types of intelligence found.
        3. No new intelligence found in the last STALE_CONVERSATION_THRESHOLD turns.

        Args:
            session_id: The unique identifier for the conversation session.

        Returns:
            True if the conversation should end, False otherwise.
        """
        with self.lock:
            session = self.sessions.get(session_id)
            if not session:
                logger.error(f"Session {session_id} not found for end conversation check.")
                return True # If session somehow lost, best to end

            current_turn = session["turn_count"]
            intelligence_types_found = sum(1 for intel_list in session["intelligence"].values() if len(intel_list) > 0)
            
            # Rule 1: Max turns exceeded
            if current_turn >= self.max_conversation_turns:
                session["conversation_active"] = False
                logger.info(f"Session {session_id} ending: Max turns ({self.max_conversation_turns}) reached.")
                return True
            
            # Rule 2: Sufficient intelligence gathered
            if intelligence_types_found >= self.min_intelligence_threshold and current_turn > 1:
                # Ensure we don't end on the very first turn if intelligence is found
                session["conversation_active"] = False
                logger.info(f"Session {session_id} ending: Sufficient intelligence types ({intelligence_types_found}) gathered.")
                return True

            # Rule 3: Conversation is stale (no new intelligence recently)
            if current_turn - session["last_intelligence_turn"] >= self.stale_conversation_threshold and current_turn > 0:
                session["conversation_active"] = False
                logger.info(f"Session {session_id} ending: Conversation stale (no new intel in {self.stale_conversation_threshold} turns).")
                return True

            return False

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Retrieves a summary of the session's current state and intelligence.

        Args:
            session_id: The unique identifier for the conversation session.

        Returns:
            A dictionary containing a summary of the session.
        """
        with self.lock:
            session = self.sessions.get(session_id)
            if not session:
                logger.error(f"Session {session_id} not found for summary.")
                return {"error": "Session not found"}

            # Convert sets back to lists for external consumption
            intelligence_for_summary = {
                k: sorted(list(v)) for k, v in session["intelligence"].items()
            }

            # Create a simplified conversation history for summary if needed, or pass full
            # For now, pass full but could be truncated for very long histories
            summary = {
                "sessionId": session["session_id"],
                "turnCount": session["turn_count"],
                "scamDetected": session["scam_detected"],
                "personaUsed": session["persona_used"],
                "extractedIntelligence": intelligence_for_summary,
                "conversationActive": session["conversation_active"],
                "lastIntelligenceTurn": session["last_intelligence_turn"],
                "createdAt": session["created_at"],
                "conversationHistory": session["conversation_history"] # Might be large, consider truncating
            }
            return summary

    def end_session(self, session_id: str) -> None:
        """Marks a session as inactive."""
        with self.lock:
            if session_id in self.sessions:
                self.sessions[session_id]["conversation_active"] = False
                logger.info(f"Session {session_id} explicitly marked as inactive.")
            else:
                logger.warning(f"Attempted to end non-existent session: {session_id}")

if __name__ == '__main__':
    # Simple test block for SessionManager
    manager = SessionManager(max_conversation_turns=5, min_intelligence_threshold=1, stale_conversation_threshold=2)
    session_id = "test_session_123"

    # 1. Get or create session
    session = manager.get_or_create_session(session_id)
    print(f"Initial Session: {manager.get_session_summary(session_id)}")

    # 2. Add first message, increment turn
    manager.increment_turn(session_id, {"sender": "scammer", "text": "Hi, your account needs verification.", "timestamp": datetime.now().isoformat()})
    manager.set_scam_detected(session_id, True)
    manager.set_persona_used(session_id, "elderly")
    print(f"\nAfter first turn: {manager.get_session_summary(session_id)}")

    # 3. Update intelligence
    new_intel_1 = {
        "bankAccounts": ["1234567890"],
        "suspiciousKeywords": ["verification", "urgent"]
    }
    manager.update_intelligence(session_id, new_intel_1)
    print(f"\nAfter adding intel 1: {manager.get_session_summary(session_id)}")

    # 4. Increment turn, add another message
    manager.increment_turn(session_id, {"sender": "user", "text": "Oh dear, what should I do?", "timestamp": datetime.now().isoformat()})
    print(f"\nAfter second turn: {manager.get_session_summary(session_id)}")
    
    # 5. Check if conversation should end (min_intelligence_threshold=1 is met)
    print(f"\nShould end after 2 turns and 1 intel type? {manager.should_end_conversation(session_id)}")
    
    # 6. Increment turns without new intel to test stale conversation
    print("\n--- Testing Stale Conversation ---")
    manager = SessionManager(max_conversation_turns=10, min_intelligence_threshold=3, stale_conversation_threshold=2) # Reset for stale test
    session_id_stale = "test_session_stale"
    manager.get_or_create_session(session_id_stale)
    manager.increment_turn(session_id_stale, {"sender": "scammer", "text": "Your lottery winning is ready!", "timestamp": datetime.now().isoformat()})
    manager.update_intelligence(session_id_stale, {"suspiciousKeywords": ["lottery", "winning"]})
    manager.increment_turn(session_id_stale, {"sender": "user", "text": "Wow!", "timestamp": datetime.now().isoformat()})
    manager.increment_turn(session_id_stale, {"sender": "scammer", "text": "Just send fees.", "timestamp": datetime.now().isoformat()}) # Turn 3
    print(f"Turn {manager.sessions[session_id_stale]['turn_count']}. Stale? {manager.should_end_conversation(session_id_stale)}")
    manager.increment_turn(session_id_stale, {"sender": "user", "text": "Hmm?", "timestamp": datetime.now().isoformat()}) # Turn 4
    print(f"Turn {manager.sessions[session_id_stale]['turn_count']}. Stale? {manager.should_end_conversation(session_id_stale)}")
    manager.increment_turn(session_id_stale, {"sender": "scammer", "text": "Hello?", "timestamp": datetime.now().isoformat()}) # Turn 5 - 2 stale turns now (turn 3, 4, 5 without new intel)
    print(f"Turn {manager.sessions[session_id_stale]['turn_count']}. Stale? {manager.should_end_conversation(session_id_stale)}")
    
    # 7. Test max turns
    print("\n--- Testing Max Turns ---")
    manager_max_turns = SessionManager(max_conversation_turns=3, min_intelligence_threshold=1, stale_conversation_threshold=10)
    session_id_max = "test_session_max"
    manager_max_turns.get_or_create_session(session_id_max)
    for i in range(1, 6): # Go beyond 3 turns
        manager_max_turns.increment_turn(session_id_max, {"sender": "scammer", "text": f"Message {i}", "timestamp": datetime.now().isoformat()})
        print(f"Turn {i}. Should end? {manager_max_turns.should_end_conversation(session_id_max)}")
