"""
Tickets Routes
"""

from flask import Blueprint, request, jsonify, send_file, make_response
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from datetime import datetime
from sqlalchemy import and_, or_
import io
import base64
import qrcode
import secrets
import uuid
import hmac
import hashlib
import logging
import os
from extensions import db

logger = logging.getLogger(__name__)
from models import (
    Ticket,
    TicketTypeModel,
    Event,
    User,
    UserRole,
    MpesaTransaction,
    EventStatus,
)
from services.pdf_service import generate_ticket_pdf
from services.email_service import send_ticket_with_pdf


# Secret key for signing QR codes (loaded from environment or use stable fallback)
QR_SIGNING_KEY = os.environ.get(
    "QR_SIGNING_KEY", b"event-hub-qr-secret-key-32bytes!"
).encode()
