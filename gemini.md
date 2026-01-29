# GEMINI.md - Master Project Instructions for AI Code Generation

## 🎯 PROJECT OVERVIEW

**Project Name:** Honeypot Scam Detection Agent  
**Purpose:** AI-powered system that detects scam messages, engages scammers autonomously, and extracts intelligence (bank accounts, UPI IDs, phishing links)  
**Hackathon:** GUVI x HCL India AI Impact Buildathon  
**Tech Stack:** FastAPI + Google Gemini API + Python 3.10+ + React  
**Timeline:** 10 days (Jan 27 - Feb 5, 2026)  
**Team Size:** 4 developers

---

## 📋 SYSTEM REQUIREMENTS

### Core Functionality

1. **Receive scam messages** via REST API endpoint
2. **Detect scam intent** using AI classification (confidence score 0.0-1.0)
3. **Engage scammers** with believable human-like responses (maintain consistent persona)
4. **Extract intelligence** from conversations (bank accounts, UPI IDs, phone numbers, phishing links, keywords)
5. **Track conversation state** across multiple turns (remember history)
6. **End conversations intelligently** (when enough intel gathered or turns exceeded)
7. **Send final callback** to GUVI evaluation endpoint with accumulated intelligence

### Technical Constraints

- Must use **Google Gemini API** (free tier, no Claude)
- API must respond in **under 5 seconds**
- Must handle **multi-turn conversations** (up to 20 turns)
- Must maintain **persona consistency** throughout conversation
- Must validate **API key authentication** (x-api-key header)
- Must return **exact JSON format** specified by GUVI

---

## 🏗️ ARCHITECTURE SPECIFICATION

### Three-Layer Architecture

```
Layer 1: API Interface (FastAPI)
├── Receives POST requests at /analyze endpoint
├── Validates x-api-key header authentication
├── Parses JSON: {sessionId, message, conversationHistory, metadata}
└── Returns JSON: {status, scamDetected, agentResponse, extractedIntelligence, engagementMetrics, continueConversation}

Layer 2: Multi-Agent AI System (Three Specialized Agents)
├── Agent 1: Detector Agent
│   ├── Classifies message as scam or legitimate
│   ├── Returns confidence score (0.0 to 1.0)
│   └── Triggers actor agent if confidence > 0.7
│
├── Agent 2: Actor Agent  
│   ├── Maintains believable victim persona (elderly/professional/novice)
│   ├── Generates human-like responses using Gemini
│   ├── Never reveals it's AI or detected scam
│   └── Adapts to scammer tactics
│
└── Agent 3: Investigator Agent
    ├── Scans messages for intelligence using regex + validation
    ├── Extracts: bank accounts (9-18 digits), UPI IDs (user@provider), phone numbers (+91 format), URLs
    ├── Validates extracted data (checksums, known providers, format validation)
    └── Accumulates intelligence across conversation turns

Layer 3: State Management & Callback
├── Session Manager tracks conversation state per sessionId
├── Accumulates intelligence across all turns
├── Decides when to end conversation (min 2 intel types OR 20 turns OR 5 stale turns)
└── Sends final callback to GUVI with complete intelligence summary
```

---

## 📂 REQUIRED FILE STRUCTURE

```
honeypot-agent/
├── agents/
│   ├── __init__.py
│   ├── detector_agent.py      # Scam classification logic
│   ├── actor_agent.py          # Persona-based response generation
│   ├── investigator_agent.py   # Intelligence extraction
│   ├── session_manager.py      # Conversation state tracking
│   ├── orchestrator.py         # Multi-agent coordinator
│   └── prompts.py              # AI prompt templates
│
├── api/
│   ├── __init__.py
│   ├── main.py                 # FastAPI server with /analyze endpoint
│   ├── models.py               # Pydantic request/response models
│   ├── callback.py             # GUVI callback handler with retry logic
│   └── auth.py                 # API key validation
│
├── intelligence/
│   ├── __init__.py
│   ├── extractors.py           # Regex patterns for extraction
│   ├── validators.py           # Validation functions
│   └── scam_database.json      # 50 test scam messages
│
├── tests/
│   ├── __init__.py
│   ├── test_api.py             # API endpoint tests
│   ├── test_agents.py          # Agent unit tests
│   ├── test_extractors.py      # Intelligence extraction tests
│   └── manual_test.py          # Quick manual testing script
│
├── config.py                   # Configuration management
├── requirements.txt            # Python dependencies
└── .env.example                # Environment variable template
```

