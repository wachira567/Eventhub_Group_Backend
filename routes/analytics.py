"""
Analytics Routes - Platform and Organizer Analytics
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from datetime import datetime, timedelta
from sqlalchemy import func, and_
from extensions import db
from models import (
    User, UserRole, Event, Ticket, TicketTypeModel,
    MpesaTransaction, EventReview, SavedEvent
)
import logging

logger = logging.getLogger(__name__)


analytics_bp = Blueprint('analytics', __name__)


@jwt_required()
@analytics_bp.route('/platform', methods=['GET'])
def get_platform_analytics():
    """Get platform-wide analytics (admin only)"""
    try:
        # Explicitly verify JWT before getting identity
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if user.role != UserRole.ADMIN:
            return jsonify({'error': 'Admin access required'}), 403
        
        period = request.args.get('period', '30')
        days = int(period)
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        stats = {
            'period_days': days,
            'users': {
                'total': User.query.count(),
                'new': User.query.filter(User.created_at >= start_date).count(),
                'organizers': User.query.filter_by(role=UserRole.ORGANIZER).count(),
                'attendees': User.query.filter_by(role=UserRole.ATTENDEE).count()
            },
            'events': {
                'total': Event.query.count(),
                'published': Event.query.filter_by(is_published=True).count(),
                'pending': Event.query.filter_by(is_published=False).count(),
                'new': Event.query.filter(Event.created_at >= start_date).count()
            },
            'tickets': {
                'total_sold': Ticket.query.count(),
                'total_valid': Ticket.query.filter(Ticket.payment_status.in_(['COMPLETED', 'PROCESSING'])).count(),
                'total_used': Ticket.query.filter_by(is_used=True).count()
            },
            'revenue': {
                'total': db.session.query(func.sum(MpesaTransaction.amount)).filter_by(status='COMPLETED').scalar() or 0,
                'period': db.session.query(func.sum(MpesaTransaction.amount)).filter(
                    MpesaTransaction.status == 'COMPLETED',
                    MpesaTransaction.created_at >= start_date
                ).scalar() or 0
            },
            'reviews': {
                'total': EventReview.query.count(),
                'average_rating': db.session.query(func.avg(EventReview.rating)).scalar() or 0
            }
        }
        
        return jsonify({'stats': stats}), 200
        
    except Exception as e:
        logger.error(f'Platform analytics error: {str(e)}', exc_info=True)
        return jsonify({'error': str(e)}), 500


@jwt_required()
@analytics_bp.route('/organizer', methods=['GET'])
def get_organizer_analytics():
    """Get analytics for current organizer"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if user.role not in [UserRole.ADMIN, UserRole.ORGANIZER]:
            return jsonify({'error': 'Organizer access required'}), 403
        
        period = request.args.get('period', '30')
        days = int(period)
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = Event.query
        if user.role == UserRole.ORGANIZER:
            query = query.filter_by(organizer_id=user.id)
        
        events = query.all()
        event_ids = [e.id for e in events]
        
        tickets_query = Ticket.query.filter(Ticket.event_id.in_(event_ids))
        transactions_query = MpesaTransaction.query.filter(
            MpesaTransaction.event_id.in_(event_ids),
            MpesaTransaction.status == 'COMPLETED'
        )
        
        stats = {
            'period_days': days,
            'events': {
                'total': len(events),
                'published': sum(1 for e in events if e.is_published),
                'draft': sum(1 for e in events if not e.is_published),
                'upcoming': sum(1 for e in events if e.start_date > datetime.utcnow()),
                'ongoing': sum(1 for e in events if e.start_date <= datetime.utcnow() <= e.end_date),
                'past': sum(1 for e in events if e.end_date < datetime.utcnow())
            },
            'tickets': {
                'total_sold': tickets_query.count(),
                'total_revenue': transactions_query.with_entities(func.sum(MpesaTransaction.amount)).scalar() or 0
            },
            'views': {
                'total': sum(e.view_count for e in events)
            }
        }
        
        event_stats = []
        for event in events:
            event_data = {
                'id': event.id,
                'title': event.title,
                'tickets_sold': Ticket.query.filter_by(event_id=event.id).count(),
                'revenue': db.session.query(func.sum(MpesaTransaction.amount)).filter(
                    MpesaTransaction.event_id == event.id,
                    MpesaTransaction.status == 'COMPLETED'
                ).scalar() or 0,
                'views': event.view_count,
                'reviews_count': EventReview.query.filter_by(event_id=event.id).count(),
                'average_rating': db.session.query(func.avg(EventReview.rating)).filter(
                    EventReview.event_id == event.id
                ).scalar() or 0
            }
            event_stats.append(event_data)
        
        stats['event_breakdown'] = event_stats
        
        return jsonify({'stats': stats}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/event/<int:event_id>', methods=['GET'])
def get_event_analytics(event_id):
    """Get analytics for a specific event"""
    try:
        # Manually verify JWT token
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        event = Event.query.get_or_404(event_id)
        
        if user.role not in [UserRole.ADMIN, UserRole.ORGANIZER]:
            return jsonify({'error': 'Permission denied'}), 403
        
        if user.role == UserRole.ORGANIZER and event.organizer_id != user.id:
            return jsonify({'error': 'You can only view analytics for your own events'}), 403
        
        ticket_types = TicketTypeModel.query.filter_by(event_id=event_id).all()
        
        tickets_by_type = []
        for tt in ticket_types:
            tickets = Ticket.query.filter_by(ticket_type_id=tt.id).all()
            tickets_by_type.append({
                'id': tt.id,
                'name': tt.name,
                'price': float(tt.price) if tt.price else 0,
                'quantity': tt.quantity or 0,
                'sold': tt.sold_quantity or 0,
                'revenue': (tt.sold_quantity or 0) * (float(tt.price) if tt.price else 0)
            })
        
        stats = {
            'event': {
                'id': event.id,
                'title': event.title,
                'image_url': event.image_url,
                'start_date': event.start_date.isoformat() if event.start_date else None,
                'views': event.view_count or 0
            },
            'tickets': {
                'total_available': sum(tt.quantity or 0 for tt in ticket_types),
                'total_sold': sum(tt.sold_quantity or 0 for tt in ticket_types),
                'total_revenue': sum((tt.sold_quantity or 0) * (float(tt.price) if tt.price else 0) for tt in ticket_types),
                'by_type': tickets_by_type
            },
            'sales': {
                'total': Ticket.query.filter_by(event_id=event_id).count(),
                'valid': Ticket.query.filter_by(event_id=event_id, payment_status='COMPLETED').count(),
                'used': Ticket.query.filter_by(event_id=event_id, is_used=True).count(),
                'cancelled': Ticket.query.filter_by(event_id=event_id, payment_status='FAILED').count()
            },
            'reviews': {
                'count': EventReview.query.filter_by(event_id=event_id).count(),
                'average_rating': db.session.query(func.avg(EventReview.rating)).filter(
                    EventReview.event_id == event_id
                ).scalar() or 0
            },
            'saves': {
                'total': SavedEvent.query.filter_by(event_id=event_id).count()
            }
        }
        
        return jsonify({'stats': stats}), 200
        
    except Exception as e:
        logger.error(f'Event analytics error for event {event_id}: {str(e)}', exc_info=True)
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/event/<int:event_id>/sales-timeline', methods=['GET'])
def get_sales_timeline(event_id):
    """Get ticket sales timeline for an event"""
    try:
        # Manually verify JWT token
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        event = Event.query.get_or_404(event_id)
        
        if user.role not in [UserRole.ADMIN, UserRole.ORGANIZER]:
            return jsonify({'error': 'Permission denied'}), 403
        
        if user.role == UserRole.ORGANIZER and event.organizer_id != user.id:
            return jsonify({'error': 'You can only view analytics for your own events'}), 403
        
        period = request.args.get('period', '7')
        days = int(period)
        start_date = datetime.utcnow() - timedelta(days=days)
        
        daily_sales = db.session.query(
            func.date(Ticket.purchased_at).label('date'),
            func.count(Ticket.id).label('count'),
            func.sum(TicketTypeModel.price).label('revenue')
        ).join(TicketTypeModel).filter(
            Ticket.event_id == event_id,
            Ticket.purchased_at >= start_date
        ).group_by(func.date(Ticket.purchased_at)).all()
        
        timeline = []
        for sale in daily_sales:
            timeline.append({
                'date': str(sale.date),
                'tickets_sold': sale.count,
                'revenue': float(sale.revenue or 0)
            })
        
        return jsonify({'timeline': timeline}), 200
        
    except Exception as e:
        logger.error(f'Sales timeline error for event {event_id}: {str(e)}', exc_info=True)
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/event/<int:event_id>/attendees', methods=['GET'])
def get_event_attendees(event_id):
    """Get attendees for a specific event with check-in status"""
    try:
        # Manually verify JWT token
        verify_jwt_in_request()
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        event = Event.query.get_or_404(event_id)
        
        if user.role not in [UserRole.ADMIN, UserRole.ORGANIZER]:
            return jsonify({'error': 'Permission denied'}), 403
        
        if user.role == UserRole.ORGANIZER and event.organizer_id != user.id:
            return jsonify({'error': 'You can only view attendees for your own events'}), 403
        
        # Get all tickets for this event with full details
        tickets = Ticket.query.filter_by(event_id=event_id).all()
        
        attendees_list = []
        
        for ticket in tickets:
            ticket_type = TicketTypeModel.query.get(ticket.ticket_type_id)
            
            # Determine name and email (user or guest)
            if ticket.is_guest:
                name = ticket.guest_name or 'Guest'
                email = ticket.guest_email or 'N/A'
            elif ticket.user_id:
                ticket_user = User.query.get(ticket.user_id)
                name = ticket_user.name if ticket_user else 'Unknown'
                email = ticket_user.email if ticket_user else 'N/A'
            else:
                name = 'Unknown'
                email = 'N/A'
            
            # Check-in status
            is_checked_in = ticket.is_used
            checked_in_at = ticket.used_at.isoformat() if ticket.used_at else None
            verified_by_user = None
            if ticket.verified_by:
                verifier = User.query.get(ticket.verified_by)
                verified_by_user = verifier.name if verifier else 'Staff'
            
            attendees_list.append({
                'id': ticket.id,
                'ticket_id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'user_name': name,
                'user_email': email,
                'ticket_type': ticket_type.name if ticket_type else 'Unknown',
                'ticket_type_id': ticket.ticket_type_id,
                'quantity': ticket.quantity,
                'total_price': float(ticket.total_price) if ticket.total_price else 0,
                'payment_status': ticket.payment_status,
                'is_guest': ticket.is_guest,
                'is_checked_in': is_checked_in,
                'checked_in_at': checked_in_at,
                'verified_by': verified_by_user,
                'purchased_at': ticket.purchased_at.isoformat() if ticket.purchased_at else None,
                'mpesa_receipt': ticket.mpesa_receipt
            })
        
        # Sort by purchase date (newest first)
        attendees_list.sort(key=lambda x: x['purchased_at'] or '', reverse=True)
        
        return jsonify({
            'attendees': attendees_list,
            'total': len(attendees_list),
            'stats': {
                'total_tickets': sum(a['quantity'] for a in attendees_list),
                'checked_in': sum(1 for a in attendees_list if a['is_checked_in']),
                'pending': sum(1 for a in attendees_list if not a['is_checked_in'] and a['payment_status'] == 'COMPLETED'),
                'total_revenue': sum(a['total_price'] for a in attendees_list if a['payment_status'] == 'COMPLETED')
            }
        }), 200
        
    except Exception as e:
        logger.error(f'Event attendees error for event {event_id}: {str(e)}', exc_info=True)
        return jsonify({'error': str(e)}), 500