from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity
)
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from utils import send_email
from models.user import User
from models.organizer_profile import OrganizerProfile
from extensions import db

auth_bp = Blueprint("auth", __name__)