---

## 🎨 DETAILED COMPONENT SPECIFICATIONS

### Component 1: Detector Agent (`agents/detector_agent.py`)

**Purpose:** Analyze incoming message and classify as scam or legitimate

**Class Structure:**

```python
class DetectorAgent:
    def __init__(self, api_key: str, model_name: str)
    def detect_scam(self, message: str, history: List[Dict]) -> Dict[str, Any]
```

**Input:**

- `message`: String containing the scam message text
- `history`: List of previous conversation messages for context

**Output:**

```python
{
    "is_scam": True/False,
    "confidence": 0.0-1.0,  # Float
    "reason": "Explanation of why it's a scam",
    "indicators": ["urgency", "suspicious link", "request for OTP"]  # List of detected patterns
}
```

**AI Prompt Requirements:**

```
System Prompt for Gemini:
- You are a scam detection expert analyzing messages
- Look for: urgency language, suspicious URLs, requests for sensitive info (OTP/password/bank details), impersonation of authorities
- Return ONLY valid JSON with keys: is_scam, confidence, reason, indicators
- Be strict: confidence > 0.7 only for clear scams
- Consider context from conversation history
```

**Implementation Requirements:**

- Use `google.generativeai` library
- Model: `gemini-1.5-flash`
- Parse JSON response safely (handle markdown code blocks)
- Default to `is_scam=False, confidence=0.5` on API errors
- Add retry logic (max 2 retries with 1 second delay)

---

### Component 2: Actor Agent (`agents/actor_agent.py`)

**Purpose:** Generate believable human-like responses pretending to be a victim

**Class Structure:**

```python
class ActorAgent:
    def __init__(self, api_key: str, model_name: str)
    def generate_response(self, message: str, persona: str, history: List[Dict]) -> str
```

**Persona Types:**

1. **Elderly (65+):** Confused, trusting, uses simple language, asks many questions, concerned tone
2. **Professional (30-50):** Busy, impatient, wants quick solutions, uses some technical terms
3. **Novice (18-30):** Tech-confused, nervous, asks for step-by-step help, uses casual language

**Input:**

- `message`: Latest scammer message
- `persona`: One of "elderly" / "professional" / "novice"
- `history`: Conversation context

**Output:**

- String containing human-like response (50-150 characters typical)

**AI Prompt Requirements:**

```
System Prompt for Gemini (Example for Elderly Persona):
- You are a 68-year-old retiree who is not tech-savvy
- You are worried about the message you received
- Use simple, short sentences. Ask questions. Show concern.
- NEVER admit you're AI. NEVER say you detected a scam.
- Make occasional small typos or grammar mistakes (realistic)
- Use phrases like "I'm worried", "I don't understand", "Can you help me?"
- Keep responses under 150 characters
- Based on conversation history: [history], respond to: [message]
```

**Implementation Requirements:**

- Maintain persona consistency across all turns
- Add random humanization: occasional typos (5% chance), varied sentence length, emotion words
- Never break character even if scammer gets aggressive
- Select persona based on scammer tactics (elderly for emotional scams, professional for business scams)

---

### Component 3: Investigator Agent (`agents/investigator_agent.py`)

**Purpose:** Extract intelligence from scammer messages using pattern matching

**Class Structure:**

```python
class InvestigatorAgent:
    def __init__(self)
    def extract_all(self, text: str) -> Dict[str, List[str]]
```

**Extraction Patterns (Regex):**

