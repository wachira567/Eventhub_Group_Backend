"""
Export Routes - CSV/PDF Exports
"""

from flask import Blueprint, request, jsonify, send_file
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from io import StringIO, BytesIO
import csv
from extensions import db
from models import User, UserRole, Event, Ticket, TicketTypeModel
from services.pdf_service import generate_tickets_pdf


export_bp = Blueprint('export', __name__)


@jwt_required()
@export_bp.route('/event/<int:event_id>/tickets/csv', methods=['GET'])
def export_event_tickets_csv(event_id):
    """Export event tickets as CSV"""
    try:
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        
        event = Event.query.get_or_404(event_id)
        
        if user.role not in [UserRole.ADMIN, UserRole.ORGANIZER]:
            return jsonify({'error': 'Permission denied'}), 403
        
        if user.role == UserRole.ORGANIZER and event.organizer_id != user.id:
            return jsonify({'error': 'You can only export tickets for your own events'}), 403
        
        tickets = Ticket.query.filter_by(event_id=event_id).all()
        
        output = StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            'Ticket Code', 'Ticket Type', 'Status', 'Purchased By',
            'Email', 'Phone', 'Purchase Date', 'Used At'
        ])
        
        for ticket in tickets:
            ticket_buyer = User.query.get(ticket.user_id)
            ticket_type = TicketTypeModel.query.get(ticket.ticket_type_id)
            
            writer.writerow([
                ticket.ticket_code,
                ticket_type.name if ticket_type else 'N/A',
                ticket.status.value,
                ticket_buyer.name if ticket_buyer else 'N/A',
                ticket_buyer.email if ticket_buyer else 'N/A',
                ticket_buyer.phone if ticket_buyer else 'N/A',
                ticket.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                ticket.used_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.used_at else 'Not used'
            ])
        
        output.seek(0)
        
        return send_file(
            BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'event-{event_id}-tickets-{datetime.utcnow().strftime("%Y-%m-%d")}.csv'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@jwt_required()
@export_bp.route('/event/<int:event_id>/attendees/csv', methods=['GET'])
def export_event_attendees_csv(event_id):
    """Export event attendees as CSV"""
    try:
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        
        event = Event.query.get_or_404(event_id)
        
        if user.role not in [UserRole.ADMIN, UserRole.ORGANIZER]:
            return jsonify({'error': 'Permission denied'}), 403
        
        if user.role == UserRole.ORGANIZER and event.organizer_id != user.id:
            return jsonify({'error': 'You can only export attendees for your own events'}), 403
        
        tickets = Ticket.query.filter_by(event_id=event_id).all()
        attendees = {}
        
        for ticket in tickets:
            if ticket.user_id not in attendees:
                ticket_buyer = User.query.get(ticket.user_id)
                ticket_type = TicketTypeModel.query.get(ticket.ticket_type_id)
                attendees[ticket.user_id] = {
                    'name': ticket_buyer.name if ticket_buyer else 'N/A',
                    'email': ticket_buyer.email if ticket_buyer else 'N/A',
                    'phone': ticket_buyer.phone if ticket_buyer else 'N/A',
                    'ticket_types': set(),
                    'total_tickets': 0,
                    'checked_in': ticket.status.value == 'used'
                }
            attendees[ticket.user_id]['ticket_types'].add(
                ticket_type.name if ticket_type else 'N/A'
            )
            attendees[ticket.user_id]['total_tickets'] += 1
        
        output = StringIO()
        writer = csv.writer(output)
        
        writer.writerow([
            'Name', 'Email', 'Phone', 'Ticket Types', 'Total Tickets', 'Checked In'
        ])
        
        for attendee in attendees.values():
            writer.writerow([
                attendee['name'],
                attendee['email'],
                attendee['phone'],
                ', '.join(attendee['ticket_types']),
                attendee['total_tickets'],
                'Yes' if attendee['checked_in'] else 'No'
            ])
        
        output.seek(0)
        
        return send_file(
            BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'event-{event_id}-attendees-{datetime.utcnow().strftime("%Y-%m-%d")}.csv'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@jwt_required()
@export_bp.route('/event/<int:event_id>/tickets/pdf', methods=['GET'])
def export_event_tickets_pdf(event_id):
    """Export event tickets as PDF"""
    try:
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        
        event = Event.query.get_or_404(event_id)
        
        if user.role not in [UserRole.ADMIN, UserRole.ORGANIZER]:
            return jsonify({'error': 'Permission denied'}), 403
        
        if user.role == UserRole.ORGANIZER and event.organizer_id != user.id:
            return jsonify({'error': 'You can only export tickets for your own events'}), 403
        
        tickets = Ticket.query.filter_by(event_id=event_id).all()
        
        pdf_data = generate_tickets_pdf(event, tickets)
        
        return send_file(
            BytesIO(pdf_data),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'event-{event_id}-tickets-{datetime.utcnow().strftime("%Y-%m-%d")}.pdf'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@jwt_required()
@export_bp.route('/my-tickets/<int:event_id>/pdf', methods=['GET'])
def export_my_tickets_pdf(event_id):
    """Export user's tickets for an event as PDF"""
    try:
        user_id = int(get_jwt_identity())
        user = User.query.get(user_id)
        
        event = Event.query.get_or_404(event_id)
        
        tickets = Ticket.query.filter_by(
            event_id=event_id,
            user_id=user_id
        ).all()
        
        if not tickets:
            return jsonify({'error': 'No tickets found'}), 404
        
        pdf_data = generate_tickets_pdf(event, tickets, user)
        
        return send_file(
            BytesIO(pdf_data),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'my-tickets-{event_id}-{datetime.utcnow().strftime("%Y-%m-%d")}.pdf'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
