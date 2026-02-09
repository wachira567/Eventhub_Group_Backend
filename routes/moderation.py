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

