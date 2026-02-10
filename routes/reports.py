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
    """Generate a PDF report based on type and date range"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if user.role not in [UserRole.ADMIN]:
            return jsonify({'error': 'Permission denied. Admin access required.'}), 403
        
        data = request.get_json()
        report_type = data.get('type', 'overview')
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        # Parse dates
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
        
        # Generate report data based on type
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
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if user.role not in [UserRole.ADMIN]:
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
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user or (user.role != UserRole.ADMIN and str(user.role) != 'ADMIN'):
            return jsonify({'error': 'Permission denied'}), 403
        
        # Query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        event_type = request.args.get('type', 'all')
        category_id = request.args.get('category')
        
        # Parse dates
        if start_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d')
        if end_date:
            end_date = datetime.strptime(end_date, '%Y-%m-%d')
        
        # Build base filters
        event_filters = {}
        if event_type != 'all':
            event_filters['is_published'] = event_type == 'published'
        if category_id:
            event_filters['category_id'] = category_id
        
        overview = get_overview_stats(start_date, end_date)
        revenue = get_revenue_stats(start_date, end_date)
        events = get_events_stats(start_date, end_date, event_filters)
        users = get_users_stats(start_date, end_date)
        
        return jsonify({
            'overview': overview,
            'revenue': revenue,
            'events': events,
            'users': users,
            'filters_applied': {
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None,
                'type': event_type,
                'category': category_id
            }
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@reports_bp.route('/events/export', methods=['GET'])
@jwt_required()
def export_events_report():
    """Export events data with detailed stats"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user or (user.role != UserRole.ADMIN and str(user.role) != 'ADMIN'):
            return jsonify({'error': 'Permission denied'}), 403
        
        events = Event.query.all()
        
        data = []
        for event in events:
            ticket_types = TicketTypeModel.query.filter_by(event_id=event.id).all()
            total_tickets = sum(tt.quantity for tt in ticket_types)
            sold_tickets = sum(tt.sold_quantity for tt in ticket_types)
            revenue = sum(tt.sold_quantity * tt.price for tt in ticket_types)
            
            # Get organizer name
            organizer = User.query.get(event.organizer_id)
            organizer_name = organizer.name if organizer else 'Unknown'
            
            # Get category name
            category = Category.query.get(event.category_id)
            category_name = category.name if category else 'Uncategorized'
            
            data.append({
                'id': event.id,
                'title': event.title,
                'status': event.status.value if hasattr(event.status, 'value') else event.status,
                'organizer_id': event.organizer_id,
                'organizer_name': organizer_name,
                'category_id': event.category_id,
                'category_name': category_name,
                'start_date': event.start_date.isoformat() if event.start_date else None,
                'end_date': event.end_date.isoformat() if event.end_date else None,
                'venue': event.venue or '',
                'city': event.city or '',
                'address': event.address or '',
                'total_tickets': total_tickets,
                'sold_tickets': sold_tickets,
                'revenue': float(revenue) if revenue else 0,
                'occupancy_rate': (sold_tickets / total_tickets * 100) if total_tickets > 0 else 0,
                'is_published': event.is_published,
                'view_count': event.view_count,
                'created_at': event.created_at.isoformat() if event.created_at else None
            })
        
        return jsonify({
            'events': data,
            'total': len(data),
            'generated_at': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@reports_bp.route('/users/export', methods=['GET'])
@jwt_required()
def export_users_report():
    """Export users data with detailed stats"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user or (user.role != UserRole.ADMIN and str(user.role) != 'ADMIN'):
            return jsonify({'error': 'Permission denied'}), 403
        
        users = User.query.all()
        
        data = []
        for u in users:
            user_tickets = Ticket.query.filter_by(user_id=u.id).all()
            total_spent = sum(float(t.total_price) for t in user_tickets if t.payment_status == 'COMPLETED')
            
            data.append({
                'id': u.id,
                'name': u.name,
                'email': u.email,
                'phone': u.phone or '',
                'role': u.role.value if hasattr(u.role, 'value') else u.role,
                'is_verified': u.is_verified,
                'is_active': u.is_active,
                'business_name': u.business_name or '',
                'created_at': u.created_at.isoformat() if u.created_at else None,
                'total_tickets': len(user_tickets),
                'total_spent': total_spent
            })
        
        return jsonify({
            'users': data,
            'total': len(data),
            'generated_at': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@reports_bp.route('/tickets/export', methods=['GET'])
@jwt_required()
def export_tickets_report():
    """Export tickets data as CSV"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if user.role not in [UserRole.ADMIN]:
            return jsonify({'error': 'Permission denied'}), 403
        
        tickets = Ticket.query.all()
        
        data = []
        for ticket in tickets:
            event = Event.query.get(ticket.event_id)
            ticket_type = TicketTypeModel.query.get(ticket.ticket_type_id)
            buyer = User.query.get(ticket.user_id)
            
            data.append({
                'id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'event': event.title if event else 'Unknown',
                'ticket_type': ticket_type.name if ticket_type else 'Unknown',
                'status': ticket.payment_status,
                'quantity': ticket.quantity,
                'total_price': ticket.total_price,
                'buyer_name': buyer.name if buyer else 'Unknown',
                'buyer_email': buyer.email if buyer else 'Unknown',
                'purchased_at': ticket.purchased_at.isoformat() if ticket.purchased_at else None,
                'mpesa_receipt': ticket.mpesa_receipt or ''
            })
        
        return jsonify({
            'tickets': data,
            'total': len(data),
            'generated_at': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def get_overview_stats(start_date=None, end_date=None):
    """Get platform overview statistics"""
    # Base queries
    users_count = User.query.count()
    events_count = Event.query.count()
    approved_events = Event.query.filter_by(status=EventStatus.APPROVED).count()
    tickets_count = Ticket.query.filter_by(payment_status='COMPLETED').count()
    
    # Revenue from completed transactions
    transactions = MpesaTransaction.query.filter_by(status='COMPLETED')
    if start_date:
        transactions = transactions.filter(MpesaTransaction.created_at >= start_date)
    if end_date:
        transactions = transactions.filter(MpesaTransaction.created_at <= end_date)
    
    total_revenue = sum(float(t.amount) for t in transactions.all())
    
    # Use PostgreSQL enum values (uppercase with PENDING_APPROVAL)
    pending_events = db.session.execute(
        text("SELECT COUNT(*) FROM events WHERE status IN ('DRAFT', 'PENDING_APPROVAL')")
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
    """Get revenue statistics"""
    transactions = MpesaTransaction.query.filter_by(status='COMPLETED')
    if start_date:
        transactions = transactions.filter(MpesaTransaction.created_at >= start_date)
    if end_date:
        transactions = transactions.filter(MpesaTransaction.created_at <= end_date)
    
    all_transactions = transactions.all()
    total_revenue = sum(float(t.amount) for t in all_transactions)
    
    # Daily breakdown
    daily_revenue = {}
    for t in all_transactions:
        date_key = t.created_at.strftime('%Y-%m-%d')
        if date_key not in daily_revenue:
            daily_revenue[date_key] = 0
        daily_revenue[date_key] += float(t.amount)
    
    transaction_count = len(all_transactions)
    avg_transaction = total_revenue / transaction_count if transaction_count > 0 else 0
    
    return {
        'total_revenue': total_revenue,
        'transaction_count': transaction_count,
        'average_transaction': avg_transaction,
        'daily_breakdown': daily_revenue
    }


def get_events_stats(start_date=None, end_date=None, filters=None):
    """Get events statistics"""
    query = Event.query
    if filters:
        query = query.filter_by(**filters)
    
    if start_date:
        query = query.filter(Event.start_date >= start_date)
    if end_date:
        query = query.filter(Event.start_date <= end_date)
    
    events = query.all()
    
    # Calculate per-event stats
    event_stats = []
    for event in events:
        ticket_types = TicketTypeModel.query.filter_by(event_id=event.id).all()
        total_tickets = sum(tt.quantity for tt in ticket_types)
        sold_tickets = sum(tt.sold_quantity for tt in ticket_types)
        revenue = sum(tt.sold_quantity * float(tt.price) for tt in ticket_types)
        
        event_stats.append({
            'id': event.id,
            'title': event.title,
            'status': event.status.value if hasattr(event.status, 'value') else event.status,
            'total_tickets': total_tickets,
            'sold_tickets': sold_tickets,
            'revenue': revenue,
            'occupancy_rate': (sold_tickets / total_tickets * 100) if total_tickets > 0 else 0
        })
    
    return {
        'total_events': len(events),
        'event_details': event_stats,
        'total_tickets_sold': sum(e['sold_tickets'] for e in event_stats),
        'total_revenue': sum(e['revenue'] for e in event_stats)
    }


def get_users_stats(start_date=None, end_date=None):
    """Get user statistics"""
    users = User.query.all()
    
    # Role distribution
    role_distribution = {}
    for user in users:
        role = user.role.value if hasattr(user.role, 'value') else user.role
        role_distribution[role] = role_distribution.get(role, 0) + 1
    
    # Activity stats
    active_users = len(set(t.user_id for t in Ticket.query.filter_by(payment_status='COMPLETED').all()))
    
    # Registration over time (simplified)
    registrations_by_month = {}
    for user in users:
        if user.created_at:
            month_key = user.created_at.strftime('%Y-%m')
            registrations_by_month[month_key] = registrations_by_month.get(month_key, 0) + 1
    
    users_count = len(users)
    verified_count = User.query.filter_by(is_verified=True).count()
    verification_rate = (verified_count / users_count * 100) if users_count > 0 else 0
    
    return {
        'total_users': users_count,
        'role_distribution': role_distribution,
        'active_users': active_users,
        'registrations_by_month': registrations_by_month,
        'verification_rate': verification_rate
    }


def get_recent_reports():
    """Get list of recently generated reports"""
    # This would typically be stored in a database table
    # For now, return empty list
    return []
