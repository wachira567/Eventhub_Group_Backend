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
