"""
Reports Routes - Analytics and Report Generation
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from sqlalchemy import text

from extensions import db
from models import (
    User, UserRole, Event, EventStatus,
    Ticket, TicketTypeModel, Category,
    MpesaTransaction
)

reports_bp = Blueprint('reports', __name__)
@reports_bp.route('/generate', methods=['POST'])
@jwt_required()
def generate_report():
    """Generate a report based on type and date range"""
    try:
        user = User.query.get(get_jwt_identity())

        if user.role != UserRole.ADMIN:
            return jsonify({'error': 'Permission denied. Admin access required.'}), 403

        data = request.get_json() or {}
        report_type = data.get('type', 'overview')
        start_date = data.get('start_date')
        end_date = data.get('end_date')

        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')

        report_data = {}

        if report_type in ['overview', 'full']:
            report_data['overview'] = get_overview_stats(start_date, end_date)

        if report_type in ['revenue', 'full']:
            report_data['revenue'] = get_revenue_stats(start_date, end_date)

        if report_type in ['events', 'full']:
            report_data['events'] = get_events_stats(start_date, end_date)

        if report_type in ['users', 'full']:
            report_data['users'] = get_users_stats(start_date, end_date)

        return jsonify({
            'report_type': report_type,
            'start_date': start_date.isoformat() if start_date else None,
            'end_date': end_date.isoformat() if end_date else None,
            'generated_at': datetime.utcnow().isoformat(),
            'data': report_data
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    @reports_bp.route('/overview', methods=['GET'])
@jwt_required()
def get_reports_overview():
    """Get overview statistics for reports page"""
    try:
        user = User.query.get(get_jwt_identity())

        if user.role != UserRole.ADMIN:
            return jsonify({'error': 'Permission denied'}), 403

        return jsonify({
            'overview': get_overview_stats(),
            'recent_reports': get_recent_reports()
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
@reports_bp.route('/analytics', methods=['GET'])
@jwt_required()
def get_analytics():
    """Get analytics data with filtering"""
    try:
        user = User.query.get(get_jwt_identity())

        if not user or user.role != UserRole.ADMIN:
            return jsonify({'error': 'Permission denied'}), 403

        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        event_type = request.args.get('type', 'all')
        category_id = request.args.get('category')

        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')

        filters = {}
        if event_type != 'all':
            filters['is_published'] = event_type == 'published'
        if category_id:
            filters['category_id'] = category_id

        return jsonify({
            'overview': get_overview_stats(start_date, end_date),
            'revenue': get_revenue_stats(start_date, end_date),
            'events': get_events_stats(start_date, end_date, filters),
            'users': get_users_stats(start_date, end_date),
            'filters_applied': {
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None,
                'type': event_type,
                'category': category_id
            }
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    @reports_bp.route('/events/export', methods=['GET'])
@jwt_required()
def export_events_report():
    """Export events data"""
    try:
        user = User.query.get(get_jwt_identity())
        if user.role != UserRole.ADMIN:
            return jsonify({'error': 'Permission denied'}), 403

        events = Event.query.all()
        data = []

        for event in events:
            ticket_types = TicketTypeModel.query.filter_by(event_id=event.id).all()
            total_tickets = sum(t.quantity for t in ticket_types)
            sold_tickets = sum(t.sold_quantity for t in ticket_types)
            revenue = sum(t.sold_quantity * t.price for t in ticket_types)

            organizer = User.query.get(event.organizer_id)
            category = Category.query.get(event.category_id)

            data.append({
                'id': event.id,
                'title': event.title,
                'status': event.status.value if hasattr(event.status, 'value') else event.status,
                'organizer_name': organizer.name if organizer else 'Unknown',
                'category_name': category.name if category else 'Uncategorized',
                'total_tickets': total_tickets,
                'sold_tickets': sold_tickets,
                'revenue': float(revenue),
                'occupancy_rate': (sold_tickets / total_tickets * 100) if total_tickets else 0
            })

        return jsonify({
            'events': data,
            'total': len(data),
            'generated_at': datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500



