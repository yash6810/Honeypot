"""
Validation functions for extracted intelligence.
"""
import re
import validators
import logging

logger = logging.getLogger(__name__)

def is_valid_bank_account(number: str) -> bool:
    """
    Validates a cleaned bank account number.
    Criteria: 9-18 digits, not all same, not simple sequential.
    """
    if not (9 <= len(number) <= 18) or not number.isdigit():
        logger.debug(f"Bank account '{number}' failed length/digit check.")
        return False
    if len(set(number)) == 1: # e.g., "111111111"
        logger.debug(f"Bank account '{number}' failed all-same-digits check.")
        return False
    # Simple check for highly sequential numbers (e.g., 123456789 or 987654321)
    if '123456789' in number or '987654321' in number:
        logger.debug(f"Bank account '{number}' failed sequential check.")
        return False
    return True

def is_valid_url(url: str) -> bool:
    """
    Validates a URL using the 'validators' library.
    """
    try:
        return validators.url(url)
    except Exception as e:
        logger.debug(f"URL validation failed for {url}: {e}")
        return False

if __name__ == '__main__':
    # Test cases for bank account validation
    print("--- Testing Bank Account Validation ---")
    print(f"'1234567890123456': {is_valid_bank_account('1234567890123456')}") # True
    print(f"'12345678': {is_valid_bank_account('12345678')}")       # False (too short)
    print(f"'1234567890123456789': {is_valid_bank_account('1234567890123456789')}") # False (too long)
    print(f"'1111111111111111': {is_valid_bank_account('1111111111111111')}") # False (all same)
    print(f"'123456789': {is_valid_bank_account('123456789')}")         # False (sequential)
    print(f"'987654321': {is_valid_bank_account('987654321')}")         # False (sequential)
    print(f"'123A567890': {is_valid_bank_account('123A567890')}")     # False (non-digit)
    print(f"'123456789012': {is_valid_bank_account('123456789012')}") # True

    # Test cases for URL validation
    print("\n--- Testing URL Validation ---")
    print(f"'https://www.google.com': {is_valid_url('https://www.google.com')}") # True
    print(f"'http://bit.ly/test': {is_valid_url('http://bit.ly/test')}")         # True
    print(f"'invalid-url': {is_valid_url('invalid-url')}")                     # False
    print(f"'ftp://example.com': {is_valid_url('ftp://example.com')}")         # True (validators supports ftp)
    print(f"'www.example.com': {is_valid_url('www.example.com')}")             # True
    print(f"'justtext': {is_valid_url('justtext')}")                           # False

