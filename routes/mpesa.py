"""
MPESA Payment Routes
"""

from flask import Blueprint, request, jsonify
from datetime import datetime
from extensions import db
from models import MpesaTransaction, Ticket, TicketStatus, User, Event, TicketTypeModel
from services.mpesa_service import mpesa_service
from services.email_service import send_ticket_confirmation


mpesa_bp = Blueprint('mpesa', __name__)


@mpesa_bp.route('/stk-push-callback', methods=['POST'])
@mpesa_bp.route('/callback', methods=['POST'])
def stk_push_callback():
    """Handle M-Pesa STK Push callback"""
    try:
        data = request.get_json()
        print(f"[MPESA CALLBACK] Raw data: {data}")
        
        result = data.get('Body', {}).get('stkCallback', {})
        result_code = result.get('ResultCode')
        result_desc = result.get('ResultDesc')
        checkout_request_id = result.get('CheckoutRequestID')
        
        print(f"[MPESA CALLBACK] ResultCode: {result_code}, ResultDesc: {result_desc}, CheckoutRequestID: {checkout_request_id}")
        
        transaction = MpesaTransaction.query.filter_by(
            checkout_request_id=checkout_request_id
        ).first()
        
        if not transaction:
            print(f"[MPESA CALLBACK] Transaction not found for checkout_request_id: {checkout_request_id}")
            return jsonify({'error': 'Transaction not found'}), 404
        
        if result_code == 0:
            callback_metadata = result.get('CallbackMetadata', {})
            items = callback_metadata.get('Item', [])
            
            amount = None
            mpesa_receipt = None
            phone = None
            
            for item in items:
                if item.get('Name') == 'Amount':
                    amount = float(item.get('Value'))
                elif item.get('Name') == 'MpesaReceiptNumber':
                    mpesa_receipt = item.get('Value')
                elif item.get('Name') == 'PhoneNumber':
                    phone = item.get('Value')
            
            transaction.status = 'completed'
            transaction.mpesa_receipt = mpesa_receipt
            transaction.result_desc = result_desc
            transaction.completed_at = datetime.utcnow()
            
            if amount:
                transaction.amount = amount
            
            # Update associated ticket payment status
            if transaction.ticket_id:
                ticket = Ticket.query.get(transaction.ticket_id)
                if ticket:
                    ticket.payment_status = 'completed'
                    ticket.mpesa_receipt = mpesa_receipt
            
            db.session.commit()
            
            # Send confirmation email
            _send_payment_confirmation_email(transaction)
            
            return jsonify({'message': 'Payment processed successfully'}), 200
        else:
            transaction.status = 'failed'
            transaction.result_desc = result_desc
            db.session.commit()
            
            return jsonify({
                'message': 'Payment failed',
                'error': result_desc
            }), 400
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


def _send_payment_confirmation_email(transaction):
    """Send payment confirmation email"""
    try:
        # Get user and event details
        user = User.query.get(transaction.user_id) if transaction.user_id else None
        event = Event.query.get(transaction.event_id)
        ticket_type = TicketTypeModel.query.get(transaction.ticket_type_id)
        
        # Get ticket
        ticket = Ticket.query.get(transaction.ticket_id) if transaction.ticket_id else None
        
        if not event:
            return False
        
        # Determine recipient
        if user:
            recipient_email = user.email
            recipient_name = user.name
        elif ticket and ticket.is_guest:
            recipient_email = ticket.guest_email
            recipient_name = ticket.guest_name or 'Guest'
        else:
            return False
        
        # Get ticket number
        ticket_number = ticket.ticket_number if ticket else f"TXN{transaction.id}"
        quantity = transaction.quantity or 1
        total_price = float(transaction.amount) if transaction.amount else 0
        
        # Send email without PDF (PDF generation may require additional setup)
        success = send_ticket_confirmation(
            user_email=recipient_email,
            user_name=recipient_name,
            event_title=event.title,
            ticket_number=ticket_number,
            quantity=quantity,
            total_price=total_price
        )
        
        print(f"Payment confirmation email sent: {success} to {recipient_email}")
        return success
    
    except Exception as e:
        print(f"Error sending payment confirmation email: {e}")
        return False


@mpesa_bp.route('/b2c-callback', methods=['POST'])
def b2c_callback():
    """Handle M-Pesa B2C callback (for refunds)"""
    try:
        data = request.get_json()
        
        result = data.get('Body', {})
        result_code = result.get('ResultCode')
        result_desc = result.get('ResultDesc')
        transaction_id = result.get('TransactionID')
        conversation_id = result.get('ConversationID')
        
        return jsonify({'message': 'B2C callback received'}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@mpesa_bp.route('/status/<path:identifier>', methods=['GET'])
def get_payment_status(identifier):
    """Get payment status for a transaction - accepts either transaction_id (int) or checkout_request_id (string)"""
    try:
        # Check if identifier is a numeric transaction_id
        if identifier.isdigit():
            transaction = MpesaTransaction.query.get(int(identifier))
        else:
            # Assume it's a checkout_request_id
            transaction = MpesaTransaction.query.filter_by(
                checkout_request_id=identifier
            ).first()
        
        if not transaction:
            return jsonify({'error': 'Transaction not found'}), 404
        
        return jsonify({
            'transaction': transaction.to_dict(),
            'status': transaction.status,
            'payment_completed': transaction.status == 'completed'
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@mpesa_bp.route('/simulate-complete/<path:identifier>', methods=['POST'])
def simulate_payment_complete(identifier):
    """Simulate payment completion for sandbox testing"""
    try:
        # Check if identifier is a numeric transaction_id
        if identifier.isdigit():
            transaction = MpesaTransaction.query.get(int(identifier))
        else:
            # Assume it's a checkout_request_id
            transaction = MpesaTransaction.query.filter_by(
                checkout_request_id=identifier
            ).first()
        
        if not transaction:
            return jsonify({'error': 'Transaction not found'}), 404
        
        # Simulate successful payment
        transaction.status = 'completed'
        transaction.mpesa_receipt = f"TEST{transaction.id}{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        transaction.result_desc = "Payment completed successfully"
        transaction.completed_at = datetime.utcnow()
        
        # Update associated ticket payment status
        if transaction.ticket_id:
            ticket = Ticket.query.get(transaction.ticket_id)
            if ticket:
                ticket.payment_status = 'completed'
                ticket.mpesa_receipt = transaction.mpesa_receipt
        
        db.session.commit()
        
        # Send confirmation email
        _send_payment_confirmation_email(transaction)
        
        return jsonify({
            'message': 'Payment simulated successfully',
            'transaction': transaction.to_dict(),
            'status': 'completed'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@mpesa_bp.route('/query/<int:transaction_id>', methods=['POST'])
def query_payment(transaction_id):
    """Query M-Pesa payment status"""
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
            transaction.completed_at = datetime.utcnow()
            
            # Update associated ticket payment status
            if transaction.ticket_id:
                ticket = Ticket.query.get(transaction.ticket_id)
                if ticket:
                    ticket.payment_status = 'completed'
                    ticket.mpesa_receipt = transaction.mpesa_receipt
            
            db.session.commit()
            
            # Send confirmation email
            _send_payment_confirmation_email(transaction)
            
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
    """Get all M-Pesa transactions (admin only)"""
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
