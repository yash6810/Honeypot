"""
Component 3: Investigator Agent
"""
import re
import logging
from typing import Dict, List, Any, Set
import json

from intelligence.validators import is_valid_bank_account, is_valid_url # Import from new module
from intelligence.extractors import PATTERNS, SCAM_KEYWORDS # Import from new module

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InvestigatorAgent:
    """
    Extracts intelligence from text using predefined regex patterns and validation rules.
    This includes bank accounts, UPI IDs, phone numbers, phishing links, and suspicious keywords.
    """

    def __init__(self):
        """
        Initializes the InvestigatorAgent. Patterns and keywords are loaded from intelligence.extractors.
        """
        self.patterns = PATTERNS
        self.scam_keywords = SCAM_KEYWORDS
        logger.info("InvestigatorAgent initialized with extraction patterns and keywords.")

    def extract_bank_accounts(self, text: str) -> List[str]:
        """Extracts and validates bank account numbers from text."""
        found_accounts = set()
        for match in re.finditer(self.patterns['bank_account'], text):
            clean_number = re.sub(r'[\s-]', '', match.group(0))
            if is_valid_bank_account(clean_number): # Use imported validator
                found_accounts.add(clean_number)
        return sorted(list(found_accounts))

    def extract_upi_ids(self, text: str) -> List[str]:
        """Extracts and validates UPI IDs from text."""
        found_upi_ids = set()
        for match in re.finditer(self.patterns['upi_id'], text, re.IGNORECASE):
            found_upi_ids.add(match.group(0).lower()) # Store in lowercase for consistency
        return sorted(list(found_upi_ids))

    def extract_phone_numbers(self, text: str) -> List[str]:
        """Extracts and validates Indian phone numbers from text."""
        found_numbers = set()
        # Use a more robust pattern if necessary, this simple one is for 10 digits
        # and optional +91 prefix.
        for match in re.finditer(self.patterns['phone'], text):
            clean_number = re.sub(r'[\s-]', '', match.group(0))
            # Basic validation: ensure it's 10 digits if +91 is not present, or 12 if +91 is present
            if clean_number.startswith('+91') and len(clean_number) == 13 and clean_number[3:].isdigit():
                found_numbers.add(clean_number)
            elif len(clean_number) == 10 and clean_number.isdigit():
                found_numbers.add(clean_number)
        return sorted(list(found_numbers))

    def extract_phishing_links(self, text: str) -> List[str]:
        """Extracts and validates URLs, including bit.ly links, from text."""
        found_urls = set()
        for pattern_name in ['url', 'bitly_url']:
            for match in re.finditer(self.patterns[pattern_name], text, re.IGNORECASE):
                url = match.group(0)
                # Remove trailing punctuation that might be part of the sentence not the URL
                cleaned_url = url.strip(".,;!?\"'")
                if is_valid_url(cleaned_url): # Use imported validator
                    found_urls.add(cleaned_url)
        return sorted(list(found_urls))

    def extract_keywords(self, text: str) -> List[str]:
        """Extracts suspicious keywords from text (case-insensitive)."""
        found_keywords = set()
        text_lower = text.lower()
        for keyword in self.scam_keywords:
            if keyword in text_lower:
                found_keywords.add(keyword)
        return sorted(list(found_keywords))

    def extract_all(self, text: str) -> Dict[str, List[str]]:
        """
        Extracts all types of intelligence (bank accounts, UPI IDs, phone numbers,
        phishing links, and suspicious keywords) from the given text.

        Args:
            text: The message text to analyze.

        Returns:
            A dictionary where keys are intelligence types and values are lists of extracted strings.
        """
        if not text or not text.strip():
            return {
                "bankAccounts": [],
                "upiIds": [],
                "phishingLinks": [],
                "phoneNumbers": [],
                "suspiciousKeywords": []
            }

        extracted_data = {
            "bankAccounts": self.extract_bank_accounts(text),
            "upiIds": self.extract_upi_ids(text),
            "phishingLinks": self.extract_phishing_links(text),
            "phoneNumbers": self.extract_phone_numbers(text),
            "suspiciousKeywords": self.extract_keywords(text)
        }
        logger.debug(f"Extracted intelligence: {extracted_data}")
        return extracted_data

if __name__ == '__main__':
    # Simple test block for InvestigatorAgent
    investigator = InvestigatorAgent()

    test_message_1 = (
        "Your account 1234-5678-9012345 has been blocked. "
        "Click this urgent link: http://bit.ly/malicious. "
        "Contact +919876543210 or send money to scammer@paytm immediately."
    )
    print("--- Test Message 1 ---")
    results_1 = investigator.extract_all(test_message_1)
    print(json.dumps(results_1, indent=2))
    # Expected: 1 bank account, 1 UPI ID, 1 phone number, 1 phishing link, multiple keywords

    test_message_2 = (
        "Hello, this is a normal message without any suspicious elements. "
        "My number is 7890123456. "
        "Visit www.example.com for more info. "
        "My account is 9876543210 (invalid, too short)."
    )
    print("\n--- Test Message 2 ---")
    results_2 = investigator.extract_all(test_message_2)
    print(json.dumps(results_2, indent=2))
    # Expected: 1 phone number, 1 phishing link, no bank accounts or UPI IDs, some keywords if "account" is in list

    test_message_3 = "Just a friendly reminder. No urgent requests."
    print("\n--- Test Message 3 ---")
    results_3 = investigator.extract_all(test_message_3)
    print(json.dumps(results_3, indent=2))
    # Expected: No intelligence extracted
