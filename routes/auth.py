# [Commits 1–3 code remains unchanged]
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

# Email token utilities
def generate_verification_token(email):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return serializer.dumps(email, salt="email-confirmation-salt")

def confirm_verification_token(token, expiration=3600):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        return serializer.loads(token, salt="email-confirmation-salt", max_age=expiration)
    except (SignatureExpired, BadSignature):
        return None

def send_verification_email(user):
    token = generate_verification_token(user.email)
    verify_url = f"{current_app.config['FRONTEND_URL']}/verify-email?token={token}"
    send_email(
        to=user.email,
        subject="Verify Your Email",
        html=f"<p>Hello {user.name}, click the link to verify your email:</p>"
             f"<a href='{verify_url}'>Verify Email</a>"
    )

def send_password_reset_email(user):
    token = generate_verification_token(user.email)
    reset_url = f"{current_app.config['FRONTEND_URL']}/reset-password?token={token}"
    send_email(
        to=user.email,
        subject="Reset Your Password",
        html=f"<p>Hello {user.name}, click the link to reset your password:</p>"
             f"<a href='{reset_url}'>Reset Password</a>"
    )

# Register endpoint
@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.json
    name = data.get("name")
    email = data.get("email")
    phone = data.get("phone")
    password = data.get("password")

    if not all([name, email, phone, password]):
        return jsonify({"error": "All fields are required"}), 400

    existing = User.query.filter_by(email=email).first()

    if existing and not existing.is_verified:
        send_verification_email(existing)
        return jsonify({"message": "Account exists but is not verified. Verification email resent."}), 200

    if existing:
        return jsonify({"error": "Email already in use"}), 409

    hashed_password = generate_password_hash(password)
    new_user = User(name=name, email=email, phone=phone, password=hashed_password)

    db.session.add(new_user)
    db.session.commit()

    send_verification_email(new_user)

    return jsonify({"message": "Account created. Please verify your email."}), 201

# --------------------------
# Verify Email
# --------------------------
@auth_bp.route("/verify-email", methods=["POST"])
def verify_email():
    token = request.json.get("token")
    email = confirm_verification_token(token)

    if not email:
        return jsonify({"error": "Invalid or expired token"}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    user.is_verified = True
    db.session.commit()

    return jsonify({"message": "Email verified successfully"}), 200
