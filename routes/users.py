"""
Users Routes - Admin User Management
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from datetime import datetime
from sqlalchemy import or_
from extensions import db
from models import User, UserRole, Event, Ticket


users_bp = Blueprint('users', __name__)


@jwt_required()
@users_bp.route('', methods=['GET'])
def get_users():
    """Get all users (admin only)"""
    try:
        # Explicitly verify JWT before getting identity
        verify_jwt_in_request()
        current_user_id = int(get_jwt_identity())
        current_user = User.query.get(current_user_id)
        
        if current_user.role not in [UserRole.ADMIN]:
            return jsonify({'error': 'Admin access required'}), 403
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('q', '').strip()
        role = request.args.get('role', '').strip()
        status = request.args.get('status', '').strip()
        
        query = User.query
        
        if search:
            search_term = f'%{search}%'
            query = query.filter(
                or_(
                    User.name.ilike(search_term),
                    User.email.ilike(search_term),
                    User.phone.ilike(search_term)
                )
            )
        
        if role:
            try:
                role_enum = UserRole(role)
                query = query.filter_by(role=role_enum)
            except ValueError:
                pass
        
        if status:
            if status == 'active':
                query = query.filter_by(is_active=True)
            elif status == 'inactive':
                query = query.filter_by(is_active=False)
            elif status == 'verified':
                query = query.filter_by(is_verified=True)
            elif status == 'unverified':
                query = query.filter_by(is_verified=False)
        
        pagination = query.order_by(User.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'users': [user.to_dict() for user in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@jwt_required()
@users_bp.route('/recent', methods=['GET'])
def get_recent_users():
    """Get recently registered users (admin only)"""
    try:
        # Explicitly verify JWT before getting identity
        verify_jwt_in_request()
        current_user_id = int(get_jwt_identity())
        current_user = User.query.get(current_user_id)
        
        if current_user.role not in [UserRole.ADMIN]:
            return jsonify({'error': 'Admin access required'}), 403
        
        limit = request.args.get('limit', 10, type=int)
        
        users = User.query.order_by(User.created_at.desc()).limit(limit).all()
        
        return jsonify({
            'users': [user.to_dict() for user in users]
        }), 200
        
    except Exception as e:
        print(f"USERS ERROR in get_recent_users: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@jwt_required()
@users_bp.route('/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Get user details"""
    try:
        # Explicitly verify JWT before getting identity
        verify_jwt_in_request()
        current_user_id = int(get_jwt_identity())
        current_user = User.query.get(current_user_id)
        
        user = User.query.get_or_404(user_id)
        
        if current_user.role not in [UserRole.ADMIN] and current_user.id != user_id:
            return jsonify({'error': 'Permission denied'}), 403
        
        return jsonify({'user': user.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@jwt_required()
@users_bp.route('/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """Update user (admin only for other users)"""
    try:
        # Explicitly verify JWT before getting identity
        verify_jwt_in_request()
        current_user_id = int(get_jwt_identity())
        current_user = User.query.get(current_user_id)
        
        user = User.query.get_or_404(user_id)
        
        if current_user.role not in [UserRole.ADMIN] and current_user.id != user_id:
            return jsonify({'error': 'Permission denied'}), 403
        
        data = request.get_json()
        
        if 'name' in data:
            if not data['name'].strip():
                return jsonify({'error': 'Name cannot be empty'}), 400
            user.name = data['name'].strip()
        
        if 'phone' in data:
            user.phone = data['phone'].strip() if data['phone'] else None
        
        if 'is_active' in data and current_user.role == UserRole.ADMIN:
            user.is_active = data['is_active']
        
        if 'role' in data and current_user.role == UserRole.ADMIN:
            try:
                user.role = UserRole(data['role'])
            except ValueError:
                return jsonify({'error': 'Invalid role'}), 400
        
        if 'is_verified' in data and current_user.role == UserRole.ADMIN:
            user.is_verified = data['is_verified']
        
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'User updated successfully',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@jwt_required()
@users_bp.route('/<int:user_id>', methods=['DELETE'])
def deactivate_user(user_id):
    """Deactivate a user (admin only)"""
    try:
        # Explicitly verify JWT before getting identity
        verify_jwt_in_request()
        current_user_id = int(get_jwt_identity())
        current_user = User.query.get(current_user_id)
        
        if current_user.role not in [UserRole.ADMIN]:
            return jsonify({'error': 'Admin access required'}), 403
        
        user = User.query.get_or_404(user_id)
        
        if user.id == current_user.id:
            return jsonify({'error': 'Cannot deactivate your own account'}), 400
        
        user.is_active = False
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'message': 'User deactivated successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@jwt_required()
@users_bp.route('/<int:user_id>/activate', methods=['POST'])
def activate_user(user_id):
    """Activate a user (admin only)"""
    try:
        # Explicitly verify JWT before getting identity
        verify_jwt_in_request()
        current_user_id = int(get_jwt_identity())
        current_user = User.query.get(current_user_id)
        
        if current_user.role not in [UserRole.ADMIN]:
            return jsonify({'error': 'Admin access required'}), 403
        
        user = User.query.get_or_404(user_id)
        
        user.is_active = True
        user.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'message': 'User activated successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@jwt_required()
@users_bp.route('/<int:user_id>/events', methods=['GET'])
def get_user_events(user_id):
    """Get events created by a user"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 12, type=int)
        
        user = User.query.get_or_404(user_id)
        
        pagination = Event.query.filter_by(organizer_id=user_id)\
            .order_by(Event.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'events': [event.to_dict() for event in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@jwt_required()
@users_bp.route('/<int:user_id>/tickets', methods=['GET'])
def get_user_tickets(user_id):
    """Get tickets purchased by a user"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        user = User.query.get_or_404(user_id)
        
        pagination = Ticket.query.filter_by(user_id=user_id)\
            .order_by(Ticket.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'tickets': [ticket.to_dict() for ticket in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@jwt_required()
@users_bp.route('/stats', methods=['GET'])
def get_user_stats():
    """Get user statistics (admin only)"""
    try:
        # Explicitly verify JWT before getting identity
        verify_jwt_in_request()
        current_user_id = int(get_jwt_identity())
        current_user = User.query.get(current_user_id)
        
        if current_user.role not in [UserRole.ADMIN]:
            return jsonify({'error': 'Admin access required'}), 403
        
        stats = {
            'total_users': User.query.count(),
            'active_users': User.query.filter_by(is_active=True).count(),
            'verified_users': User.query.filter_by(is_verified=True).count(),
            'organizers': User.query.filter_by(role=UserRole.ORGANIZER).count(),
            'attendees': User.query.filter_by(role=UserRole.ATTENDEE).count(),
            'admins': User.query.filter_by(role=UserRole.ADMIN).count(),
            'moderators': User.query.filter_by(role=UserRole.MODERATOR).count()
        }
        
        return jsonify({'stats': stats}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
