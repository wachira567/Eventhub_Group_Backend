"""
Email Service for notifications
"""

import os
from flask_mail import Message
from extensions import mail
from io import BytesIO


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
        
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Ticket confirmation email error: {e}")
        return False


def send_ticket_with_pdf(user_email, user_name, event_title, ticket_number, quantity, total_price, pdf_buffer, filename=None):
    """Send ticket confirmation email with PDF attachment"""
    try:
        msg = Message(
            subject=f'Your Ticket for {event_title}',
            sender=os.environ.get('MAIL_USERNAME'),
            recipients=[user_email]
        )
        
        msg.html = f"""..."""  # Keep same styled HTML from Step 4
        
        # Attach PDF safely
        if pdf_buffer:
            try:
                if isinstance(pdf_buffer, bytes):
                    pdf_data = pdf_buffer
                else:
                    pdf_buffer.seek(0)
                    pdf_data = pdf_buffer.read()
                attachment_filename = filename or f"ticket_{ticket_number}.pdf"
                msg.attach(
                    filename=attachment_filename,
                    content_type='application/pdf',
                    data=pdf_data
                )
            except Exception as e_attach:
                print(f"PDF attachment error: {e_attach}")
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Ticket email error: {e}")
        return False


def send_guest_ticket_confirmation(guest_email, guest_name, event_title, ticket_number, quantity, total_price, pdf_buffer):
    """Send ticket confirmation to guest user"""
    return send_ticket_with_pdf(
        user_email=guest_email,
        user_name=guest_name or 'Guest',
        event_title=event_title,
        ticket_number=ticket_number,
        quantity=quantity,
        total_price=total_price,
        pdf_buffer=pdf_buffer,
        filename=f"EventHub_Ticket_{ticket_number}.pdf"
    )


def send_event_approval_notification(user_email, user_name, event_title, status, reason=None):
    """Send event approval/rejection notification"""
    try:
        subject = f'Event {"Approved" if status == "published" else "Rejected"} - {event_title}'
        msg = Message(
            subject=subject,
            sender=os.environ.get('MAIL_USERNAME'),
            recipients=[user_email]
        )
        status_text = "has been approved and is now live!" if status == "published" else "has been rejected"
        reason_text = f"<p><strong>Reason:</strong> {reason}</p>" if reason else ""
        msg.html = f"""
        <h1>Event Update</h1>
        <p>Hi {user_name},</p>
        <p>Your event <strong>{event_title}</strong> {status_text}</p>
        {reason_text}
        <p>Thank you for using EventHub!</p>
        """
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Event approval notification error: {e}")
        return False


def send_event_reminder(user_email, user_name, event_title, event_date, event_location):
    """Send event reminder email"""
    try:
        msg = Message(
            subject=f'Reminder: {event_title} is coming up!',
            sender=os.environ.get('MAIL_USERNAME'),
            recipients=[user_email]
        )
        msg.html = f"""
        <h1>Event Reminder</h1>
        <p>Hi {user_name},</p>
        <p>Don't forget! <strong>{event_title}</strong> is happening soon.</p>
        <ul>
            <li><strong>Date:</strong> {event_date}</li>
            <li><strong>Location:</strong> {event_location}</li>
        </ul>
        <p>See you there!</p>
        """
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Event reminder email error: {e}")
        return False


def send_event_approval_email(user_email, user_name, event_title, notes=None):
    """Send event approval notification with frontend link"""
    try:
        frontend_url = os.environ.get('FRONTEND_URL', 'http://localhost:5173')
        msg = Message(
            subject=f'🎉 Your Event "{event_title}" Has Been Approved!',
            sender=os.environ.get('MAIL_USERNAME'),
            recipients=[user_email]
        )
        notes_section = f"""<div style="background: #f0f0f0; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <p style="margin: 0; color: #666;"><strong>Moderator Notes:</strong></p>
            <p style="margin: 10px 0 0;">{notes}</p>
        </div>""" if notes else "<p style='margin-top: 20px;'>Your event is ready to be published!</p>"
        msg.html = f"""..."""  # Keep styled HTML as in Step 5
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Event approval email error: {e}")
        return False


def send_event_rejection_email(user_email, user_name, event_title, reason):
    """Send event rejection notification with frontend link"""
    try:
        frontend_url = os.environ.get('FRONTEND_URL', 'http://localhost:5173')
        msg = Message(
            subject=f'Event Update: "{event_title}" Needs Changes',
            sender=os.environ.get('MAIL_USERNAME'),
            recipients=[user_email]
        )
        msg.html = f"""..."""  # Keep styled HTML as in Step 5
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Event rejection email error: {e}")
        return False
