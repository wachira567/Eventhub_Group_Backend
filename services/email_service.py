"""
Email Service for notifications
"""

import os
from flask_mail import Message


def send_ticket_confirmation(user_email, user_name, event_title, ticket_number, quantity, total_price):
    """Send ticket confirmation email (legacy, without PDF)"""
    try:
        msg = Message(
            subject=f'Ticket Confirmed - {event_title}',
            sender=os.environ.get('MAIL_USERNAME'),
            recipients=[user_email]
        )
        
        msg.html = f"""
        <h1>Ticket Confirmed!</h1>
        <p>Hi {user_name},</p>
        <p>Your tickets for <strong>{event_title}</strong> have been confirmed.</p>
        <ul>
            <li><strong>Ticket Number:</strong> {ticket_number}</li>
            <li><strong>Quantity:</strong> {quantity}</li>
            <li><strong>Total Paid:</strong> KES {total_price}</li>
        </ul>
        <p>Please present this ticket number at the event entrance.</p>
        <p>Thank you for using EventHub!</p>
        """
        
        from extensions import mail
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False
