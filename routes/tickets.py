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

def debug_regenerate_qr(ticket_id):
    """Debug endpoint to regenerate QR code for a ticket"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if user.role not in [UserRole.ADMIN, UserRole.ORGANIZER]:
            return jsonify({"error": "Permission denied"}), 403

        ticket = Ticket.query.get(ticket_id)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404

        # Generate new QR data and code
        qr_data = generate_secure_qr_data(ticket.id)
        qr_code = generate_qr_code(qr_data)

        # Update ticket
        ticket.qr_data = qr_data
        ticket.qr_code = qr_code
        db.session.commit()

        return jsonify(
            {
                "message": "QR code regenerated",
                "ticket": ticket.to_dict(),
                "qr_data": qr_data,
            }
        ), 200

    except Exception as e:
        logger.error(f"debug_regenerate_qr error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@tickets_bp.route("", methods=["POST"])
def purchase_ticket():
    """Purchase tickets for an event - now creates reservation (supports guest checkout)"""
    try:
        # Try to get JWT identity, but don't fail if not present (allows guest checkout)
        user_id = None
        is_authenticated = False
        try:
            verify_jwt_in_request()
            user_id = get_jwt_identity()
            is_authenticated = True
        except Exception as e:
            # No valid JWT - this is a guest purchase
            logger.warning(f"purchase_ticket: JWT verification failed: {e}")
            pass

        user = None

        logger.info(
            f"purchase_ticket: user_id={user_id}, is_authenticated={is_authenticated}"
        )

        data = request.get_json()
        logger.info(f"purchase_ticket: data={data}")

        # Check if this is a guest checkout (user explicitly requested guest checkout)
        # Note: is_guest_checkout will be checked after we parse request data below
        is_guest_checkout = data.get("is_guest_checkout", False)

        # CRITICAL FIX: If user_id is set (JWT verified), this is an authenticated purchase
        # even if frontend mistakenly sends is_guest_checkout=true
        # Only allow guest checkout if JWT verification failed (user_id is None)
        is_guest = is_guest_checkout and not is_authenticated

        logger.info(
            f"purchase_ticket: is_guest={is_guest}, is_guest_checkout={is_guest_checkout}, is_authenticated={is_authenticated}, user_id={user_id}"
        )

        # For authenticated users, validate the user exists
        if is_authenticated and user_id:
            user = User.query.get(user_id)

            if not user:
                logger.warning(f"purchase_ticket: User not found for user_id={user_id}")
                return jsonify({"error": "User not found"}), 404

            if not user.is_verified:
                logger.warning(f"purchase_ticket: User {user_id} not verified")
                return jsonify(
                    {"error": "Please verify your email to purchase tickets"}
                ), 403

        # For guests, validate required fields
        if is_guest:
            if not data.get("email"):
                return jsonify({"error": "Email is required for guest checkout"}), 400
            if not data.get("name"):
                return jsonify({"error": "Name is required for guest checkout"}), 400

        event_id = data.get("event_id")
        ticket_type_id = data.get("ticket_type_id")
        quantity = data.get("quantity", 1)
        payment_method = data.get("payment_method", "mpesa")

        if not event_id or not ticket_type_id:
            logger.warning(
                f"purchase_ticket: Missing event_id or ticket_type_id: event_id={event_id}, ticket_type_id={ticket_type_id}"
            )
            return jsonify({"error": "Event ID and ticket type ID are required"}), 400

        if quantity < 1:
            logger.warning(f"purchase_ticket: Invalid quantity: {quantity}")
            return jsonify({"error": "Quantity must be at least 1"}), 400

        event = db.session.get(Event, event_id)
        if not event:
            logger.warning(f"purchase_ticket: Event not found: event_id={event_id}")
            return jsonify({"error": "Event not found"}), 404

        logger.info(
            f"purchase_ticket: event={event.title}, is_published={event.is_published}, status={event.status}"
        )
        if not event.is_published or event.status != EventStatus.APPROVED:
            logger.warning(
                f"purchase_ticket: Event not available for tickets: is_published={event.is_published}, status={event.status}"
            )
            return jsonify({"error": "Tickets not available for this event"}), 400

        ticket_type = db.session.get(TicketTypeModel, ticket_type_id)
        if not ticket_type or ticket_type.event_id != event_id:
            logger.warning(
                f"purchase_ticket: Invalid ticket type: ticket_type_id={ticket_type_id}"
            )
            return jsonify({"error": "Invalid ticket type"}), 400

        if ticket_type.sold_quantity + quantity > ticket_type.quantity:
            logger.warning(
                f"purchase_ticket: Not enough tickets available: sold={ticket_type.sold_quantity}, quantity={quantity}, total={ticket_type.quantity}"
            )
            return jsonify(
                {
                    "error": f"Only {ticket_type.quantity - ticket_type.sold_quantity} tickets available"
                }
            ), 400

        total_price = ticket_type.price * quantity

        if payment_method == "mpesa":
            phone = data.get("phone")

            if is_guest:
                # For guest checkout, create a special guest ticket
                return create_guest_reservation(
                    event, ticket_type, quantity, data, phone
                )

            if not phone:
                # Create pending reservation without payment (for authenticated users)
                return create_pending_reservation(
                    user, event, ticket_type, quantity, data
                )

            return initiate_mpesa_payment(
                user_id, event_id, ticket_type_id, quantity, total_price, phone
            )
        else:
            return jsonify(
                {"error": "Invalid payment method. Only M-Pesa is supported."}
            ), 400

    except Exception as e:
        db.session.rollback()
        logger.error(f"purchase_ticket error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@tickets_bp.route("/initiate-payment", methods=["POST"])
@jwt_required()