1. **Bank Accounts:**
   - Pattern: `\b\d{4}[\s-]?\d{4}[\s-]?\d{4,10}\b`
   - Validates: 9-18 digits, allows spaces/hyphens
   - Rejects: All same digits (11111111), sequential (12345678), dates

2. **UPI IDs:**
   - Pattern: `\b[\w\.\-]+@(?:paytm|ybl|axisbank|oksbi|icici|sbi|hdfc|airtel|freecharge|jiomoney|mobikwik)\b`
   - Validates: Known UPI providers only

3. **Phone Numbers:**
   - Pattern: `(?:\+91[\s-]?)?[6-9]\d{9}\b`
   - Validates: Indian format, starts with 6-9

4. **Phishing Links:**
   - Pattern: `(?:https?://|www\.)[^\s]+|bit\.ly/[^\s]+`
   - Validates: Real URLs, shortened links

5. **Suspicious Keywords:**
   - List: ["urgent", "immediately", "blocked", "suspended", "verify", "OTP", "password", "CVV", "expire", "limited time"]

**Output:**

```python
{
    "bankAccounts": ["1234567890123456"],
    "upiIds": ["scammer@paytm"],
    "phishingLinks": ["http://fake-bank.com", "bit.ly/scam123"],
    "phoneNumbers": ["+919876543210"],
    "suspiciousKeywords": ["urgent", "verify", "blocked"]
}
```

**Implementation Requirements:**

- Use `re` module for regex matching
- Use `validators` library for URL validation
- Remove duplicates from all lists
- Validate each extraction (bank account checksums, UPI provider whitelist)

---

### Component 4: Session Manager (`agents/session_manager.py`)

**Purpose:** Track conversation state across multiple message turns

**Class Structure:**

```python
class SessionManager:
    def __init__(self)
    def get_or_create_session(self, session_id: str) -> Dict
    def update_intelligence(self, session_id: str, new_intel: Dict) -> None
    def increment_turn(self, session_id: str) -> int
    def should_end_conversation(self, session_id: str) -> bool
    def get_session_summary(self, session_id: str) -> Dict
```

**Session State Structure:**

```python
{
    "session_id": "abc-123",
    "turn_count": 5,
    "scam_detected": True,
    "persona_used": "elderly",
    "intelligence": {
        "bankAccounts": [...],
        "upiIds": [...],
        "phishingLinks": [...],
        "phoneNumbers": [...],
        "suspiciousKeywords": [...]
    },
    "conversation_active": True,
    "last_intelligence_turn": 3,  # Track when we last found something
    "created_at": "2026-01-27T10:00:00Z"
}
```

**Conversation End Logic:**

```python
def should_end_conversation(session_id):
    # End if ANY of these conditions:
    # 1. Found at least 2 types of intelligence (e.g., 1 UPI + 1 phone)
    # 2. Turn count >= 20 (prevent infinite loops)
    # 3. No new intelligence in last 5 turns (conversation is stale)
    # Return: Boolean
```

**Implementation Requirements:**

- Store sessions in memory (Python dict)
- Merge intelligence without duplicates (use sets)
- Thread-safe for concurrent requests (use `threading.Lock`)

---

### Component 5: Orchestrator (`agents/orchestrator.py`)

**Purpose:** Coordinate all three agents and manage conversation flow

**Class Structure:**

```python
class Orchestrator:
    def __init__(self, detector: DetectorAgent, actor: ActorAgent, investigator: InvestigatorAgent, session_manager: SessionManager)
    def process_message(self, session_id: str, message: Dict, history: List[Dict], metadata: Dict) -> Dict
```

**Processing Flow:**

```
1. Get or create session from session manager
2. Extract message text from message dict
3. Call detector agent IF first message OR confidence was low before
4. If scam detected (confidence > 0.7):
   a. Select persona based on metadata (channel, language) and scammer tactics
   b. Call actor agent to generate response
5. Call investigator agent to extract intelligence from scammer's message
6. Update session with new intelligence
7. Increment turn count
8. Check if conversation should end
9. Build and return response dict
```

