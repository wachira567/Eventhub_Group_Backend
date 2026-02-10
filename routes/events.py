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
    

@mpesa_bp.route('/query/<int:transaction_id>', methods=['POST'])
def query_payment(transaction_id):
    try:
        transaction = MpesaTransaction.query.get_or_404(transaction_id)
        if not transaction.checkout_request_id:
            return jsonify({'error': 'No checkout request ID'}), 400
        
        response = mpesa_service.query_stk_status(
            checkout_request_id=transaction.checkout_request_id
        )
        
        if response.get('ResultCode') == 0:
            transaction.status = 'completed'
            transaction.mpesa_receipt = response.get('Result', {}).get('MpesaReceiptNumber')
            db.session.commit()
            return jsonify({
                'status': 'completed',
                'mpesa_receipt': transaction.mpesa_receipt
            }), 200
        else:
            transaction.status = 'failed'
            transaction.result_desc = response.get('ResultDesc')
            db.session.commit()
            return jsonify({
                'status': 'failed',
                'error': response.get('ResultDesc')
            }), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@mpesa_bp.route('/transactions', methods=['GET'])
def get_transactions():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', '').strip()
        
        query = MpesaTransaction.query
        if status:
            query = query.filter_by(status=status)
        
        pagination = query.order_by(MpesaTransaction.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'transactions': [t.to_dict() for t in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
