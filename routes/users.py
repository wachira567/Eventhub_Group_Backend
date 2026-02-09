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

