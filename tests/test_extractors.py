"""
Test suite for intelligence extraction and validation functions.
Covers intelligence/extractors.py and intelligence/validators.py.
"""
import pytest
import re
from intelligence.extractors import PATTERNS, SCAM_KEYWORDS
from intelligence.validators import is_valid_bank_account, is_valid_url
from agents.investigator_agent import InvestigatorAgent # To test the integration of extractors/validators


# --- Test intelligence/validators.py ---

def test_is_valid_bank_account():
    """Test various scenarios for bank account validation."""
    # Valid cases
    assert is_valid_bank_account("1234567890123456") is True
    assert is_valid_bank_account("9876543210987") is True
    assert is_valid_bank_account("55554444333322221") is True # 17 digits

    # Invalid cases: length
    assert is_valid_bank_account("12345678") is False  # Too short
    assert is_valid_bank_account("1234567890123456789") is False # Too long
    assert is_valid_bank_account("") is False # Empty

    # Invalid cases: non-digits
    assert is_valid_bank_account("123A4567890") is False

    # Invalid cases: all same digits
    assert is_valid_bank_account("1111111111111111") is False
    assert is_valid_bank_account("0000000000000000") is False

    # Invalid cases: simple sequential
    assert is_valid_bank_account("1234567890") is False
    assert is_valid_bank_account("9876543210") is False
    assert is_valid_bank_account("0123456789") is False


def test_is_valid_url():
    """Test various scenarios for URL validation."""
    # Valid cases
    assert is_valid_url("https://www.google.com") is True
    assert is_valid_url("http://example.com/path?query=1") is True
    assert is_valid_url("www.sub.domain.co.uk") is True
    assert is_valid_url("bit.ly/shortlink") is True
    assert is_valid_url("ftp://fileserver.com/doc.pdf") is True # validators supports FTP
    assert is_valid_url("https://192.168.1.1/admin") is True # IP address URL

    # Invalid cases
    assert is_valid_url("not-a-url") is False
    assert is_valid_url("example.com") is False # Missing schema or www.
    assert is_valid_url("google") is False
    assert is_valid_url("http:/missing.slash.com") is False
    assert is_valid_url("") is False


# --- Test intelligence/extractors.py (via InvestigatorAgent for practical application) ---

@pytest.fixture(name="investigator")
def investigator_fixture():
    """Provides an InvestigatorAgent instance for testing."""
    return InvestigatorAgent()

def test_extract_bank_accounts(investigator: InvestigatorAgent):
    """Test bank account extraction with valid and invalid patterns."""
    text = "My account is 1234-5678-90123456 and also 9876 5432 1098. Invalid: 1111-2222-3333-4444 (all same). Also check 1234567890. Another valid 5555-5555-5555-5555555"
    accounts = investigator.extract_bank_accounts(text)
    assert "1234567890123456" in accounts
    assert "987654321098" in accounts
    assert "55555555555555555" in accounts
    assert "1111222233334444" not in accounts # All same digits rule
    assert "1234567890" not in accounts # Sequential digits rule


def test_extract_upi_ids(investigator: InvestigatorAgent):
    """Test UPI ID extraction."""
    text = "My UPI ID is user@paytm and another one is john.doe@ybl. Ignore email@example.com."
    upi_ids = investigator.extract_upi_ids(text)
    assert "user@paytm" in upi_ids
    assert "john.doe@ybl" in upi_ids
    assert "email@example.com" not in upi_ids
    assert len(upi_ids) == 2


def test_extract_phone_numbers(investigator: InvestigatorAgent):
    """Test phone number extraction."""
    text = "Call me at +919876543210 or 8765432109. Not 123456789 (too short) or +911234567890 (invalid start digit)."
    phone_numbers = investigator.extract_phone_numbers(text)
    assert "+919876543210" in phone_numbers
    assert "8765432109" in phone_numbers
    assert "+911234567890" not in phone_numbers # Invalid starting digit (1)
    assert len(phone_numbers) == 2


def test_extract_phishing_links(investigator: InvestigatorAgent):
    """Test phishing link extraction."""
    text = "Visit http://phishing.com/scam and also bit.ly/malicious. This is not a link: example.com. Good link: https://valid.org/safe"
    links = investigator.extract_phishing_links(text)
    assert "http://phishing.com/scam" in links
    assert "bit.ly/malicious" in links
    assert "https://valid.org/safe" in links # Should also detect valid URLs
    assert "example.com" not in links # Should not detect just domain without schema/www.
    assert len(links) == 3


def test_extract_keywords(investigator: InvestigatorAgent):
    """Test suspicious keyword extraction."""
    text = "This is an urgent message to verify your account immediately. Click here!"
    keywords = investigator.extract_keywords(text)
    assert "urgent" in keywords
    assert "verify" in keywords
    assert "immediately" in keywords
    assert "account" in keywords
    assert "click here" in keywords
    assert "message" not in keywords # Not a scam keyword


def test_extract_all_combined(investigator: InvestigatorAgent):
    """Test combined extraction of all intelligence types."""
    text = (
        "URGENT: Your account 1234-5678-90123456 has been suspended. "
        "Visit http://scam.site to verify. Call +919988776655. "
        "Send funds to user@axisbank. This is a limited time offer."
    )
    all_intel = investigator.extract_all(text)

    assert "1234567890123456" in all_intel["bankAccounts"]
    assert "http://scam.site" in all_intel["phishingLinks"]
    assert "+919988776655" in all_intel["phoneNumbers"]
    assert "user@axisbank" in all_intel["upiIds"]
    assert "urgent" in all_intel["suspiciousKeywords"]
    assert "suspended" in all_intel["suspiciousKeywords"]
    assert "limited time" in all_intel["suspiciousKeywords"]

    assert len(all_intel["bankAccounts"]) == 1
    assert len(all_intel["phishingLinks"]) == 1
    assert len(all_intel["phoneNumbers"]) == 1
    assert len(all_intel["upiIds"]) == 1
    assert len(all_intel["suspiciousKeywords"]) >= 3 # Depends on exact keyword list
