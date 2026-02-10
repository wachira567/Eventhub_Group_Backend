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
