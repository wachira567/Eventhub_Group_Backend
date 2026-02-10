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


def send_ticket_with_pdf(user_email, user_name, event_title, ticket_number, quantity, total_price, pdf_buffer, filename=None):
    """
    Send ticket confirmation email with PDF attachment
    """
    try:
        msg = Message(
            subject=f'Your Ticket for {event_title}',
            sender=os.environ.get('MAIL_USERNAME'),
            recipients=[user_email]
        )
        
        msg.html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #F05537; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 8px 8px; }}
                .ticket-info {{ background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #F05537; }}
                .ticket-number {{ font-size: 24px; font-weight: bold; color: #F05537; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
                .btn {{ display: inline-block; background: #F05537; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Your Ticket is Confirmed!</h1>
                </div>
                <div class="content">
                    <p>Hi {user_name},</p>
                    <p>Thank you for purchasing tickets for <strong>{event_title}</strong>!</p>
                    
                    <div class="ticket-info">
                        <p style="margin: 0; color: #666;">Ticket Number</p>
                        <p class="ticket-number">{ticket_number}</p>
                        
                        <table style="width: 100%; margin-top: 15px;">
                            <tr>
                                <td style="color: #666;">Quantity:</td>
                                <td style="font-weight: bold;">{quantity}</td>
                            </tr>
                            <tr>
                                <td style="color: #666;">Total Paid:</td>
                                <td style="font-weight: bold;">KES {total_price:,.2f}</td>
                            </tr>
                        </table>
                    </div>
                    
                    <p>Your ticket PDF is attached to this email. Please save it and present it at the event entrance for scanning.</p>
                    
                    <p><strong>Important:</strong></p>
                    <ul>
                        <li>Each ticket has a unique QR code for verification</li>
                        <li>Tickets are non-transferable and can only be used once</li>
                        <li>Please arrive early to allow time for check-in</li>
                    </ul>
                    
                    <p>We look forward to seeing you there!</p>
                    
                    <div class="footer">
                        <p>Need help? Contact us at support@eventhub.com</p>
                        <p>&copy; 2026 EventHub. All rights reserved.</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Attach PDF
        if pdf_buffer:
            from extensions import mail
            from io import BytesIO
            
            # Handle both bytes and BytesIO buffers
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
            
            mail.send(msg)
            print(f"Ticket email sent successfully to {user_email}")
        return True
    except Exception as e:
        print(f"Email error: {e}")
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
        from extensions import mail
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
        print(f"Email error: {e}")
        return False


def send_event_reminder(user_email, user_name, event_title, event_date, event_location):
    """Send event reminder email"""
    try:
        from extensions import mail
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
        print(f"Email error: {e}")
        return False


def send_event_approval_email(user_email, user_name, event_title, notes=None):
    """Send event approval notification"""
    try:
        from extensions import mail
        frontend_url = os.environ.get('FRONTEND_URL', 'http://localhost:5173')
        
        msg = Message(
            subject=f'🎉 Your Event "{event_title}" Has Been Approved!',
            sender=os.environ.get('MAIL_USERNAME'),
            recipients=[user_email]
        )
        
        notes_section = f"""<div style="background: #f0f0f0; padding: 15px; border-radius: 8px; margin: 20px 0;">
            <p style="margin: 0; color: #666;"><strong>Moderator Notes:</strong></p>
            <p style="margin: 10px 0 0;">{notes}</p>
        </div>""" if notes else """
        <p style="margin-top: 20px;">Your event is ready to be published and will be visible to attendees!</p>
        """
        
        msg.html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #10B981; color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 8px 8px; }}
                .button {{ display: inline-block; background: #10B981; color: white; padding: 15px 30px; 
                          text-decoration: none; border-radius: 4px; margin: 20px 0; font-weight: bold; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>✅ Event Approved!</h1>
                </div>
                <div class="content">
                    <p>Hi {user_name},</p>
                    <p>Great news! Your event <strong>"{event_title}"</strong> has been approved by our moderation team.</p>
                    {notes_section}
                    <p>You can now publish your event and start selling tickets!</p>
                    <center>
                        <a href="{frontend_url}/organizer/events" class="button">Manage Your Event</a>
                    </center>
                    <div class="footer">
                        <p>Need help? Contact us at support@eventhub.com</p>
                        <p>&copy; 2026 EventHub. All rights reserved.</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


def send_event_rejection_email(user_email, user_name, event_title, reason):
    """Send event rejection notification"""
    try:
        from extensions import mail
        frontend_url = os.environ.get('FRONTEND_URL', 'http://localhost:5173')
        
        msg = Message(
            subject=f'Event Update: "{event_title}" Needs Changes',
            sender=os.environ.get('MAIL_USERNAME'),
            recipients=[user_email]
        )
        
        msg.html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #F05537; color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
                .content {{ background: #f9f9f9; padding: 30px; border-radius: 0 0 8px 8px; }}
                .reason-box {{ background: #fef2f2; border: 1px solid #fecaca; padding: 20px; border-radius: 8px; margin: 20px 0; }}
                .button {{ display: inline-block; background: #F05537; color: white; padding: 15px 30px; 
                          text-decoration: none; border-radius: 4px; margin: 20px 0; font-weight: bold; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>⚠️ Action Required</h1>
                </div>
                <div class="content">
                    <p>Hi {user_name},</p>
                    <p>Thank you for submitting your event <strong>"{event_title}"</strong> for review.</p>
                    <p>Our moderation team has reviewed your submission and would like you to make some changes before it can be approved.</p>
                    
                    <div class="reason-box">
                        <p style="margin: 0 0 10px;"><strong>Please review the following:</strong></p>
                        <p style="margin: 0;">{reason}</p>
                    </div>
                    
                    <p>Please make the necessary changes and resubmit your event for review.</p>
                    <center>
                        <a href="{frontend_url}/organizer/events" class="button">Edit Your Event</a>
                    </center>
                    
                    <p style="margin-top: 20px;">If you have any questions about the feedback, please don't hesitate to contact us.</p>
                    
                    <div class="footer">
                        <p>Need help? Contact us at support@eventhub.com</p>
                        <p>&copy; 2026 EventHub. All rights reserved.</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False
