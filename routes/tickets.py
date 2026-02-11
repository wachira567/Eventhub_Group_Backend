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
def initiate_payment_for_reservation():
    """Initiate payment for an existing reservation"""
    logger.info("=== initiate_payment_for_reservation: Function entered ===")
    try:
        user_id = get_jwt_identity()
        logger.info(f"initiate_payment: user_id={user_id}")

        data = request.get_json()
        ticket_id = data.get("ticket_id")
        phone = data.get("phone") or data.get("phone_number")

        logger.info(f"initiate_payment: ticket_id={ticket_id}, phone={phone}")

        if not ticket_id:
            return jsonify({"error": "Ticket ID is required"}), 400

        if not phone:
            return jsonify({"error": "Phone number is required"}), 400

        ticket = db.session.get(Ticket, ticket_id)
        if not ticket:
            logger.warning(f"initiate_payment: Ticket not found: {ticket_id}")
            return jsonify({"error": "Ticket not found"}), 404

        logger.info(
            f"initiate_payment: ticket.user_id={ticket.user_id}, request user_id={user_id}"
        )

        # Fix type mismatch: user_id from JWT is string, ticket.user_id is int
        if str(ticket.user_id) != str(user_id):
            logger.warning(
                f"initiate_payment: Permission denied - ticket.user_id={ticket.user_id}, user_id={user_id}"
            )
            return jsonify({"error": "Permission denied"}), 403

        if ticket.payment_status != "PENDING":
            logger.warning(
                f"initiate_payment: Ticket {ticket_id} is not pending, status={ticket.payment_status}"
            )
            return jsonify({"error": "Ticket is not pending payment"}), 400

        transaction = (
            MpesaTransaction.query.filter_by(
                user_id=user_id,
                event_id=ticket.event_id,
                ticket_type_id=ticket.ticket_type_id,
                status="PENDING",
            )
            .order_by(MpesaTransaction.id.desc())
            .first()
        )

        logger.info(f"initiate_payment: Found transaction: {transaction}")

        if not transaction:
            logger.warning(
                f"initiate_payment: No pending transaction found for ticket {ticket_id}"
            )
            return jsonify({"error": "No pending transaction found"}), 400

        # Update transaction with phone and initiate payment
        transaction.phone_number = phone
        db.session.commit()

        ticket_type = db.session.get(TicketTypeModel, ticket.ticket_type_id)
        logger.info(
            f"initiate_payment: ticket_type={ticket_type}, price={ticket_type.price if ticket_type else 'N/A'}"
        )

        if not ticket_type:
            logger.error(
                f"initiate_payment: Ticket type not found: {ticket.ticket_type_id}"
            )
            return jsonify({"error": "Ticket type not found"}), 400

        total_price = ticket_type.price * ticket.quantity
        logger.info(
            f"initiate_payment: Calling mpesa_service with total_price={total_price}"
        )

        return initiate_mpesa_payment(
            user_id,
            ticket.event_id,
            ticket.ticket_type_id,
            ticket.quantity,
            total_price,
            phone,
            transaction.id,
        )

    except Exception as e:
        db.session.rollback()
        logger.error(f"initiate_payment_for_reservation error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


def create_pending_reservation(user, event, ticket_type, quantity, data):
    """Create a pending reservation without payment"""
    try:
        total_price = ticket_type.price * quantity

        # Create a pending M-Pesa transaction (no payment yet)
        from datetime import datetime
        import time

        reference = f"TICKET-{event.id}-{user.id}-{time.time()}"

        transaction = MpesaTransaction(
            user_id=user.id,
            event_id=event.id,
            ticket_type_id=ticket_type.id,
            quantity=quantity,
            amount=total_price,
            phone_number="",  # Will be filled during payment
            reference=reference,
            status="PENDING",
        )
        db.session.add(transaction)
        db.session.commit()

        # Create a temporary ticket with pending status
        ticket = Ticket(
            user_id=user.id,
            event_id=event.id,
            ticket_type_id=ticket_type.id,
            ticket_number=f"TEMP-{transaction.id}",
            quantity=quantity,
            total_price=total_price,
            payment_status="PENDING",
        )
        db.session.add(ticket)
        db.session.commit()

        return jsonify(
            {
                "message": "Reservation created. Complete payment to confirm.",
                "ticket": ticket.to_dict(),
                "transaction_id": transaction.id,
            }
        ), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"create_pending_reservation error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


def create_guest_reservation(event, ticket_type, quantity, data, phone):
    """Create a reservation for guest checkout"""
    try:
        import secrets

        total_price = ticket_type.price * quantity

        # Get guest details from data
        guest_email = data.get("email")
        guest_name = data.get("name")

        logger.info(
            f"create_guest_reservation: Storing guest_email={guest_email}, guest_name={guest_name}"
        )

        # Generate a unique reference
        reference = f"GUEST-{event.id}-{secrets.randbelow(1000000)}"

        # Create guest ticket FIRST (so we can link it to the transaction)
        guest_token = secrets.token_urlsafe(32)

        # Create guest ticket
        ticket = Ticket(
            user_id=None,  # No user account
            event_id=event.id,
            ticket_type_id=ticket_type.id,
            ticket_number=f"GUEST-{secrets.randbelow(1000000)}",
            quantity=quantity,
            total_price=total_price,
            payment_status="PENDING",
            is_guest=True,
            guest_email=data.get("email"),
            guest_name=data.get("name"),
        )
        db.session.add(ticket)
        db.session.flush()  # Get ticket ID

        logger.info(f"create_guest_reservation: Created ticket ID {ticket.id}")

        # Create a pending M-Pesa transaction with ticket_id link
        transaction = MpesaTransaction(
            user_id=None,  # NULL for guests - no foreign key violation
            event_id=event.id,
            ticket_type_id=ticket_type.id,
            ticket_id=ticket.id,  # Link to the guest ticket
            quantity=quantity,
            amount=total_price,
            phone_number=phone or "",
            reference=reference,
            status="PENDING",
        )
        db.session.add(transaction)
        db.session.commit()

        # Update ticket with transaction reference
        ticket.ticket_number = f"GUEST-{transaction.id}"
        db.session.commit()

        return jsonify(
            {
                "message": "Guest reservation created. Complete payment to confirm.",
                "ticket": ticket.to_dict(),
                "transaction_id": transaction.id,
                "guest_token": guest_token,
                "guest_email": data.get("email"),
                "guest_name": data.get("name"),
            }
        ), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"create_guest_reservation error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@tickets_bp.route("/guest-initiate-payment", methods=["POST"])
def initiate_guest_payment():
    """Initiate payment for a guest reservation"""
    logger.info("=== initiate_guest_payment: Function entered ===")
    try:
        data = request.get_json()
        ticket_id = data.get("ticket_id")
        guest_token = data.get("guest_token")
        phone = data.get("phone") or data.get("phone_number")

        logger.info(
            f"initiate_guest_payment: ticket_id={ticket_id}, guest_token present={bool(guest_token)}, phone={phone}"
        )


        if not ticket_id:
            logger.error("initiate_guest_payment: Missing ticket_id")
            return jsonify({"error": "Ticket ID is required"}), 400

        if not guest_token:
            logger.error("initiate_guest_payment: Missing guest_token")
            return jsonify({"error": "Guest token is required"}), 400

        if not phone:
            logger.error(f"initiate_guest_payment: Missing phone number. Received data: {data}")
            return jsonify({"error": "Phone number is required"}), 400

        ticket = db.session.get(Ticket, ticket_id)
        if not ticket:
            logger.warning(f"initiate_guest_payment: Ticket not found: {ticket_id}")
            return jsonify({"error": "Ticket not found"}), 404

        # Verify guest token
        if not ticket.is_guest:
            logger.warning(
                f"initiate_guest_payment: Ticket {ticket_id} is not a guest ticket"
            )
            return jsonify({"error": "Invalid ticket"}), 400

        if ticket.payment_status != "PENDING":
            logger.warning(
                f"initiate_guest_payment: Ticket {ticket_id} is not pending, status={ticket.payment_status}"
            )
            return jsonify({"error": "Ticket is not pending payment"}), 400


        # Find the pending transaction for this guest ticket
        # CRITICAL FIX: Filter by ticket_id to ensure we get the specific transaction for this user/ticket
        # failing to do so could cause race conditions where we pick up another guest's transaction
        transaction = (
            MpesaTransaction.query.filter_by(
                ticket_id=ticket.id,
                status="PENDING",
            )
            .order_by(MpesaTransaction.id.desc())
            .first()
        )

        if not transaction:
            logger.warning(
                f"initiate_guest_payment: No pending transaction found for ticket {ticket_id}"
            )
            return jsonify({"error": "No pending transaction found"}), 400

        # Update transaction with phone (keep user_id as NULL for guests)
        transaction.phone_number = phone
        # Don't set user_id - keep it NULL for guests
        db.session.commit()

        ticket_type = db.session.get(TicketTypeModel, ticket.ticket_type_id)
        logger.info(f"initiate_guest_payment: ticket_type={ticket_type}")

        if not ticket_type:
            logger.error(
                f"initiate_guest_payment: Ticket type not found: {ticket.ticket_type_id}"
            )
            return jsonify({"error": "Ticket type not found"}), 400

        total_price = float(ticket_type.price) * ticket.quantity
        logger.info(
            f"initiate_guest_payment: Calling mpesa_service with total_price={total_price}"
        )

        # Use None for guest transactions
        return initiate_mpesa_payment(
            None,
            ticket.event_id,
            ticket.ticket_type_id,
            ticket.quantity,
            total_price,
            phone,
            transaction.id,
        )

    except Exception as e:
        db.session.rollback()
        logger.error(f"initiate_guest_payment error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


def create_guest_tickets(transaction):
    """Create tickets for guest after successful payment - now with secure QR codes"""
    try:
        # GUARD: Refuse to process authenticated user transactions as guest
        if transaction.user_id is not None:
            logger.error(
                f"create_guest_tickets: REJECTED - Transaction has user_id={transaction.user_id} but was routed to guest ticket creation. "
                f"This should not happen. Please check confirm_payment() logic."
            )
            return jsonify(
                {
                    "error": "Internal error: Authenticated user transaction was incorrectly routed to guest ticket creation. "
                    "Please contact support or try again."
                }
            ), 500

        # Check if this specific transaction has already been processed
        # We check if the pending ticket linked to this transaction is already COMPLETED
        if transaction.ticket_id:
            pending_ticket = db.session.get(Ticket, transaction.ticket_id)
            if pending_ticket and pending_ticket.payment_status == "COMPLETED":
                # This transaction was already processed - return existing completed tickets
                existing_tickets = Ticket.query.filter_by(
                    event_id=transaction.event_id,
                    ticket_type_id=transaction.ticket_type_id,
                    payment_status="COMPLETED",
                ).all()
                logger.warning(
                    f"create_guest_tickets: Transaction {transaction.id} already processed, found {len(existing_tickets)} completed tickets"
                )
                return jsonify(
                    {
                        "message": "Payment already confirmed",
                        "transaction_id": transaction.id,
                        "status": "already_processed",
                        "tickets": [t.to_dict() for t in existing_tickets],
                    }
                ), 200

        event_id = transaction.event_id
        ticket_type_id = transaction.ticket_type_id
        quantity = transaction.quantity

        event = db.session.get(Event, event_id)
        if not event:
            return jsonify({"error": "Event not found"}), 404

        ticket_type = db.session.get(TicketTypeModel, ticket_type_id)
        if not ticket_type:
            return jsonify({"error": "Ticket type not found"}), 404

        # Find the guest ticket using transaction.ticket_id (the correct way)
        guest_ticket = None
        if transaction.ticket_id:
            guest_ticket = db.session.get(Ticket, transaction.ticket_id)
            logger.info(
                f"create_guest_tickets: Found ticket by transaction.ticket_id={transaction.ticket_id}"
            )

        # Fallback: if no ticket_id link, search by event/ticket_type (old method)
        if not guest_ticket:
            logger.warning(
                f"create_guest_tickets: No ticket_id link, using fallback search"
            )
            guest_ticket = (
                Ticket.query.filter_by(
                    event_id=event_id,
                    ticket_type_id=ticket_type_id,
                    is_guest=True,
                    payment_status="PENDING",
                )
                .order_by(Ticket.id.desc())
                .first()
            )

        if not guest_ticket:
            return jsonify({"error": "Guest ticket not found"}), 404

        logger.info(
            f"create_guest_tickets: Found guest ticket ID={guest_ticket.id}, guest_email={guest_ticket.guest_email}, guest_name={guest_ticket.guest_name}"
        )

        # Validate that guest email is properly set
        if not guest_ticket.guest_email or "@" not in guest_ticket.guest_email:
            logger.error(
                f"create_guest_tickets: Invalid or missing guest_email: {guest_ticket.guest_email}"
            )
            return jsonify(
                {"error": "Guest email is missing or invalid. Please contact support."}
            ), 400

        # Get total_price from ticket type
        total_price = float(ticket_type.price) * quantity

        # Create final tickets with secure QR codes
        tickets = []
        for i in range(quantity):
            # First create the ticket to get its ID
            ticket = Ticket(
                user_id=None,  # Guest - no user account
                event_id=event_id,
                ticket_type_id=ticket_type_id,
                ticket_number=f"TEMP-{i + 1}",
                qr_code="",
                qr_data="",
                total_price=total_price,
                payment_status="COMPLETED",
                is_guest=True,
                guest_email=guest_ticket.guest_email,
                guest_name=guest_ticket.guest_name,
            )
            db.session.add(ticket)
            db.session.flush()  # Get the ticket ID without committing

            # Now generate secure QR data with the actual ticket ID
            qr_data = generate_secure_qr_data(ticket.id)
            qr_code = generate_qr_code(qr_data)

            logger.info(
                f"create_guest_tickets: Generated QR for ticket {ticket.id}: {qr_data}"
            )

            # Update ticket with QR code
            ticket.ticket_number = qr_data[:16].upper()
            ticket.qr_code = qr_code
            ticket.qr_data = qr_data

            tickets.append(ticket)

        # Update ticket type sold quantity
        ticket_type.sold_quantity += quantity

        # Update transaction status
        transaction.status = "COMPLETED"

        # Mark guest ticket as completed/failed
        guest_ticket.payment_status = "COMPLETED"

        db.session.commit()

        # Generate PDF and send email to guest
        try:
            pdf_buffer = generate_ticket_pdf(tickets[0], ticket_type, event, None)

            # Send confirmation email with PDF
            email_sent = send_ticket_with_pdf(
                user_email=guest_ticket.guest_email,
                user_name=guest_ticket.guest_name,
                event_title=event.title,
                ticket_number=tickets[0].ticket_number,
                quantity=quantity,
                total_price=float(transaction.amount),
                pdf_buffer=pdf_buffer,
            )

            if email_sent:
                logger.info(
                    f"Guest ticket confirmation email sent to {guest_ticket.guest_email}"
                )
            else:
                logger.warning(
                    f"Failed to send guest ticket email to {guest_ticket.guest_email}"
                )

        except Exception as email_error:
            logger.error(f"Error sending guest ticket email: {str(email_error)}")
            # Don't fail the transaction if email fails

        return jsonify(
            {
                "message": "Payment successful! Your tickets are ready. Check your email for the ticket PDF.",
                "tickets": [ticket.to_dict() for ticket in tickets],
                "email_sent": email_sent if "email_sent" in dir() else False,
            }
        ), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"create_guest_tickets error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


def initiate_mpesa_payment(
    user_id,
    event_id,
    ticket_type_id,
    quantity,
    total_price,
    phone,
    existing_transaction_id=None,
):
    """Initiate M-Pesa STK Push payment"""
    try:
        from services.mpesa_service import mpesa_service

        if existing_transaction_id:
            transaction = MpesaTransaction.query.get(existing_transaction_id)
            if not transaction:
                return jsonify({"error": "Transaction not found"}), 400
        else:
            reference = f"TICKET-{event_id}-{user_id}-{datetime.utcnow().timestamp()}"

            transaction = MpesaTransaction(
                user_id=user_id,
                event_id=event_id,
                ticket_type_id=ticket_type_id,
                quantity=quantity,
                amount=total_price,
                phone_number=phone,
                reference=reference,
                status="PENDING",
            )
            db.session.add(transaction)
            db.session.commit()

        response = mpesa_service.initiate_stk_push(
            phone_number=phone,
            amount=int(total_price),
            order_id=transaction.reference,
            description=f"EventHub Tickets - Event {event_id}",
        )

        if response.get("success"):
            transaction.checkout_request_id = response.get("checkout_request_id")
            db.session.commit()

            return jsonify(
                {
                    "message": "Payment initiated. Please check your phone.",
                    "transaction_id": transaction.id,
                    "checkout_request_id": response.get("checkout_request_id"),
                    "payment_url": None,
                }
            ), 200
        else:
            transaction.status = "FAILED"
            db.session.commit()

            return jsonify(
                {
                    "error": "Payment initiation failed",
                    "details": response.get("error", "Unknown error"),
                }
            ), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@tickets_bp.route("/confirm-payment", methods=["POST"])
def confirm_payment():
    """Confirm payment and create tickets"""
    try:
        data = request.get_json()
        transaction_id = data.get("transaction_id")
        checkout_request_id = data.get("checkout_request_id")
        payment_method = data.get("payment_method", "mpesa")

        logger.info(
            f"confirm_payment: transaction_id={transaction_id}, checkout_request_id={checkout_request_id}, payment_method={payment_method}"
        )

        if payment_method == "mpesa":
            if not checkout_request_id:
                logger.warning("confirm_payment: No checkout_request_id provided")
                return jsonify({"error": "checkout_request_id is required"}), 400

            # First find transaction by checkout_request_id
            transaction = MpesaTransaction.query.filter_by(
                checkout_request_id=checkout_request_id
            ).first()

            if not transaction:
                logger.warning(
                    f"confirm_payment: Transaction not found for checkout_request_id={checkout_request_id}"
                )
                return jsonify({"error": "Transaction not found"}), 404

            logger.info(
                f"confirm_payment: Found transaction: id={transaction.id}, status={transaction.status}, checkout_request_id={transaction.checkout_request_id}"
            )

            # Check if this specific transaction has already been processed
            # We check if the pending ticket linked to this transaction is already COMPLETED
            pending_ticket = None
            if transaction.ticket_id:
                pending_ticket = db.session.get(Ticket, transaction.ticket_id)

            if pending_ticket and pending_ticket.payment_status == "COMPLETED":
                # This transaction was already processed - return the existing completed tickets
                existing_tickets = Ticket.query.filter_by(
                    event_id=transaction.event_id,
                    ticket_type_id=transaction.ticket_type_id,
                    payment_status="COMPLETED",
                ).all()
                logger.warning(
                    f"confirm_payment: Transaction {transaction.id} already processed, found {len(existing_tickets)} completed tickets"
                )
                return jsonify(
                    {
                        "message": "Payment already confirmed",
                        "transaction_id": transaction.id,
                        "status": "already_processed",
                        "tickets": [t.to_dict() for t in existing_tickets],
                    }
                ), 200

            # Check if this is a guest transaction (user_id = 0 or linked to guest ticket)
            # Use transaction.ticket_id if available, otherwise fall back to searching
            guest_ticket = None
            if transaction.ticket_id:
                guest_ticket = db.session.get(Ticket, transaction.ticket_id)
                logger.info(
                    f"confirm_payment: Found guest ticket by transaction.ticket_id={transaction.ticket_id}, "
                    f"guest_ticket.is_guest={guest_ticket.is_guest if guest_ticket else 'N/A'}, "
                    f"guest_ticket.user_id={guest_ticket.user_id if guest_ticket else 'N/A'}"
                )

            if not guest_ticket:
                # Fallback: search by event/ticket_type AND phone number (more specific)
                # Only use this fallback for truly guest transactions (user_id is None)
                if transaction.user_id is None:
                    phone_filter = (
                        transaction.phone_number if transaction.phone_number else None
                    )
                    if phone_filter:
                        guest_ticket = (
                            Ticket.query.filter_by(
                                event_id=transaction.event_id,
                                ticket_type_id=transaction.ticket_type_id,
                                is_guest=True,
                                payment_status="PENDING",
                            )
                            .filter(
                                or_(
                                    Ticket.guest_email.ilike(f"%{phone_filter}%"),
                                    Ticket.guest_name.ilike(f"%{phone_filter}%"),
                                )
                            )
                            .first()
                        )
                    else:
                        # If no phone number, search by the most recent pending guest ticket
                        guest_ticket = (
                            Ticket.query.filter_by(
                                event_id=transaction.event_id,
                                ticket_type_id=transaction.ticket_type_id,
                                is_guest=True,
                                payment_status="PENDING",
                            )
                            .order_by(Ticket.id.desc())
                            .first()
                        )
                    logger.info(
                        f"confirm_payment: Fallback search found guest_ticket={guest_ticket.id if guest_ticket else None}, "
                        f"transaction.user_id={transaction.user_id}, has_phone={bool(phone_filter)}"
                    )
                else:
                    logger.info(
                        f"confirm_payment: Transaction has user_id={transaction.user_id}, skipping guest ticket fallback"
                    )

            if guest_ticket:
                # This is a guest transaction - verify it has guest email
                logger.info(
                    f"confirm_payment: Guest transaction detected, guest_ticket.id={guest_ticket.id}, "
                    f"guest_email={guest_ticket.guest_email}, transaction.user_id={transaction.user_id}"
                )
                # Double-check: if the transaction has a user_id (authenticated user)
                # but we found a guest ticket, this is an error - don't process as guest
                if transaction.user_id is not None:
                    logger.error(
                        f"confirm_payment: ERROR - Transaction has user_id={transaction.user_id} but found guest ticket. "
                        f"Not processing as guest. Guest ticket email: {guest_ticket.guest_email}"
                    )
                    return jsonify(
                        {
                            "error": "Ticket mismatch: You are logged in but ticket is for a guest. Please try again."
                        }
                    ), 400
                return create_guest_tickets(transaction)

            result = verify_mpesa_payment(transaction)

            if result["success"]:
                return create_tickets(transaction)
            else:
                return jsonify({"error": result["error"]}), 400
        else:
            transaction = MpesaTransaction.query.get(transaction_id)
            if not transaction:
                return jsonify({"error": "Invalid transaction"}), 400

            return create_tickets(transaction)

    except Exception as e:
        logger.error(f"confirm_payment error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


def verify_mpesa_payment(transaction):
    """Verify M-Pesa payment status"""
    try:
        # Refresh from database to get latest status
        db.session.refresh(transaction)

        logger.info(
            f"verify_mpesa_payment: Transaction {transaction.id}, current status='{transaction.status}', checkout_request_id='{transaction.checkout_request_id}'"
        )

        # If transaction is already marked as completed (e.g., from simulate-complete), skip API query
        # Check both lowercase and uppercase for compatibility
        if transaction.status and transaction.status.lower() == "completed":
            logger.info(
                f"verify_mpesa_payment: Transaction {transaction.id} already marked as completed, skipping API query"
            )
            return {"success": True}

        from services.mpesa_service import mpesa_service

        if not transaction.checkout_request_id:
            logger.warning(
                f"verify_mpesa_payment: No checkout_request_id for transaction {transaction.id}"
            )
            return {"success": False, "error": "No checkout request ID"}

        response = mpesa_service.query_stk_status(
            checkout_request_id=transaction.checkout_request_id
        )

        logger.info(f"verify_mpesa_payment: API response={response}")

        if response.get("ResultCode") == 0:
            transaction.status = "COMPLETED"
            db.session.commit()
            return {"success": True}
        else:
            transaction.status = "FAILED"
            db.session.commit()
            return {
                "success": False,
                "error": response.get("ResultDesc", "Payment failed"),
            }

    except Exception as e:
        logger.error(f"verify_mpesa_payment error: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}


def create_tickets(transaction):
    """Create tickets after successful payment - now with secure QR codes"""
    try:
        user_id = transaction.user_id
        event_id = transaction.event_id
        ticket_type_id = transaction.ticket_type_id
        quantity = transaction.quantity

        # Check if this specific transaction has already been processed
        # Look for existing COMPLETED tickets with the same transaction reference
        existing_tickets = Ticket.query.filter_by(
            user_id=user_id,
            event_id=event_id,
            ticket_type_id=ticket_type_id,
            payment_status="COMPLETED",
        ).all()

        # If tickets already exist for this transaction, return them without creating duplicates
        # Check if the transaction was already marked as completed
        if transaction.status == "COMPLETED" and existing_tickets:
            logger.warning(
                f"create_tickets: Transaction {transaction.id} already processed, found {len(existing_tickets)} completed tickets"
            )
            return jsonify(
                {
                    "message": "Payment already confirmed",
                    "transaction_id": transaction.id,
                    "status": "already_processed",
                    "tickets": [t.to_dict() for t in existing_tickets],
                }
            ), 200

        user = db.session.get(User, user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        event = db.session.get(Event, event_id)
        if not event:
            return jsonify({"error": "Event not found"}), 404

        ticket_type = db.session.get(TicketTypeModel, ticket_type_id)
        if not ticket_type:
            return jsonify({"error": "Ticket type not found"}), 404

        # Get total_price from ticket type (more reliable than transaction.amount)
        total_price = float(ticket_type.price) * quantity

        # Create tickets with secure QR codes
        tickets = []
        for i in range(quantity):
            # First create the ticket to get its ID
            ticket = Ticket(
                user_id=user_id,
                event_id=event_id,
                ticket_type_id=ticket_type_id,
                ticket_number=f"TEMP-{i + 1}",
                qr_code="",
                qr_data="",
                total_price=total_price,
                payment_status="COMPLETED",
            )
            db.session.add(ticket)
            db.session.flush()  # Get the ticket ID without committing

            # Now generate secure QR data with the actual ticket ID
            qr_data = generate_secure_qr_data(ticket.id)
            qr_code = generate_qr_code(qr_data)

            logger.info(
                f"create_tickets: Generated QR for ticket {ticket.id}: {qr_data}"
            )

            # Update ticket with QR code
            ticket.ticket_number = qr_data[:16].upper()
            ticket.qr_code = qr_code
            ticket.qr_data = qr_data

            tickets.append(ticket)

        ticket_type.sold_quantity += quantity

        transaction.status = "COMPLETED"
        db.session.commit()

        # Generate PDF and send email
        try:
            # Generate PDF for each ticket
            pdf_buffer = generate_ticket_pdf(tickets[0], ticket_type, event, user)

            # Send confirmation email with PDF
            email_sent = send_ticket_with_pdf(
                user_email=user.email,
                user_name=user.name,
                event_title=event.title,
                ticket_number=tickets[0].ticket_number,
                quantity=quantity,
                total_price=float(transaction.amount),
                pdf_buffer=pdf_buffer,
            )

            if email_sent:
                logger.info(f"Ticket confirmation email sent to {user.email}")
            else:
                logger.warning(f"Failed to send ticket email to {user.email}")

        except Exception as email_error:
            logger.error(f"Error sending ticket email: {str(email_error)}")
            # Don't fail the transaction if email fails

        return jsonify(
            {
                "message": "Payment successful! Your tickets are ready. Check your email for the ticket PDF.",
                "tickets": [ticket.to_dict() for ticket in tickets],
                "email_sent": email_sent if "email_sent" in dir() else False,
            }
        ), 201

    except Exception as e:
        db.session.rollback()
        logger.error(f"create_tickets error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@tickets_bp.route("/my-tickets", methods=["GET"])
@jwt_required()
def get_my_tickets():
    """Get current user's tickets"""
    try:
        user_id = get_jwt_identity()
        status = request.args.get("status", "").strip()
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 12, type=int)

        query = Ticket.query.filter_by(user_id=user_id)

        if status:
            query = query.filter(Ticket.payment_status == status)

        pagination = query.order_by(Ticket.purchased_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        # Include event data with each ticket
        tickets_with_events = []
        for ticket in pagination.items:
            ticket_dict = ticket.to_dict()
            # Fetch event data
            event = db.session.get(Event, ticket.event_id)
            if event:
                ticket_dict["event"] = {
                    "id": event.id,
                    "title": event.title,
                    "start_date": event.start_date.isoformat()
                    if event.start_date
                    else None,
                    "end_date": event.end_date.isoformat() if event.end_date else None,
                    "venue": event.venue,
                    "location": event.venue,  # For compatibility with frontend
                    "image_url": event.image_url,
                }
            else:
                ticket_dict["event"] = None

            # Fetch ticket type name
            ticket_type = db.session.get(TicketTypeModel, ticket.ticket_type_id)
            if ticket_type:
                ticket_dict["ticket_type_name"] = ticket_type.name
            else:
                ticket_dict["ticket_type_name"] = "Ticket"

            tickets_with_events.append(ticket_dict)

        return jsonify(
            {
                "tickets": tickets_with_events,
                "total": pagination.total,
                "pages": pagination.pages,
                "current_page": page,
            }
        ), 200

    except Exception as e:
        logger.error(f"get_my_tickets error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@tickets_bp.route("", methods=["GET"])
@jwt_required()
def get_all_tickets():
    """Get all tickets for admin"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if not user or user.role not in [UserRole.ADMIN, UserRole.ORGANIZER]:
            return jsonify({"error": "Permission denied"}), 403

        status = request.args.get("status", "").strip()
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 12, type=int)

        query = Ticket.query

        if status:
            query = query.filter(Ticket.payment_status == status)

        pagination = query.order_by(Ticket.purchased_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify(
            {
                "tickets": [ticket.to_dict() for ticket in pagination.items],
                "total": pagination.total,
                "pages": pagination.pages,
                "current_page": page,
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tickets_bp.route("/<int:ticket_id>", methods=["GET"])
@jwt_required()
def get_ticket(ticket_id):
    """Get single ticket details"""
    try:
        user_id = get_jwt_identity()
        ticket = Ticket.query.get_or_404(ticket_id)

        if ticket.user_id != user_id:
            return jsonify({"error": "Permission denied"}), 403

        return jsonify({"ticket": ticket.to_dict()}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tickets_bp.route("/<int:ticket_id>/download", methods=["GET", "OPTIONS"])
def download_ticket_pdf(ticket_id):
    """Download ticket as PDF - supports both authenticated users and guests"""
    # Handle CORS preflight requests
    if request.method == "OPTIONS":
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "http://localhost:5173")
        response.headers.add("Access-Control-Allow-Credentials", "true")
        response.headers.add(
            "Access-Control-Allow-Headers", "Content-Type, Authorization"
        )
        response.headers.add("Access-Control-Allow-Methods", "GET, OPTIONS")
        return response, 200

    try:
        # Check for guest token in query parameters
        guest_token = request.args.get("guest_token")
        guest_email = request.args.get("email")

        ticket = db.session.get(Ticket, ticket_id)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404

        # For guest tickets, verify guest token or email
        if ticket.is_guest:
            if guest_token:
                # Guest token validation - the token was stored in session during purchase
                # For now, accept any guest ticket if guest_token is provided
                # In production, you should validate the token properly
                pass
            elif guest_email:
                # Validate by email
                if ticket.guest_email != guest_email:
                    return jsonify({"error": "Permission denied"}), 403
            else:
                return jsonify(
                    {"error": "Guest token or email required for guest ticket"}
                ), 400
        else:
            # For authenticated users, require JWT
            from flask_jwt_extended import jwt_required, get_jwt_identity

            user_id = get_jwt_identity()

            if ticket.user_id != user_id:
                return jsonify({"error": "Permission denied"}), 403

        ticket_type = db.session.get(TicketTypeModel, ticket.ticket_type_id)
        event = db.session.get(Event, ticket.event_id)

        # For guest tickets, user will be None
        user = User.query.get(ticket.user_id) if ticket.user_id else None

        pdf_data = generate_ticket_pdf(ticket, ticket_type, event, user)

        response = make_response(
            send_file(
                io.BytesIO(pdf_data),
                mimetype="application/pdf",
                as_attachment=True,
                download_name=f"ticket-{ticket.ticket_number}.pdf",
            )
        )

        # Add CORS headers for file download
        response.headers.add("Access-Control-Allow-Origin", "http://localhost:5173")
        response.headers.add("Access-Control-Allow-Credentials", "true")

        return response

    except Exception as e:
        logger.error(f"download_ticket_pdf error: {str(e)}", exc_info=True)
        response = jsonify({"error": str(e)})
        response.headers.add("Access-Control-Allow-Origin", "http://localhost:5173")
        response.headers.add("Access-Control-Allow-Credentials", "true")
        return response, 500


@tickets_bp.route("/<int:ticket_id>/qr", methods=["GET"])
@jwt_required()
def get_ticket_qr(ticket_id):
    """Get ticket QR code image"""
    try:
        ticket = Ticket.query.get_or_404(ticket_id)

        return jsonify(
            {"qr_code": ticket.qr_code, "ticket_number": ticket.ticket_number}
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tickets_bp.route("/verify", methods=["POST"])
@jwt_required()
def verify_ticket():
    """Verify a ticket (for organizers) - now with secure QR verification"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if user.role not in [UserRole.ADMIN, UserRole.ORGANIZER]:
            return jsonify({"error": "Permission denied"}), 403

        data = request.get_json()
        qr_data = data.get("qr_data", "").strip()
        event_id = data.get("event_id")

        if not qr_data:
            return jsonify({"error": "QR data is required"}), 400

        # Verify the QR code signature
        logger.info(f"verify_ticket: QR data received: {qr_data}")
        logger.info(f"verify_ticket: QR_SIGNING_KEY length: {len(QR_SIGNING_KEY)}")
        verification = verify_qr_token(qr_data)
        logger.info(f"verify_ticket: Verification result: {verification}")
        if not verification["valid"]:
            logger.warning(
                f"verify_ticket: QR verification failed: {verification['error']}"
            )
            return jsonify({"valid": False, "error": verification["error"]}), 400

        ticket_id = verification["ticket_id"]
        ticket = Ticket.query.get(ticket_id)

        if not ticket:
            return jsonify({"valid": False, "error": "Ticket not found"}), 404

        if event_id and ticket.event_id != event_id:
            return jsonify(
                {"valid": False, "error": "Ticket is for a different event"}
            ), 400

        event = Event.query.get(ticket.event_id)
        if user.role == UserRole.ORGANIZER and event.organizer_id != user.id:
            return jsonify(
                {"error": "You can only verify tickets for your own events"}
            ), 403

        if ticket.is_used:
            return jsonify(
                {
                    "valid": False,
                    "error": "Ticket has already been used",
                    "used_at": ticket.used_at,
                    "ticket": ticket.to_dict(),
                }
            ), 400

        if ticket.payment_status == "FAILED":
            return jsonify(
                {
                    "valid": False,
                    "error": "Ticket has been cancelled",
                    "ticket": ticket.to_dict(),
                }
            ), 400

        if event.end_date < datetime.utcnow():
            return jsonify(
                {
                    "valid": False,
                    "error": "Event has already ended",
                    "ticket": ticket.to_dict(),
                }
            ), 400

        ticket.is_used = True
        ticket.used_at = datetime.utcnow()
        ticket.verified_by = user_id
        db.session.commit()

        return jsonify(
            {
                "valid": True,
                "message": "Ticket verified successfully",
                "ticket": ticket.to_dict(),
            }
        ), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@tickets_bp.route("/<int:ticket_id>", methods=["DELETE"])
@jwt_required()
def cancel_ticket(ticket_id):
    """Cancel a ticket (refund process)"""
    try:
        user_id = get_jwt_identity()
        ticket = Ticket.query.get_or_404(ticket_id)

        if ticket.user_id != user_id:
            return jsonify({"error": "Permission denied"}), 403

        if ticket.is_used:
            return jsonify({"error": "Cannot cancel a used ticket"}), 400

        event = Event.query.get(ticket.event_id)
        if event.start_date < datetime.utcnow():
            return jsonify({"error": "Cannot cancel ticket for past event"}), 400

        ticket.payment_status = "FAILED"

        ticket_type = TicketTypeModel.query.get(ticket.ticket_type_id)
        ticket_type.sold_quantity -= 1

        db.session.commit()

        return jsonify(
            {"message": "Ticket cancelled successfully", "ticket": ticket.to_dict()}
        ), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@tickets_bp.route("/event/<int:event_id>", methods=["GET"])
@jwt_required()
def get_event_tickets(event_id):
    """Get all tickets for an event (organizer only)"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        event = Event.query.get_or_404(event_id)

        if user.role not in [UserRole.ADMIN, UserRole.ORGANIZER]:
            return jsonify({"error": "Permission denied"}), 403

        if user.role == UserRole.ORGANIZER and event.organizer_id != user.id:
            return jsonify(
                {"error": "You can only view tickets for your own events"}
            ), 403

        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 50, type=int)
        status = request.args.get("status", "").strip()

        query = Ticket.query.filter_by(event_id=event_id)

        if status:
            query = query.filter(Ticket.payment_status == status)

        pagination = query.order_by(Ticket.purchased_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify(
            {
                "tickets": [ticket.to_dict() for ticket in pagination.items],
                "total": pagination.total,
                "pages": pagination.pages,
                "current_page": page,
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tickets_bp.route("/event/<int:event_id>/scan", methods=["POST"])
@jwt_required()
def scan_ticket(event_id):
    """Scan and verify ticket at event entry - now with secure QR verification"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if user.role not in [UserRole.ADMIN, UserRole.ORGANIZER]:
            return jsonify({"error": "Permission denied"}), 403

        event = Event.query.get_or_404(event_id)

        if user.role == UserRole.ORGANIZER and event.organizer_id != user.id:
            return jsonify(
                {"error": "You can only scan tickets for your own events"}
            ), 403

        data = request.get_json()
        qr_data = data.get("qr_data", "").strip()

        if not qr_data:
            return jsonify({"error": "QR data is required"}), 400

        # Verify the QR code signature with detailed logging
        logger.info(f"scan_ticket: Received QR data: {qr_data}")
        verification = verify_qr_token(qr_data)
        logger.info(f"scan_ticket: Verification result: {verification}")
        if not verification["valid"]:
            logger.warning(f"scan_ticket: QR verification failed for {qr_data}")
            return jsonify({"valid": False, "error": verification["error"]}), 400

        ticket_id = verification["ticket_id"]
        logger.info(f"scan_ticket: Looking for ticket with id: {ticket_id}")
        ticket = Ticket.query.get(ticket_id)

        if not ticket:
            logger.warning(f"scan_ticket: Ticket not found for id: {ticket_id}")
            return jsonify({"valid": False, "error": "Invalid ticket"}), 404

        if ticket.event_id != event_id:
            return jsonify(
                {"valid": False, "error": "Ticket is for a different event"}
            ), 400

        if ticket.is_used:
            return jsonify(
                {
                    "valid": False,
                    "error": "Ticket already used",
                    "ticket": ticket.to_dict(),
                }
            ), 400

        if ticket.payment_status == "FAILED":
            return jsonify(
                {
                    "valid": False,
                    "error": "Ticket is cancelled",
                    "ticket": ticket.to_dict(),
                }
            ), 400

        ticket.is_used = True
        ticket.used_at = datetime.utcnow()
        ticket.verified_by = user_id
        db.session.commit()

        return jsonify(
            {
                "valid": True,
                "message": "Ticket verified successfully",
                "ticket": ticket.to_dict(),
            }
        ), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"scan_ticket error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@tickets_bp.route("/event/<int:event_id>/stats", methods=["GET"])
@jwt_required()
def get_ticket_stats(event_id):
    """Get ticket statistics for an event"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        event = Event.query.get_or_404(event_id)

        if user.role not in [UserRole.ADMIN, UserRole.ORGANIZER]:
            return jsonify({"error": "Permission denied"}), 403

        if user.role == UserRole.ORGANIZER and event.organizer_id != user.id:
            return jsonify(
                {"error": "You can only view stats for your own events"}
            ), 403

        ticket_types = TicketTypeModel.query.filter_by(event_id=event_id).all()

        stats = {
            "total_tickets_available": sum(tt.quantity for tt in ticket_types),
            "total_tickets_sold": sum(tt.sold_quantity for tt in ticket_types),
            "total_revenue": sum(tt.sold_quantity * tt.price for tt in ticket_types),
            "ticket_types": [tt.to_dict() for tt in ticket_types],
            "valid_tickets": Ticket.query.filter_by(
                event_id=event_id, payment_status="COMPLETED"
            ).count(),
            "used_tickets": Ticket.query.filter_by(
                event_id=event_id, is_used=True
            ).count(),
            "cancelled_tickets": Ticket.query.filter_by(
                event_id=event_id, payment_status="FAILED"
            ).count(),
        }

        return jsonify({"stats": stats}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@tickets_bp.route("/event/<int:event_id>/search", methods=["GET", "POST"])
@jwt_required()
def search_event_tickets(event_id):
    """Search tickets for an event by phone, email, or ticket number"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        event = Event.query.get_or_404(event_id)

        if user.role not in [UserRole.ADMIN, UserRole.ORGANIZER]:
            return jsonify({"error": "Permission denied"}), 403

        if user.role == UserRole.ORGANIZER and event.organizer_id != user.id:
            return jsonify(
                {"error": "You can only search tickets for your own events"}
            ), 403

        # For POST requests, read from JSON body; for GET, read from query params
        if request.method == "POST":
            data = request.get_json() or {}
            search_query = data.get("search", "").strip().lower()
        else:
            search_query = request.args.get("search", "").strip().lower()

        if not search_query:
            return jsonify({"tickets": []}), 200

        # Search by ticket number, guest email, or guest name
        query = Ticket.query.filter_by(event_id=event_id)

        # Add search conditions
        search_conditions = []

        # Search by ticket number (case insensitive)
        search_conditions.append(Ticket.ticket_number.ilike(f"%{search_query}%"))

        # Search by guest email
        search_conditions.append(Ticket.guest_email.ilike(f"%{search_query}%"))

        # Search by guest name
        search_conditions.append(Ticket.guest_name.ilike(f"%{search_query}%"))

        # Combine conditions with OR
        query = query.filter(or_(*search_conditions))

        tickets = query.order_by(Ticket.purchased_at.desc()).limit(20).all()

        return jsonify(
            {"tickets": [ticket.to_dict() for ticket in tickets], "count": len(tickets)}
        ), 200

    except Exception as e:
        logger.error(f"search_event_tickets error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@tickets_bp.route("/debug/reset-ticket/<int:ticket_id>", methods=["POST"])
def debug_reset_ticket(ticket_id):
    """Debug endpoint to reset ticket usage (for testing)"""
    try:
        ticket = Ticket.query.get(ticket_id)
        if not ticket:
            return jsonify({"error": "Ticket not found"}), 404

        ticket.is_used = False
        ticket.used_at = None
        ticket.verified_by = None
        db.session.commit()

        return jsonify(
            {
                "message": f"Ticket {ticket_id} has been reset",
                "ticket": ticket.to_dict(),
            }
        ), 200
    except Exception as e:
        logger.error(f"debug_reset_ticket error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@tickets_bp.route("/debug/list-used-tickets/<int:event_id>", methods=["GET"])
def debug_list_used_tickets(event_id):
    """Debug endpoint to list all used tickets for an event"""
    try:
        used_tickets = (
            Ticket.query.filter_by(event_id=event_id, is_used=True)
            .order_by(Ticket.used_at.desc())
            .all()
        )

        return jsonify(
            {"count": len(used_tickets), "tickets": [t.to_dict() for t in used_tickets]}
        ), 200
    except Exception as e:
        logger.error(f"debug_list_used_tickets error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@tickets_bp.route("/confirm-by-code", methods=["POST"])
@jwt_required()
def confirm_ticket_by_code():
    """Confirm ticket entry by ticket number (for manual/backup verification)"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if user.role not in [UserRole.ADMIN, UserRole.ORGANIZER]:
            return jsonify({"error": "Permission denied"}), 403

        data = request.get_json()
        ticket_code = data.get("ticket_code", "").strip().upper()
        event_id = data.get("event_id")

        if not ticket_code:
            return jsonify({"error": "Ticket code is required"}), 400

        if not event_id:
            return jsonify({"error": "Event ID is required"}), 400

        event = Event.query.get(event_id)
        if not event:
            return jsonify({"error": "Event not found"}), 404

        if user.role == UserRole.ORGANIZER and event.organizer_id != user.id:
            return jsonify(
                {"error": "You can only verify tickets for your own events"}
            ), 403

        ticket = Ticket.query.filter_by(
            ticket_number=ticket_code, event_id=event_id
        ).first()

        if not ticket:
            return jsonify({"valid": False, "error": "Ticket not found"}), 404

        if ticket.is_used:
            return jsonify(
                {
                    "valid": False,
                    "error": "Ticket has already been used",
                    "used_at": ticket.used_at,
                    "ticket": ticket.to_dict(),
                }
            ), 400

        if ticket.payment_status == "FAILED":
            return jsonify(
                {
                    "valid": False,
                    "error": "Ticket has been cancelled",
                    "ticket": ticket.to_dict(),
                }
            ), 400

        if ticket.payment_status != "COMPLETED":
            return jsonify(
                {
                    "valid": False,
                    "error": f"Ticket status is {ticket.payment_status}, not valid for entry",
                    "ticket": ticket.to_dict(),
                }
            ), 400

        # Confirm the ticket
        ticket.is_used = True
        ticket.used_at = datetime.utcnow()
        ticket.verified_by = user_id
        db.session.commit()

        return jsonify(
            {
                "valid": True,
                "message": "Ticket confirmed successfully",
                "ticket": ticket.to_dict(),
            }
        ), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"confirm_ticket_by_code error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500
