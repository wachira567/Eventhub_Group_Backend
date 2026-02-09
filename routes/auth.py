"""
Authentication Routes
"""

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt,
)
from datetime import datetime, timedelta
from extensions import db, mail
from models import User, UserRole
from email_validator import validate_email, EmailNotValidError
import phonenumbers
from phonenumbers import PhoneNumberFormat as PNF
import secrets
from flask_mail import Message


auth_bp = Blueprint("auth", __name__)


def generate_verification_token():
    """Generate a secure random token for email verification"""
    return secrets.token_urlsafe(32)


def send_verification_email(user_email, user_name, verification_token):
    """Send email verification magic link"""
    try:
        frontend_url = current_app.config.get("FRONTEND_URL", "http://localhost:5173")
        verification_url = f"{frontend_url}/verify-email?token={verification_token}"

        msg = Message(
            subject="Verify Your Email - EventHub",
            sender=current_app.config.get("MAIL_USERNAME"),
            recipients=[user_email],
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
                .button {{ display: inline-block; background: #F05537; color: white; padding: 15px 30px; 
                          text-decoration: none; border-radius: 4px; margin: 20px 0; font-weight: bold; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
                .link {{ color: #F05537; word-break: break-all; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 Welcome to EventHub!</h1>
                </div>
                <div class="content">
                    <p>Hi {user_name},</p>
                    <p>Thank you for signing up! Please verify your email address to complete your registration.</p>
                    <p>Click the button below to verify your email:</p>
                    <center>
                        <a href="{verification_url}" class="button">Verify My Email</a>
                    </center>
                    <p>Or copy and paste this link into your browser:</p>
                    <p class="link">{verification_url}</p>
                    <p><strong>This link will expire in 24 hours.</strong></p>
                    <p>If you didn't create an account with EventHub, you can safely ignore this email.</p>
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
        print(f"Verification email error: {e}")
        return False


@auth_bp.route("/register", methods=["POST"])
def register():
    """Register a new user"""
    try:
        data = request.get_json()

        email = data.get("email", "").strip().lower()
        password = data.get("password", "")
        name = data.get("name", "").strip()
        phone = data.get("phone", "").strip()
        role = data.get("role", "attendee")

        if not email or not password or not name:
            return jsonify({"error": "Email, password, and name are required"}), 400

        # Validate email
        try:
            valid_email = validate_email(email)
            email = valid_email.email
        except EmailNotValidError as e:
            return jsonify({"error": str(e)}), 400

        # Validate phone
        if phone:
            try:
                parsed_phone = phonenumbers.parse(phone, "KE")
                if not phonenumbers.is_valid_number(parsed_phone):
                    return jsonify({"error": "Invalid phone number"}), 400
                phone = phonenumbers.format_number(parsed_phone, PNF.E164)
            except:
                return jsonify({"error": "Invalid phone number format"}), 400

        # Check if user exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            if existing_user.is_verified:
                return jsonify(
                    {"error": "Email already registered. Please log in."}
                ), 400
            else:
                verification_token = generate_verification_token()
                existing_user.email_verification_token = verification_token
                existing_user.email_verification_expires = (
                    datetime.utcnow() + timedelta(hours=24)
                )
                db.session.commit()
                send_verification_email(
                    existing_user.email, existing_user.name, verification_token
                )
                return jsonify(
                    {
                        "message": "Verification email resent. Please check your email.",
                        "requiresVerification": True,
                    }
                ), 200

        if phone and User.query.filter_by(phone=phone).first():
            return jsonify({"error": "Phone number already registered"}), 400

        # Create user
        verification_token = generate_verification_token()
        user = User(
            email=email,
            name=name,
            phone=phone,
            role=UserRole(role),
            is_verified=False,
            email_verification_token=verification_token,
            email_verification_expires=datetime.utcnow() + timedelta(hours=24),
        )
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        send_verification_email(user.email, user.name, verification_token)

        return jsonify(
            {
                "message": "Registration successful! Please check your email to verify your account.",
                "requiresVerification": True,
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "is_verified": user.is_verified,
                },
            }
        ), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@auth_bp.route("/verify-email", methods=["GET", "POST"])
def verify_email():
    """Verify email using magic link token"""
    try:
        if request.method == "GET":
            token = request.args.get("token")
        else:
            data = request.get_json()
            token = data.get("token")

        if not token:
            return jsonify({"error": "Verification token is required"}), 400

        user = User.query.filter_by(email_verification_token=token).first()

        if not user:
            return jsonify({"error": "Invalid or expired verification token"}), 400

        if (
            user.email_verification_expires
            and user.email_verification_expires < datetime.utcnow()
        ):
            return jsonify({"error": "Verification token has expired"}), 400

        user.is_verified = True
        user.email_verification_token = None
        user.email_verification_expires = None
        db.session.commit()

        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))

        return jsonify(
            {
                "message": "Email verified successfully!",
                "user": user.to_dict(),
                "access_token": access_token,
                "refresh_token": refresh_token,
            }
        ), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@auth_bp.route("/login", methods=["POST"])
def login():
    """Login user"""
    try:
        data = request.get_json()
        email = data.get("email", "").strip().lower()
        password = data.get("password", "")

        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400

        user = User.query.filter_by(email=email).first()

        if not user:
            return jsonify(
                {
                    "error": "Account not found. Please check your email or sign up.",
                    "userNotFound": True,
                }
            ), 404

        if not user.check_password(password):
            return jsonify({"error": "Invalid password. Please try again."}), 401

        if not user.is_active:
            return jsonify({"error": "Account is deactivated"}), 403

        if not user.is_verified:
            verification_token = generate_verification_token()
            user.email_verification_token = verification_token
            user.email_verification_expires = datetime.utcnow() + timedelta(hours=24)
            db.session.commit()
            send_verification_email(user.email, user.name, verification_token)
            return jsonify(
                {
                    "error": "Please verify your email before logging in. A new verification link has been sent.",
                    "requiresVerification": True,
                    "email": user.email,
                }
            ), 403

        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))

        return jsonify(
            {
                "message": "Login successful",
                "user": user.to_dict(),
                "access_token": access_token,
                "refresh_token": refresh_token,
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh_token():
    """Refresh access token"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if not user:
            return jsonify({"error": "User not found"}), 404

        access_token = create_access_token(identity=str(user.id))

        return jsonify({"access_token": access_token}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def get_current_user():
    """Get current user profile"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if not user:
            return jsonify({"error": "User not found"}), 404

        return jsonify({"user": user.to_dict()}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    """Logout user"""
    return jsonify({"message": "Successfully logged out"}), 200


@auth_bp.route("/change-password", methods=["POST"])
@jwt_required()
def change_password():
    """Change user password"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        current_password = data.get("current_password", "")
        new_password = data.get("new_password", "")

        if not current_password or not new_password:
            return jsonify({"error": "Current and new password are required"}), 400

        user = User.query.get(user_id)

        if not user or not user.check_password(current_password):
            return jsonify({"error": "Current password is incorrect"}), 401

        user.set_password(new_password)
        db.session.commit()

        return jsonify({"message": "Password changed successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


def send_password_reset_email(user_email, user_name, reset_token):
    """Send password reset magic link"""
    try:
        frontend_url = current_app.config.get("FRONTEND_URL", "http://localhost:5173")
        reset_url = f"{frontend_url}/reset-password?token={reset_token}"

        msg = Message(
            subject="Reset Your Password - EventHub",
            sender=current_app.config.get("MAIL_USERNAME"),
            recipients=[user_email],
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
                .button {{ display: inline-block; background: #F05537; color: white; padding: 15px 30px; 
                          text-decoration: none; border-radius: 4px; margin: 20px 0; font-weight: bold; }}
                .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
                .link {{ color: #F05537; word-break: break-all; }}
                .warning {{ background: #fff3cd; border: 1px solid #ffc107; padding: 10px; border-radius: 4px; margin: 15px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🔐 Password Reset</h1>
                </div>
                <div class="content">
                    <p>Hi {user_name},</p>
                    <p>We received a request to reset your password. Click the button below to create a new password:</p>
                    <center>
                        <a href="{reset_url}" class="button">Reset My Password</a>
                    </center>
                    <p>Or copy and paste this link into your browser:</p>
                    <p class="link">{reset_url}</p>
                    
                    <div class="warning">
                        <p><strong>This link will expire in 1 hour for security purposes.</strong></p>
                        <p>If you didn't request a password reset, you can safely ignore this email.</p>
                    </div>
                    
                    <p>For security, if you didn't make this request, please contact us immediately.</p>
                    
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
        print(f"Password reset email error: {e}")
        return False


@auth_bp.route("/forgot-password", methods=["POST"])
def forgot_password():
    """Request password reset email for verified users only"""
    try:
        data = request.get_json()
        email = data.get("email", "").strip().lower()

        if not email:
            return jsonify({"error": "Email is required"}), 400

        # Check if user exists and is verified
        user = User.query.filter_by(email=email).first()

        if not user:
            # Don't reveal if user exists or not for security
            return jsonify(
                {
                    "message": "If an account with this email exists and is verified, you will receive a password reset link."
                }
            ), 200

        if not user.is_verified:
            return jsonify(
                {
                    "error": "This email is not verified. Please verify your email first or contact support."
                }
            ), 400

        # Generate reset token
        reset_token = secrets.token_urlsafe(32)
        user.password_reset_token = reset_token
        user.password_reset_expires = datetime.utcnow() + timedelta(hours=1)
        db.session.commit()

        # Send reset email
        send_password_reset_email(user.email, user.name, reset_token)

        return jsonify(
            {
                "message": "If an account with this email exists and is verified, you will receive a password reset link."
            }
        ), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@auth_bp.route("/reset-password", methods=["POST"])
def reset_password():
    """Reset password using magic link token"""
    try:
        data = request.get_json()
        token = data.get("token", "")
        new_password = data.get("new_password", "")

        if not token or not new_password:
            return jsonify({"error": "Token and new password are required"}), 400

        if len(new_password) < 6:
            return jsonify(
                {"error": "Password must be at least 6 characters long"}
            ), 400

        # Find user with valid reset token
        user = User.query.filter_by(password_reset_token=token).first()

        if not user:
            return jsonify({"error": "Invalid or expired reset token"}), 400

        if (
            user.password_reset_expires
            and user.password_reset_expires < datetime.utcnow()
        ):
            return jsonify(
                {
                    "error": "Reset token has expired. Please request a new password reset."
                }
            ), 400

        # Update password
        user.set_password(new_password)
        user.password_reset_token = None
        user.password_reset_expires = None
        db.session.commit()

        return jsonify(
            {
                "message": "Password reset successfully! You can now log in with your new password."
            }
        ), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@auth_bp.route("/verify-reset-token", methods=["POST"])
def verify_reset_token():
    """Verify if a reset token is valid"""
    try:
        data = request.get_json()
        token = data.get("token", "")

        if not token:
            return jsonify({"error": "Token is required"}), 400

        user = User.query.filter_by(password_reset_token=token).first()

        if not user:
            return jsonify({"valid": False, "error": "Invalid token"}), 400

        if (
            user.password_reset_expires
            and user.password_reset_expires < datetime.utcnow()
        ):
            return jsonify({"valid": False, "error": "Token has expired"}), 400

        return jsonify({"valid": True}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@auth_bp.route("/profile", methods=["PUT"])
@jwt_required()
def update_profile():
    """Update user profile"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()

        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Check if trying to update sensitive fields
        name = data.get("name", "").strip()
        phone = data.get("phone", "").strip()
        new_password = data.get("new_password", "")
        business_name = data.get("business_name", "").strip()

        # Sensitive fields require password verification
        sensitive_fields = ["email", "role", "is_active"]
        has_sensitive_changes = any(field in data for field in sensitive_fields)
        needs_password_verification = new_password or has_sensitive_changes

        if needs_password_verification:
            current_password = data.get("current_password", "")
            if not current_password:
                return jsonify(
                    {"error": "Current password is required to make these changes"}
                ), 400

            if not user.check_password(current_password):
                return jsonify({"error": "Current password is incorrect"}), 401

        # Update name
        if name:
            if len(name) < 2:
                return jsonify(
                    {"error": "Name must be at least 2 characters long"}
                ), 400
            user.name = name

        # Update phone
        if phone:
            try:
                parsed_phone = phonenumbers.parse(phone, "KE")
                if not phonenumbers.is_valid_number(parsed_phone):
                    return jsonify({"error": "Invalid phone number"}), 400
                formatted_phone = phonenumbers.format_number(parsed_phone, PNF.E164)
                existing_user = User.query.filter_by(phone=formatted_phone).first()
                if existing_user and existing_user.id != user.id:
                    return jsonify({"error": "Phone number is already registered"}), 400
                user.phone = formatted_phone
            except:
                return jsonify({"error": "Invalid phone number format"}), 400
        elif "phone" in data and data["phone"] is None:
            user.phone = None

        # Update business name
        if "business_name" in data:
            user.business_name = business_name if business_name else None

        # Update password if provided
        if new_password:
            if len(new_password) < 6:
                return jsonify(
                    {"error": "New password must be at least 6 characters long"}
                ), 400
            user.set_password(new_password)

        user.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify(
            {"message": "Profile updated successfully", "user": user.to_dict()}
        ), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@auth_bp.route("/organizer-profile", methods=["GET", "PUT"])
@jwt_required()
def organizer_profile():
    """Get or update organizer profile"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)

        if not user:
            return jsonify({"error": "User not found"}), 404

        if request.method == "GET":
            return jsonify(
                {
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "phone": user.phone,
                    "business_name": user.business_name,
                    "role": user.role.value if user.role else None,
                }
            ), 200

        # PUT request - update profile
        data = request.get_json()

        name = data.get("name", "").strip()
        phone = data.get("phone", "").strip()
        business_name = data.get("business_name", "").strip()

        # Update name
        if name:
            if len(name) < 2:
                return jsonify(
                    {"error": "Name must be at least 2 characters long"}
                ), 400
            user.name = name

        # Update phone
        if phone:
            try:
                parsed_phone = phonenumbers.parse(phone, "KE")
                if not phonenumbers.is_valid_number(parsed_phone):
                    return jsonify({"error": "Invalid phone number"}), 400
                formatted_phone = phonenumbers.format_number(parsed_phone, PNF.E164)
                existing_user = User.query.filter_by(phone=formatted_phone).first()
                if existing_user and existing_user.id != user.id:
                    return jsonify({"error": "Phone number is already registered"}), 400
                user.phone = formatted_phone
            except:
                return jsonify({"error": "Invalid phone number format"}), 400
        elif "phone" in data and data["phone"] is None:
            user.phone = None

        # Update business name
        if "business_name" in data:
            user.business_name = business_name if business_name else None

        user.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify(
            {
                "message": "Profile updated successfully",
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "phone": user.phone,
                "business_name": user.business_name,
                "role": user.role.value if user.role else None,
            }
        ), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