**Output Format:**

```python
{
    "status": "success",
    "scamDetected": True,
    "agentResponse": "Oh no! What should I do? I'm so worried!",
    "extractedIntelligence": {
        "bankAccounts": [...],
        "upiIds": [...],
        "phishingLinks": [...],
        "phoneNumbers": [...],
        "suspiciousKeywords": [...]
    },
    "engagementMetrics": {
        "conversationTurn": 5,
        "responseTimeMs": 1842,
        "totalIntelligenceItems": 3
    },
    "continueConversation": True,  # False if should end
    "agentNotes": "Scammer using urgency tactics, requested UPI payment"
}
```

---

### Component 6: FastAPI Server (`api/main.py`)

**Purpose:** Provide REST API endpoint that receives requests from GUVI

**Required Endpoints:**

1. **Health Check:**

```python
@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}
```

1. **Main Analysis Endpoint:**

```python
@app.post("/analyze")
async def analyze_scam_message(
    data: IncomingMessage,
    x_api_key: str = Header(None)
):
    # 1. Validate API key
    # 2. Call orchestrator.process_message()
    # 3. If continueConversation is False, trigger callback
    # 4. Return response
```

**Request Model (`api/models.py`):**

```python
class IncomingMessage(BaseModel):
    sessionId: str
    message: dict  # {sender: str, text: str, timestamp: str}
    conversationHistory: List[dict]
    metadata: dict  # {channel: str, language: str, locale: str}
```

**Response Model:**

```python
class ApiResponse(BaseModel):
    status: str
    scamDetected: bool
    agentResponse: str
    extractedIntelligence: dict
    engagementMetrics: dict
    continueConversation: bool
```

**Implementation Requirements:**

- Add CORS middleware for React dashboard
- Use dependency injection for orchestrator
- Add request logging (timestamp, session_id, endpoint)
- Handle errors gracefully (return 500 with error message, never crash)
- Add request timeout (30 seconds max)

---

### Component 7: GUVI Callback Handler (`api/callback.py`)

**Purpose:** Send final intelligence summary to GUVI when conversation ends

**Function Structure:**

```python
async def send_final_callback(session_id: str, final_data: Dict) -> bool:
    # POST to: https://hackathon.guvi.in/api/updateHoneyPotFinalResult
    # Returns: True if successful, False if all retries failed
```

**Payload Format:**

```python
{
    "sessionId": "abc-123",
    "scamDetected": True,
    "totalMessagesExchanged": 12,
    "extractedIntelligence": {
        "bankAccounts": [...],
        "upiIds": [...],
        "phishingLinks": [...],
        "phoneNumbers": [...],
        "suspiciousKeywords": [...]
    },
    "agentNotes": "Scammer impersonated bank, requested OTP and UPI payment. Successfully extracted 2 UPI IDs and 1 phone number through 12-turn engagement."
}
```

**Implementation Requirements:**

- Use `httpx` library for async HTTP requests
- Retry logic: 3 attempts with exponential backoff (2s, 4s, 8s)
- Timeout: 10 seconds per attempt
- Logging: INFO on success, ERROR on failure with details
- Never throw exception (return False instead)

---

### Component 8: Intelligence Extractors (`intelligence/extractors.py`)

**Complete Implementation:**

