"""
Moderation Routes - Event Approval/Rejection
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from jwt.exceptions import ExpiredSignatureError
from datetime import datetime
from extensions import db
from models import User, UserRole, Event, EventStatus
from services.email_service import send_event_approval_email, send_event_rejection_email


import logging

logger = logging.getLogger(__name__)


moderation_bp = Blueprint('moderation', __name__)


@jwt_required()
@moderation_bp.route('/pending', methods=['GET'])
def get_pending_events():
    """Get all pending events for moderation"""
    try:
        # Explicitly verify JWT before getting identity
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if user.role not in [UserRole.ADMIN, UserRole.MODERATOR]:
            return jsonify({'error': 'Moderator access required'}), 403
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        pagination = Event.query.filter_by(is_published=False)\
            .order_by(Event.created_at.asc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({'events': [event.to_dict() for event in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        }), 200
        
    except ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except Exception as e:
        print(f"MODERATION ERROR in get_pending_events: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@jwt_required()
@moderation_bp.route('/event/<int:event_id>', methods=['GET'])
def get_event_for_moderation(event_id):
    """Get event details for moderation"""
    try:
        # Explicitly verify JWT before getting identity
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if user.role not in [UserRole.ADMIN, UserRole.MODERATOR]:
            return jsonify({'error': 'Moderator access required'}), 403
        
        event = Event.query.get_or_404(event_id)
        
        # Only pending/draft events should be moderated
        if event.status not in [EventStatus.DRAFT, EventStatus.PENDING]:
            return jsonify({'error': 'Event is not pending moderation'}), 400
        
        return jsonify({'event': event.to_dict()}), 200
        
    except ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except Exception as e:
        print(f"MODERATION ERROR in get_event_for_moderation: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@jwt_required()
@moderation_bp.route('/event/<int:event_id>/approve', methods=['POST'])
def approve_event(event_id):
    """Approve an event"""
    try:
        # Explicitly verify JWT before getting identity
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if user.role not in [UserRole.ADMIN, UserRole.MODERATOR]:
            return jsonify({'error': 'Moderator access required'}), 403
        
        event = Event.query.get_or_404(event_id)
        
        # Check if event is already approved
        if event.status == EventStatus.APPROVED:
            return jsonify({'error': 'Event is already approved'}), 400
        
        data = request.get_json(silent=True) or {}
        notes = data.get('notes', '').strip()
        
        event.status = EventStatus.APPROVED
        event.is_published = True
        event.moderated_at = datetime.utcnow()
        event.moderated_by = user_id
        event.moderation_notes = notes
        
        db.session.commit()
        
        organizer = User.query.get(event.organizer_id)
        if organizer:
            send_event_approval_email(organizer.email, organizer.name, event.title, notes)
        
        return jsonify({
            'message': 'Event approved successfully',
            'event': event.to_dict()
        }), 200
        
    except ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except Exception as e:
        db.session.rollback()
        # Try to reconnect if connection issue
        if 'connection' in str(e).lower() or 'ssl' in str(e).lower():
            db.session.remove()
        print(f"MODERATION ERROR in approve_event: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@jwt_required()
@moderation_bp.route('/event/<int:event_id>/reject', methods=['POST'])
def reject_event(event_id):
    """Reject an event"""
    try:
        # Explicitly verify JWT before getting identity
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if user.role not in [UserRole.ADMIN, UserRole.MODERATOR]:
            return jsonify({'error': 'Moderator access required'}), 403
        
        event = Event.query.get_or_404(event_id)
        
        # Check if event is already rejected
        if event.status == EventStatus.REJECTED:
            return jsonify({'error': 'Event is already rejected'}), 400
        
        data = request.get_json(silent=True)
        reason = data.get('reason', '').strip() if data else ''
        
        if not reason:
            return jsonify({'error': 'Rejection reason is required'}), 400
        
        event.status = EventStatus.REJECTED
        event.moderated_at = datetime.utcnow()
        event.moderated_by = user_id
        event.moderation_notes = reason
        
        db.session.commit()
        
        organizer = User.query.get(event.organizer_id)
        if organizer:
            send_event_rejection_email(organizer.email, organizer.name, event.title, reason)
        
        return jsonify({
            'message': 'Event rejected',
            'event': event.to_dict()
        }), 200
        
    except ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except Exception as e:
        db.session.rollback()
        # Try to reconnect if connection issue
        if 'connection' in str(e).lower() or 'ssl' in str(e).lower():
            db.session.remove()
        print(f"MODERATION ERROR in reject_event: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@jwt_required()
@moderation_bp.route('/stats', methods=['GET'])
def get_moderation_stats():
    """Get moderation statistics"""
    try:
        # Explicitly verify JWT before getting identity
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if user.role not in [UserRole.ADMIN, UserRole.MODERATOR]:
            return jsonify({'error': 'Moderator access required'}), 403
        
        stats = {
            'pending': Event.query.filter_by(is_published=False).count(),
            'approved_today': Event.query.filter(
                Event.status == EventStatus.APPROVED,
                Event.moderated_at >= datetime.utcnow().replace(hour=0, minute=0, second=0)
            ).count(),
            'rejected_today': Event.query.filter(
                Event.status == EventStatus.REJECTED,
                Event.moderated_at >= datetime.utcnow().replace(hour=0, minute=0, second=0)
            ).count(),
            'total_approved': Event.query.filter_by(status=EventStatus.APPROVED).count(),
            'total_rejected': Event.query.filter_by(status=EventStatus.REJECTED).count()
        }
        
        return jsonify({'stats': stats}), 200
        
    except ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except Exception as e:
        print(f"MODERATION ERROR in get_moderation_stats: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@jwt_required()
@moderation_bp.route('/event/<int:event_id>/request-changes', methods=['POST'])
def request_event_changes(event_id):
    """Request changes to an event (soft rejection)"""
    try:
        # Explicitly verify JWT before getting identity
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if user.role not in [UserRole.ADMIN, UserRole.MODERATOR]:
            return jsonify({'error': 'Moderator access required'}), 403
        
        event = Event.query.get_or_404(event_id)
        
        # Only pending/draft events should be moderated
        if event.status not in [EventStatus.DRAFT, EventStatus.PENDING]:
            return jsonify({'error': 'Event is not pending moderation'}), 400
        
        data = request.get_json(silent=True)
        feedback = data.get('feedback', '').strip() if data else ''
        
        if not feedback:
            return jsonify({'error': 'Feedback is required'}), 400
        
        event.status = EventStatus.DRAFT
        event.moderation_notes = feedback
        event.moderated_at = datetime.utcnow()
        event.moderated_by = user_id
        
        db.session.commit()
        
        return jsonify({
            'message': 'Change request sent to organizer',
            'feedback': feedback
        }), 200
        
    except ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except Exception as e:
        db.session.rollback()
        # Try to reconnect if connection issue
        if 'connection' in str(e).lower() or 'ssl' in str(e).lower():
            db.session.remove()
        print(f"MODERATION ERROR in request_event_changes: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500