"""
PDF Ticket Generation Service
Generates PDF tickets with QR codes for event entry
"""

import io
import os
import qrcode
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    HRFlowable,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

def generate_ticket_pdf_buffer(ticket, event, ticket_type, user=None):
    """Generate a PDF ticket and return as BytesIO buffer"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    elements = []
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=28,
        textColor=colors.HexColor("#1E0A3C"),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    )

    event_title_style = ParagraphStyle(
        "EventTitle",
        parent=styles["Heading2"],
        fontSize=22,
        textColor=colors.HexColor("#F05537"),
        spaceAfter=10,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    )

    label_style = ParagraphStyle(
        "LabelStyle",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#6F7287"),
        spaceAfter=2,
    )

    value_style = ParagraphStyle(
        "ValueStyle",
        parent=styles["Normal"],
        fontSize=14,
        textColor=colors.HexColor("#1E0A3C"),
        spaceAfter=12,
        fontName="Helvetica-Bold",
    )

    ticket_number_style = ParagraphStyle(
        "TicketNumber",
        parent=styles["Normal"],
        fontSize=18,
        textColor=colors.HexColor("#F05537"),
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    )

    # Header
    elements.append(Paragraph("EVENTHUB", title_style))
    elements.append(Spacer(1, 10))
    elements.append(
        HRFlowable(width="100%", thickness=2, color=colors.HexColor("#F05537"))
    )
    elements.append(Spacer(1, 20))

    # Event Title
    elements.append(Paragraph(event.title, event_title_style))
    elements.append(Spacer(1, 20))

    # Generate QR Code
    qr_data = ticket.qr_data or ticket.ticket_number
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(str(qr_data))
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="#1E0A3C", back_color="white")
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    qr_image = Image(qr_buffer, width=2 * inch, height=2 * inch)

    # Ticket info table
    ticket_info_data = [
        [
            Paragraph("TICKET NUMBER", label_style),
            Paragraph("TICKET TYPE", label_style),
        ],
        [
            Paragraph(ticket.ticket_number, ticket_number_style),
            Paragraph(ticket_type.name, value_style),
        ],
    ]

    ticket_info_table = Table(ticket_info_data, colWidths=[3 * inch, 3 * inch])
    ticket_info_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )

    qr_and_info = Table(
        [[qr_image, ticket_info_table]], colWidths=[2.5 * inch, 4 * inch]
    )
    qr_and_info.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )

    elements.append(qr_and_info)
    elements.append(Spacer(1, 20))
    elements.append(
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E5E5E5"))
    )
    elements.append(Spacer(1, 20))