```python
import re
from typing import Dict, List
import validators

class IntelligenceExtractor:
    def __init__(self):
        # Regex patterns
        self.patterns = {
            'bank_account': r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4,10}\b',
            'upi_id': r'\b[\w\.\-]+@(?:paytm|ybl|axisbank|oksbi|icici|sbi|hdfc|airtel|freecharge|jiomoney|mobikwik)\b',
            'phone': r'(?:\+91[\s-]?)?[6-9]\d{9}\b',
            'url': r'(?:https?://|www\.)[^\s]+|bit\.ly/[^\s]+'
        }
        
        # Scam keyword database
        self.scam_keywords = [
            "urgent", "immediately", "blocked", "suspended", "verify",
            "OTP", "password", "CVV", "expire", "limited time", "act now",
            "account closed", "confirm identity", "click here"
        ]
    
    def extract_all(self, text: str) -> Dict[str, List[str]]:
        return {
            "bankAccounts": self.extract_bank_accounts(text),
            "upiIds": self.extract_upi_ids(text),
            "phoneNumbers": self.extract_phone_numbers(text),
            "phishingLinks": self.extract_urls(text),
            "suspiciousKeywords": self.extract_keywords(text)
        }
    
    def extract_bank_accounts(self, text: str) -> List[str]:
        matches = re.findall(self.patterns['bank_account'], text)
        validated = []
        for match in matches:
            clean = match.replace(' ', '').replace('-', '')
            if self.is_valid_bank_account(clean):
                validated.append(clean)
        return list(set(validated))  # Remove duplicates
    
    def is_valid_bank_account(self, number: str) -> bool:
        # Check length
        if len(number) < 9 or len(number) > 18:
            return False
        # Reject all same digits
        if len(set(number)) < 3:
            return False
        # Reject sequential
        if number in ['123456789', '987654321', '1234567890']:
            return False
        return True
    
    # Similar methods for UPI, phone, URLs, keywords...
```

---

### Component 9: Test Suite (`tests/test_api.py`)

**Required Tests:**

1. **Test Scam Detection:**

```python
def test_analyze_detects_scam():
    response = client.post("/analyze", headers=headers, json=scam_message)
    assert response.status_code == 200
    assert response.json()["scamDetected"] == True
    assert response.json()["extractedIntelligence"]["phishingLinks"] != []
```

1. **Test Multi-Turn Conversation:**

```python
def test_multi_turn_maintains_context():
    # Send 3 messages in sequence
    # Assert intelligence accumulates
    # Assert persona stays consistent
```

1. **Test Authentication:**

```python
def test_invalid_api_key_returns_401():
    response = client.post("/analyze", headers={"x-api-key": "wrong"}, json=message)
    assert response.status_code == 401
```

1. **Test Conversation End:**

```python
def test_ends_after_max_turns():
    # Send 20 messages
    # Assert continueConversation becomes False
```

---

## 🔧 CONFIGURATION REQUIREMENTS

### Environment Variables (`.env`)

```bash
# AI Provider
GEMINI_API_KEY=AIzaSyC_your_key_here
AI_PROVIDER=gemini

# API Security
API_SECRET_KEY=strong-random-secret-key-here

# GUVI Integration
GUVI_CALLBACK_URL=https://hackathon.guvi.in/api/updateHoneyPotFinalResult

# Agent Behavior
MAX_CONVERSATION_TURNS=20
MIN_INTELLIGENCE_THRESHOLD=2
STALE_CONVERSATION_THRESHOLD=5

# Performance
API_TIMEOUT=30
```

### Dependencies (`requirements.txt`)

```
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.3
google-generativeai==0.3.2
requests==2.31.0
httpx==0.26.0
python-dotenv==1.0.0
validators==0.22.0
pytest==7.4.3
pytest-asyncio==0.21.1
```

---

## 🎯 CODE GENERATION INSTRUCTIONS FOR GEMINI

When generating code, follow these principles:

1. **Complete Implementations:** Generate full working code, not stubs or TODOs
2. **Error Handling:** Wrap external calls in try-except with meaningful error messages
3. **Type Hints:** Use Python type hints for all function parameters and returns
4. **Docstrings:** Add Google-style docstrings to all classes and functions
5. **Comments:** Explain complex logic inline
6. **Validation:** Validate all inputs before processing
7. **Logging:** Add logging for debugging (use Python `logging` module)
8. **Testing:** Generate corresponding test for each function

### Example Code Quality Standard

