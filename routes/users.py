"""
Users Routes - Admin User Management
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from datetime import datetime
from sqlalchemy import or_

from extensions import db
from models import User, UserRole, Event, Ticket

users_bp = Blueprint('users', __name__)
