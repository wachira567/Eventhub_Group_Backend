"""
Moderation Routes - Event Approval/Rejection
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from jwt.exceptions import ExpiredSignatureError
from datetime import datetime
import logging

from extensions import db
from models import User, UserRole, Event, EventStatus
from services.email_service import (
    send_event_approval_email,
    send_event_rejection_email
)

logger = logging.getLogger(__name__)

moderation_bp = Blueprint('moderation', __name__)
@jwt_required()
@moderation_bp.route('/pending', methods=['GET'])
def get_pending_events():
    """Get all pending events for moderation"""
    try:
        verify_jwt_in_request()
        user = User.query.get(get_jwt_identity())

        if user.role not in [UserRole.ADMIN, UserRole.MODERATOR]:
            return jsonify({'error': 'Moderator access required'}), 403

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)

        pagination = Event.query.filter_by(is_published=False)\
            .order_by(Event.created_at.asc())\
            .paginate(page=page, per_page=per_page, error_out=False)

        return jsonify({
            'events': [e.to_dict() for e in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        }), 200

    except ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except Exception as e:
        logger.exception("Error fetching pending events")
        return jsonify({'error': str(e)}), 500
    @jwt_required()
@moderation_bp.route('/event/<int:event_id>', methods=['GET'])
def get_event_for_moderation(event_id):
    """Get event details for moderation"""
    try:
        verify_jwt_in_request()
        user = User.query.get(get_jwt_identity())

        if user.role not in [UserRole.ADMIN, UserRole.MODERATOR]:
            return jsonify({'error': 'Moderator access required'}), 403

        event = Event.query.get_or_404(event_id)

        if event.status not in [EventStatus.DRAFT, EventStatus.PENDING]:
            return jsonify({'error': 'Event is not pending moderation'}), 400

        return jsonify({'event': event.to_dict()}), 200

    except ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except Exception as e:
        logger.exception("Error fetching event for moderation")
        return jsonify({'error': str(e)}), 500
    @jwt_required()
@moderation_bp.route('/event/<int:event_id>/approve', methods=['POST'])
def approve_event(event_id):
    """Approve an event"""
    try:
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if user.role not in [UserRole.ADMIN, UserRole.MODERATOR]:
            return jsonify({'error': 'Moderator access required'}), 403

        event = Event.query.get_or_404(event_id)

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
            send_event_approval_email(
                organizer.email,
                organizer.name,
                event.title,
                notes
            )

        return jsonify({
            'message': 'Event approved successfully',
            'event': event.to_dict()
        }), 200

    except ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except Exception as e:
        db.session.rollback()
        db.session.remove()
        logger.exception("Error approving event")
        return jsonify({'error': str(e)}), 500
    @jwt_required()
@moderation_bp.route('/event/<int:event_id>/reject', methods=['POST'])
def reject_event(event_id):
    """Reject an event"""
    try:
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if user.role not in [UserRole.ADMIN, UserRole.MODERATOR]:
            return jsonify({'error': 'Moderator access required'}), 403

        event = Event.query.get_or_404(event_id)

        if event.status == EventStatus.REJECTED:
            return jsonify({'error': 'Event is already rejected'}), 400

        data = request.get_json(silent=True) or {}
        reason = data.get('reason', '').strip()

        if not reason:
            return jsonify({'error': 'Rejection reason is required'}), 400

        event.status = EventStatus.REJECTED
        event.moderated_at = datetime.utcnow()
        event.moderated_by = user_id
        event.moderation_notes = reason

        db.session.commit()

        organizer = User.query.get(event.organizer_id)
        if organizer:
            send_event_rejection_email(
                organizer.email,
                organizer.name,
                event.title,
                reason
            )

        return jsonify({
            'message': 'Event rejected',
            'event': event.to_dict()
        }), 200

    except ExpiredSignatureError:
        return jsonify({'error': 'Token expired'}), 401
    except Exception as e:
        db.session.rollback()
        db.session.remove()
        logger.exception("Error rejecting event")
        return jsonify({'error': str(e)}), 500
    @jwt_required()
@moderation_bp.route('/event/<int:event_id>/request-changes', methods=['POST'])
def request_event_changes(event_id):
    """Request changes to an event"""
    try:
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if user.role not in [UserRole.ADMIN, UserRole.MODERATOR]:
            return jsonify({'error': 'Moderator access required'}), 403

        event = Event.query.get_or_404(event_id)

        if event.status not in [EventStatus.DRAFT, EventStatus.PENDING]:
            return jsonify({'error': 'Event is not pending moderation'}), 400

        data = request.get_json(silent=True) or {}
        feedback = data.get('feedback', '').strip()

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
        db.session.remove()
        logger.exception("Error requesting event changes")
        return jsonify({'error': str(e)}), 500




