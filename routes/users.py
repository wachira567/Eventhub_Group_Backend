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
        verify_jwt_in_request()
        current_user = User.query.get(get_jwt_identity())

        if current_user.role != UserRole.ADMIN:
            return jsonify({'error': 'Admin access required'}), 403

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('q', '').strip()
        role = request.args.get('role', '').strip()
        status = request.args.get('status', '').strip()

        query = User.query

        if search:
            term = f"%{search}%"
            query = query.filter(
                or_(
                    User.name.ilike(term),
                    User.email.ilike(term),
                    User.phone.ilike(term)
                )
            )

        if role:
            try:
                query = query.filter_by(role=UserRole(role))
            except ValueError:
                pass

        if status == 'active':
            query = query.filter_by(is_active=True)
        elif status == 'inactive':
            query = query.filter_by(is_active=False)
        elif status == 'verified':
            query = query.filter_by(is_verified=True)
        elif status == 'unverified':
            query = query.filter_by(is_verified=False)

        pagination = query.order_by(User.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify({
            'users': [u.to_dict() for u in pagination.items],
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
        verify_jwt_in_request()
        current_user = User.query.get(get_jwt_identity())

        if current_user.role != UserRole.ADMIN:
            return jsonify({'error': 'Admin access required'}), 403

        limit = request.args.get('limit', 10, type=int)
        users = User.query.order_by(User.created_at.desc()).limit(limit).all()

        return jsonify({'users': [u.to_dict() for u in users]}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    @jwt_required()
@users_bp.route('/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Get user details"""
    try:
        verify_jwt_in_request()
        current_user = User.query.get(get_jwt_identity())
        user = User.query.get_or_404(user_id)

        if current_user.role != UserRole.ADMIN and current_user.id != user_id:
            return jsonify({'error': 'Permission denied'}), 403

        return jsonify({'user': user.to_dict()}), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    @jwt_required()
@users_bp.route('/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    """Update user"""
    try:
        verify_jwt_in_request()
        current_user = User.query.get(get_jwt_identity())
        user = User.query.get_or_404(user_id)

        if current_user.role != UserRole.ADMIN and current_user.id != user_id:
            return jsonify({'error': 'Permission denied'}), 403

        data = request.get_json()

        if 'name' in data and data['name'].strip():
            user.name = data['name'].strip()

        if 'phone' in data:
            user.phone = data['phone'].strip() if data['phone'] else None

        if current_user.role == UserRole.ADMIN:
            if 'is_active' in data:
                user.is_active = data['is_active']
            if 'is_verified' in data:
                user.is_verified = data['is_verified']
            if 'role' in data:
                user.role = UserRole(data['role'])

        user.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({'message': 'User updated', 'user': user.to_dict()}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
    @jwt_required()
@users_bp.route('/<int:user_id>', methods=['DELETE'])
def deactivate_user(user_id):
    """Deactivate user"""
    try:
        verify_jwt_in_request()
        current_user = User.query.get(get_jwt_identity())

        if current_user.role != UserRole.ADMIN:
            return jsonify({'error': 'Admin access required'}), 403

        user = User.query.get_or_404(user_id)

        if user.id == current_user.id:
            return jsonify({'error': 'Cannot deactivate yourself'}), 400

        user.is_active = False
        user.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({'message': 'User deactivated'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@jwt_required()
@users_bp.route('/<int:user_id>/activate', methods=['POST'])
def activate_user(user_id):
    """Activate user"""
    try:
        verify_jwt_in_request()
        current_user = User.query.get(get_jwt_identity())

        if current_user.role != UserRole.ADMIN:
            return jsonify({'error': 'Admin access required'}), 403

        user = User.query.get_or_404(user_id)
        user.is_active = True
        user.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({'message': 'User activated'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500





