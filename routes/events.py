from flask import Blueprint, request, jsonify
from datetime import datetime
from extensions import db
from models import MpesaTransaction, Ticket, TicketStatus
from services.mpesa_service import mpesa_service

mpesa_bp = Blueprint("mpesa", __name__)


@mpesa_bp.route("/stk-push-callback", methods=["POST"])
def stk_push_callback():
    try:
        data = request.get_json()

        result = data.get("Body", {}).get("stkCallback", {})
        result_code = result.get("ResultCode")
        result_desc = result.get("ResultDesc")
        checkout_request_id = result.get("CheckoutRequestID")

        transaction = MpesaTransaction.query.filter_by(
            checkout_request_id=checkout_request_id
        ).first()

        if not transaction:
            return jsonify({"error": "Transaction not found"}), 404

        if result_code == 0:
            callback_metadata = result.get("CallbackMetadata", {})
            items = callback_metadata.get("Item", [])

            amount = None
            mpesa_receipt = None
            phone = None

            for item in items:
                if item.get("Name") == "Amount":
                    amount = float(item.get("Value"))
                elif item.get("Name") == "MpesaReceiptNumber":
                    mpesa_receipt = item.get("Value")
                elif item.get("Name") == "PhoneNumber":
                    phone = item.get("Value")

            transaction.status = "completed"
            transaction.mpesa_receipt = mpesa_receipt
            transaction.result_desc = result_desc

            if amount:
                transaction.amount = amount

            db.session.commit()
            return jsonify({"message": "Payment processed successfully"}), 200
        else:
            transaction.status = "failed"
            transaction.result_desc = result_desc
            db.session.commit()

            return jsonify({"message": "Payment failed", "error": result_desc}), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@mpesa_bp.route("/b2c-callback", methods=["POST"])
def b2c_callback():
    try:
        data = request.get_json()
        result = data.get("Body", {})
        return jsonify({"message": "B2C callback received"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@mpesa_bp.route("/status/<path:identifier>", methods=["GET"])
def get_payment_status(identifier):
    try:
        if identifier.isdigit():
            transaction = MpesaTransaction.query.get(int(identifier))
        else:
            transaction = MpesaTransaction.query.filter_by(
                checkout_request_id=identifier
            ).first()

        if not transaction:
            return jsonify({"error": "Transaction not found"}), 404

        return jsonify(
            {
                "transaction": transaction.to_dict(),
                "status": transaction.status,
                "payment_completed": transaction.status == "completed",
            }
        ), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
