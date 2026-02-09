"""
Moderation Routes - Event Approval/Rejection
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from jwt.exceptions import ExpiredSignatureError
from datetime import datetime
import logging

from extensions import db
from models import User, UserRole, Event, EventStatus
from services.email_service import (
    send_event_approval_email,
    send_event_rejection_email
)

logger = logging.getLogger(__name__)

moderation_bp = Blueprint('moderation', __name__)
