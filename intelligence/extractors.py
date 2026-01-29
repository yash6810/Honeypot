"""
Centralized regex patterns and keyword lists for intelligence extraction.
"""

from typing import Dict, List, Set

# Regex patterns for various types of intelligence
PATTERNS: Dict[str, str] = {
    'bank_account': r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4,10}\b', # 9-18 digits, allows spaces/hyphens
    'upi_id': r'\b[\w\.\-]+@(?:paytm|ybl|axisbank|oksbi|icici|sbi|hdfc|airtel|freecharge|jiomoney|mobikwik|apl|okicici|okaxis|tmp)\b', # Common UPI providers
    'phone': r'(?:\+91[\s-]?)?[6-9]\d{9}\b', # Indian mobile numbers, optionally with +91 prefix
    'url': r'(?:https?://|www\.)[^\s]+', # General URL pattern (http/https/www)
    'bitly_url': r'bit\.ly/[^\s]+' # Specific pattern for bit.ly shortened URLs
}

# Set of suspicious keywords used for scam detection
SCAM_KEYWORDS: Set[str] = {
    "urgent", "immediately", "blocked", "suspended", "verify",
    "OTP", "password", "CVV", "expire", "limited time", "act now",
    "account closed", "confirm identity", "click here", "debit", "credit",
    "transaction", "kyc", "bank", "financial", "loan", "lucky draw",
    "prize", "winning", "redeem", "cashback", "reward", "congratulations",
    "fund", "transfer", "link", "application", "form", "secret", "code",
    "security", "fraud", "alert", "problem", "issue", "restore", "validate",
    "investment", "opportunity", "profit", "money", "fee", "tax", "customs",
    "delivery", "package", "shipment", "update", "attention", "warning",
    "confirm", "personal", "information", "details", "contact", "official",
    "government", "police", "court", "arrest", "warrant", "fine", "penalty"
}

if __name__ == '__main__':
    print("--- Intelligence Patterns ---")
    for key, value in PATTERNS.items():
        print(f"{key}: {value}")
    
    print("\n--- Scam Keywords (first 10) ---")
    for i, keyword in enumerate(list(SCAM_KEYWORDS)[:10]):
        print(f"- {keyword}")
