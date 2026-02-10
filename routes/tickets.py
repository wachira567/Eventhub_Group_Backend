"""
Tickets Routes
"""

from flask import Blueprint, request, jsonify, send_file, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from datetime import datetime
from sqlalchemy import and_, or_
import io
import base64
import qrcode
import secrets
import uuid
import hmac
import hashlib
import logging
import os
from extensions import db

logger = logging.getLogger(__name__)
from models import (
    Ticket,
    TicketTypeModel,
    Event,
    User,
    UserRole,
    MpesaTransaction,
    EventStatus,
)
from services.pdf_service import generate_ticket_pdf
from services.email_service import send_ticket_with_pdf


# Secret key for signing QR codes (loaded from environment or use stable fallback)
QR_SIGNING_KEY = os.environ.get(
    "QR_SIGNING_KEY", b"event-hub-qr-secret-key-32bytes!"
).encode()



def generate_secure_qr_data(ticket_id: int) -> str:
    """Generate a secure, verifiable QR code token with HMAC signature"""
    # Generate a unique UUID for this ticket
    ticket_uuid = str(uuid.uuid4())

    # Create a signature using HMAC-SHA256
    message = f"{ticket_id}:{ticket_uuid}"
    signature = hmac.new(QR_SIGNING_KEY, message.encode(), hashlib.sha256).hexdigest()[
        :16
    ]  # Use first 16 chars for shorter QR

    # Return format: UUID:SIGNATURE:TICKET_ID
    return f"{ticket_uuid}:{signature}:{ticket_id}"

def verify_qr_token(qr_data: str) -> dict:
    """Verify a QR code token and return the ticket ID if valid"""
    try:
        parts = qr_data.split(":")
        if len(parts) != 3:
            logger.warning(
                f"verify_qr_token: Invalid QR format - expected 3 parts, got {len(parts)}"
            )
            return {"valid": False, "error": "Invalid QR format - expected 3 parts"}

        ticket_uuid, signature, ticket_id = parts

        logger.info(
            f"verify_qr_token: Parsed QR - uuid={ticket_uuid}, sig={signature}, ticket_id={ticket_id}"
        )
        logger.info(
            f"verify_qr_token: QR_SIGNING_KEY length={len(QR_SIGNING_KEY)}, key_hex={QR_SIGNING_KEY.hex()[:32]}..."
        )

        # Verify the signature
        message = f"{ticket_id}:{ticket_uuid}"
        logger.info(f"verify_qr_token: message='{message}'")

        expected_signature = hmac.new(
            QR_SIGNING_KEY, message.encode(), hashlib.sha256
        ).hexdigest()[:16]

        logger.info(
            f"verify_qr_token: provided_sig='{signature}', expected_sig='{expected_signature}'"
        )
        logger.info(f"verify_qr_token: match={signature == expected_signature}")

        if not hmac.compare_digest(signature, expected_signature):
            logger.warning(
                f"verify_qr_token: Signature mismatch - possible forgery or key mismatch"
            )
            return {"valid": False, "error": "Invalid signature - possible forgery"}

        return {"valid": True, "ticket_uuid": ticket_uuid, "ticket_id": int(ticket_id)}
    except Exception as e:
        logger.error(f"QR verification error: {e}", exc_info=True)
        return {"valid": False, "error": "Verification failed"}


def generate_qr_code(data: str) -> str:
    """Generate QR code as base64 string"""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()


tickets_bp = Blueprint("tickets", __name__)


# Health check endpoint
@tickets_bp.route("/debug/qr-key-check", methods=["GET"])
def debug_qr_key_check():
    """Debug endpoint to check QR signing key configuration"""
    try:
        import hmac
        import hashlib

        # Test with a sample message
        test_message = "test:12345"
        expected_sig = hmac.new(
            QR_SIGNING_KEY, test_message.encode(), hashlib.sha256
        ).hexdigest()[:16]

        return jsonify(
            {
                "qr_signing_key_length": len(QR_SIGNING_KEY),
                "qr_signing_key_type": type(QR_SIGNING_KEY).__name__,
                "qr_signing_key_hex": QR_SIGNING_KEY.hex()[:64] + "...",
                "test_signature": expected_sig,
                "status": "ok",
            }
        ), 200
    except Exception as e:
        logger.error(f"debug_qr_key_check error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


# Debug endpoint to check QR signing key and test verification
@tickets_bp.route("/debug/qr-test", methods=["POST"])
def debug_qr_test():
    """Debug endpoint to test QR verification"""
    try:
        data = request.get_json()
        qr_data = data.get("qr_data", "").strip()

        logger.info(f"debug_qr_test: Received QR data: {qr_data}")
        logger.info(f"debug_qr_test: QR_SIGNING_KEY length: {len(QR_SIGNING_KEY)}")

        if not qr_data:
            return jsonify(
                {
                    "error": "QR data is required",
                    "qr_signing_key_length": len(QR_SIGNING_KEY),
                }
            ), 400

        parts = qr_data.split(":")

        if len(parts) != 3:
            return jsonify(
                {
                    "valid": False,
                    "error": "Invalid QR format - expected 3 parts",
                    "parts_count": len(parts),
                    "qr_signing_key_length": len(QR_SIGNING_KEY),
                }
            ), 400

        ticket_uuid, signature, ticket_id = parts

        # Try to find the ticket regardless of signature
        try:
            ticket = Ticket.query.get(int(ticket_id))
        except:
            ticket = None

        # Calculate what the signature SHOULD be
        message = f"{ticket_id}:{ticket_uuid}"
        expected_signature = hmac.new(
            QR_SIGNING_KEY, message.encode(), hashlib.sha256
        ).hexdigest()[:16]

        return jsonify(
            {
                "qr_data_parts": {
                    "ticket_uuid": ticket_uuid,
                    "signature": signature,
                    "ticket_id": ticket_id,
                },
                "signature_analysis": {
                    "provided_signature": signature,
                    "expected_signature": expected_signature,
                    "match": signature == expected_signature,
                },
                "ticket_found": ticket is not None,
                "ticket_info": ticket.to_dict() if ticket else None,
                "qr_signing_key_length": len(QR_SIGNING_KEY),
                "verification_status": "VALID"
                if signature == expected_signature
                else "INVALID_SIGNATURE",
            }
        ), 200

    except Exception as e:
        logger.error(f"debug_qr_test error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@tickets_bp.route("/debug/regenerate-qr/<int:ticket_id>", methods=["POST"])
@jwt_required()