```python
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class DetectorAgent:
    """
    Scam detection agent using Gemini API.
    
    This agent analyzes incoming messages and classifies them as scam
    or legitimate with a confidence score.
    
    Attributes:
        api_key (str): Gemini API key
        model_name (str): Gemini model identifier
        client: Gemini API client
    """
    
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash"):
        """
        Initialize the detector agent.
        
        Args:
            api_key: Gemini API key
            model_name: Model to use (default: gemini-1.5-flash)
            
        Raises:
            ValueError: If api_key is empty
        """
        if not api_key:
            raise ValueError("API key cannot be empty")
            
        self.api_key = api_key
        self.model_name = model_name
        self.client = self._initialize_client()
        logger.info(f"DetectorAgent initialized with model: {model_name}")
    
    def _initialize_client(self):
        """Initialize Gemini API client."""
        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        return genai.GenerativeModel(self.model_name)
    
    def detect_scam(self, message: str, history: Optional[List[Dict]] = None) -> Dict[str, any]:
        """
        Detect if a message is a scam.
        
        Args:
            message: Message text to analyze
            history: Optional conversation history for context
            
        Returns:
            Dict containing:
                - is_scam (bool): Whether message is a scam
                - confidence (float): Confidence score 0.0-1.0
                - reason (str): Explanation
                - indicators (List[str]): Detected scam patterns
                
        Raises:
            None: Returns default response on error
        """
        if not message or len(message.strip()) == 0:
            logger.warning("Empty message received")
            return self._default_response()
        
        try:
            # Construct prompt with history context
            prompt = self._build_detection_prompt(message, history or [])
            
            # Call Gemini API
            response = self.client.generate_content(prompt)
            
            # Parse JSON response
            result = self._parse_response(response.text)
            
            logger.info(f"Scam detection complete: {result['is_scam']} (confidence: {result['confidence']})")
            return result
            
        except Exception as e:
            logger.error(f"Error detecting scam: {str(e)}")
            return self._default_response()
    
    def _build_detection_prompt(self, message: str, history: List[Dict]) -> str:
        """Build the prompt for Gemini."""
        # Implementation...
        
    def _parse_response(self, response_text: str) -> Dict:
        """Safely parse JSON from Gemini response."""
        # Implementation...
        
    def _default_response(self) -> Dict:
        """Return default response on error."""
        return {
            "is_scam": False,
            "confidence": 0.5,
            "reason": "Unable to analyze message",
            "indicators": []
        }
```

---

## ⚠️ CRITICAL REQUIREMENTS - MUST IMPLEMENT

1. **NEVER use localStorage or sessionStorage** (not supported in deployment)
2. **NEVER hardcode API keys** (use environment variables only)
3. **NEVER expose .env file** (add to .gitignore)
4. **ALWAYS validate inputs** (check for None, empty strings, invalid formats)
5. **ALWAYS handle Gemini API errors** (timeout, rate limits, invalid responses)
6. **ALWAYS send callback** when conversation ends (this is mandatory for scoring)
7. **ALWAYS maintain persona consistency** (agent must not break character)
8. **ALWAYS accumulate intelligence** (merge across turns, no duplicates)

---

## 🚀 USAGE INSTRUCTIONS

### For Gemini CLI

```bash
# Generate a complete component
gemini "Based on GEMINI.md, generate complete Python code for agents/detector_agent.py with all methods implemented, error handling, type hints, and docstrings"

# Generate tests
gemini "Based on GEMINI.md specifications for DetectorAgent, generate complete pytest test suite in tests/test_agents.py covering scam detection, error handling, and edge cases"

# Debug an issue
gemini "I'm getting error [paste error]. Based on GEMINI.md architecture, what's wrong and how do I fix it? Here's my code: [paste code]"
```

### For Development

1. Read this entire document first
2. Understand the architecture
3. Generate one component at a time
4. Test each component before moving to next
5. Integrate components incrementally

---

**This document contains complete specifications for building the Honeypot Agent system. Use it as context when prompting Gemini CLI to generate accurate, production-ready code.**
