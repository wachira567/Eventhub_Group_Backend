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
@reports_bp.route('/users/export', methods=['GET'])
@jwt_required()
def export_users_report():
    """Export users data"""
    try:
        user = User.query.get(get_jwt_identity())
        if user.role != UserRole.ADMIN:
            return jsonify({'error': 'Permission denied'}), 403

        users = User.query.all()
        data = []

        for u in users:
            tickets = Ticket.query.filter_by(user_id=u.id).all()
            spent = sum(float(t.total_price) for t in tickets if t.payment_status == 'COMPLETED')

            data.append({
                'id': u.id,
                'name': u.name,
                'email': u.email,
                'role': u.role.value if hasattr(u.role, 'value') else u.role,
                'is_verified': u.is_verified,
                'is_active': u.is_active,
                'total_tickets': len(tickets),
                'total_spent': spent
            })

        return jsonify({
            'users': data,
            'total': len(data),
            'generated_at': datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
@reports_bp.route('/tickets/export', methods=['GET'])
@jwt_required()
def export_tickets_report():
    """Export tickets data"""
    try:
        user = User.query.get(get_jwt_identity())
        if user.role != UserRole.ADMIN:
            return jsonify({'error': 'Permission denied'}), 403

        tickets = Ticket.query.all()
        data = []

        for t in tickets:
            event = Event.query.get(t.event_id)
            buyer = User.query.get(t.user_id)
            ticket_type = TicketTypeModel.query.get(t.ticket_type_id)

            data.append({
                'ticket_number': t.ticket_number,
                'event': event.title if event else 'Unknown',
                'ticket_type': ticket_type.name if ticket_type else 'Unknown',
                'buyer': buyer.name if buyer else 'Unknown',
                'status': t.payment_status,
                'total_price': t.total_price
            })

        return jsonify({
            'tickets': data,
            'total': len(data),
            'generated_at': datetime.utcnow().isoformat()
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500
    def get_overview_stats(start_date=None, end_date=None):
    users_count = User.query.count()
    events_count = Event.query.count()
    approved_events = Event.query.filter_by(status=EventStatus.APPROVED).count()
    tickets_count = Ticket.query.filter_by(payment_status='COMPLETED').count()

    transactions = MpesaTransaction.query.filter_by(status='COMPLETED')
    if start_date:
        transactions = transactions.filter(MpesaTransaction.created_at >= start_date)
    if end_date:
        transactions = transactions.filter(MpesaTransaction.created_at <= end_date)

    total_revenue = sum(float(t.amount) for t in transactions.all())

    pending_events = db.session.execute(
        text("SELECT COUNT(*) FROM events WHERE status IN ('DRAFT','PENDING_APPROVAL')")
    ).scalar()

    return {
        'total_users': users_count,
        'total_events': events_count,
        'published_events': approved_events,
        'total_tickets_sold': tickets_count,
        'total_revenue': total_revenue,
        'pending_events': pending_events
    }


def get_revenue_stats(start_date=None, end_date=None):
    transactions = MpesaTransaction.query.filter_by(status='COMPLETED')
    if start_date:
        transactions = transactions.filter(MpesaTransaction.created_at >= start_date)
    if end_date:
        transactions = transactions.filter(MpesaTransaction.created_at <= end_date)

    txs = transactions.all()
    total = sum(float(t.amount) for t in txs)

    daily = {}
    for t in txs:
        key = t.created_at.strftime('%Y-%m-%d')
        daily[key] = daily.get(key, 0) + float(t.amount)

    return {
        'total_revenue': total,
        'transaction_count': len(txs),
        'average_transaction': total / len(txs) if txs else 0,
        'daily_breakdown': daily
    }
def get_events_stats(start_date=None, end_date=None, filters=None):
    query = Event.query
    if filters:
        query = query.filter_by(**filters)
    if start_date:
        query = query.filter(Event.start_date >= start_date)
    if end_date:
        query = query.filter(Event.start_date <= end_date)

    events = query.all()
    stats = []

    for e in events:
        ticket_types = TicketTypeModel.query.filter_by(event_id=e.id).all()
        total = sum(t.quantity for t in ticket_types)
        sold = sum(t.sold_quantity for t in ticket_types)
        revenue = sum(t.sold_quantity * float(t.price) for t in ticket_types)

        stats.append({
            'id': e.id,
            'title': e.title,
            'total_tickets': total,
            'sold_tickets': sold,
            'revenue': revenue
        })

    return {
        'total_events': len(events),
        'event_details': stats,
        'total_tickets_sold': sum(s['sold_tickets'] for s in stats),
        'total_revenue': sum(s['revenue'] for s in stats)
    }


def get_users_stats(start_date=None, end_date=None):
    users = User.query.all()

    roles = {}
    for u in users:
        role = u.role.value if hasattr(u.role, 'value') else u.role
        roles[role] = roles.get(role, 0) + 1

    active_users = len(set(t.user_id for t in Ticket.query.filter_by(payment_status='COMPLETED').all()))
    verified = User.query.filter_by(is_verified=True).count()

    return {
        'total_users': len(users),
        'role_distribution': roles,
        'active_users': active_users,
        'verification_rate': (verified / len(users) * 100) if users else 0
    }
def get_recent_reports():
    """Return recently generated reports (placeholder)"""
    return []




