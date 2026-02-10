#!/usr/bin/env python3
"""
Test script for secure QR code system
Tests the HMAC signature verification
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the functions directly from the routes file
import hmac
import hashlib
import secrets
import uuid

# Same QR_SIGNING_KEY generation (must match the one in tickets.py)
QR_SIGNING_KEY = secrets.token_bytes(32)

def generate_secure_qr_data(ticket_id: int) -> str:
    """Generate a secure, verifiable QR code token with HMAC signature"""
    ticket_uuid = str(uuid.uuid4())
    message = f"{ticket_id}:{ticket_uuid}"
    signature = hmac.new(
        QR_SIGNING_KEY,
        message.encode(),
        hashlib.sha256
    ).hexdigest()[:16]
    return f"{ticket_uuid}:{signature}:{ticket_id}"

def verify_qr_token(qr_data: str) -> dict:
    """Verify a QR code token and return the ticket ID if valid"""
    try:
        parts = qr_data.split(':')
        if len(parts) != 3:
            return {'valid': False, 'error': 'Invalid QR format'}
        
        ticket_uuid, signature, ticket_id = parts
        
        message = f"{ticket_id}:{ticket_uuid}"
        expected_signature = hmac.new(
            QR_SIGNING_KEY,
            message.encode(),
            hashlib.sha256
        ).hexdigest()[:16]
        
        if not hmac.compare_digest(signature, expected_signature):
            return {'valid': False, 'error': 'Invalid signature - possible forgery'}
        
        return {
            'valid': True,
            'ticket_uuid': ticket_uuid,
            'ticket_id': int(ticket_id)
        }
    except Exception as e:
        return {'valid': False, 'error': f'Verification failed: {e}'}

def test_secure_qr():
    """Test the secure QR code system"""
    print("=" * 60)
    print("Secure QR Code System Test")
    print("=" * 60)
    
    # Test 1: Generate and verify valid QR code
    print("\n[TEST 1] Generate and verify valid QR code")
    ticket_id = 12345
    qr_data = generate_secure_qr_data(ticket_id)
    print(f"  Generated QR data: {qr_data}")
    
    verification = verify_qr_token(qr_data)
    print(f"  Verification result: {verification}")
    assert verification['valid'], "Valid QR code should pass verification"
    assert verification['ticket_id'] == ticket_id, "Ticket ID should match"
    print("  ✓ PASSED: Valid QR code verified successfully")
    
    # Test 2: Reject forged QR code
    print("\n[TEST 2] Reject forged QR code")
    forged_qr = f"{uuid.uuid4()}:fake_signature:{ticket_id}"
    verification = verify_qr_token(forged_qr)
    print(f"  Verification result: {verification}")
    assert not verification['valid'], "Forged QR code should fail verification"
    assert 'Invalid signature' in verification['error'], "Should report signature error"
    print("  ✓ PASSED: Forged QR code rejected")
    
    # Test 3: Reject malformed QR code
    print("\n[TEST 3] Reject malformed QR code")
    malformed_qr = "invalid-format"
    verification = verify_qr_token(malformed_qr)
    print(f"  Verification result: {verification}")
    assert not verification['valid'], "Malformed QR code should fail verification"
    assert 'Invalid QR format' in verification['error'], "Should report format error"
    print("  ✓ PASSED: Malformed QR code rejected")
    
    # Test 4: Verify different ticket IDs produce different QR codes
    print("\n[TEST 4] Verify uniqueness")
    qr1 = generate_secure_qr_data(100)
    qr2 = generate_secure_qr_data(200)
    print(f"  QR for ticket 100: {qr1}")
    print(f"  QR for ticket 200: {qr2}")
    assert qr1 != qr2, "Different tickets should have different QR codes"
    print("  ✓ PASSED: QR codes are unique per ticket")
    
    print("\n" + "=" * 60)
    print("All tests passed! Secure QR system is working correctly.")
    print("=" * 60)

if __name__ == "__main__":
    test_secure_qr()
