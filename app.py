"""
EventHub Backend - Flask Application
Event Ticketing & Management Platform
"""

import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_migrate import Migrate
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager
from flask_jwt_extended.exceptions import JWTExtendedException
import socket

# MONKEY PATCH: Force IPv4
# Render environment seems to lack IPv6 support, causing "Address family not supported"
# and "Network is unreachable" errors when smtplib picks the IPv6 address.
orig_getaddrinfo = socket.getaddrinfo

def getaddrinfo_ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
    # Force AF_INET (IPv4)
    family = socket.AF_INET
    return orig_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = getaddrinfo_ipv4_only
# END MONKEY PATCH

from extensions import db, mail

# Load environment variables
load_dotenv()

# Import models for Flask-Migrate
from models import db


def create_app():
    """Application factory pattern"""
    app = Flask(__name__)
    
    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///eventhub.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 10,
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'max_overflow': 20,
        'pool_timeout': 30,
    }
    app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-key')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES', 3600))
    app.config['JWT_TOKEN_LOCATION'] = ['headers']
    app.config['JWT_HEADER_NAME'] = 'Authorization'
    app.config['JWT_HEADER_TYPE'] = 'Bearer'
    app.config['JWT_CSRF_PROTECT'] = False  # Disable CSRF for stateless JWT
    app.config['RESEND_API_KEY'] = os.environ.get('RESEND_API_KEY')
    app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
    app.config['MAIL_USE_TLS'] = os.environ.get('MAIL_USE_TLS', 'True').lower() == 'true'
    app.config['MAIL_USE_SSL'] = os.environ.get('MAIL_USE_SSL', 'False').lower() == 'true'
    app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')
    app.config['FRONTEND_URL'] = os.environ.get('FRONTEND_URL', 'http://localhost:5173')
    
    # Initialize JWT
    jwt = JWTManager(app)
    
    # JWT Error handlers
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        print(f"JWT Error: Invalid token - {error}")
        return jsonify({
            'error': 'Invalid token',
            'message': str(error)
        }), 422

    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, decoded_token):
        print(f"JWT Error: Token expired")
        return jsonify({
            'error': 'Token has expired'
        }), 422

    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, decoded_token):
        print(f"JWT Error: Token revoked")
        return jsonify({
            'error': 'Token has been revoked'
        }), 422

    @jwt.needs_fresh_token_loader
    def needs_fresh_token_callback(jwt_header, decoded_token):
        print(f"JWT Error: Fresh token required")
        return jsonify({
            'error': 'Fresh token required'
        }), 422
    
    # Initialize extensions
    migrate = Migrate(app, db)
    
    db.init_app(app)
    mail.init_app(app)
    
    # Add before_request handler to ensure fresh database connection
    @app.before_request
    def before_request():
        db.session.flush()
    
    # Add teardown handler
    @app.teardown_appcontext
    def shutdown_session(exception=None):
        db.session.remove()
    
    CORS(app, resources={r"/api/*": {
        "origins": [os.environ.get('FRONTEND_URL', 'http://localhost:5173')],
        "supports_credentials": True,
        "allow_headers": ["Content-Type", "Authorization"],
        "expose_headers": ["Authorization"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]
    }})
    
    # Register blueprints
    from routes.auth import auth_bp
    from routes.events import events_bp
    from routes.tickets import tickets_bp
    from routes.mpesa import mpesa_bp
    from routes.users import users_bp
    from routes.analytics import analytics_bp
    from routes.moderation import moderation_bp
    from routes.reviews import reviews_bp
    from routes.export import export_bp
    from routes.reports import reports_bp
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(events_bp, url_prefix='/api/events')
    app.register_blueprint(tickets_bp, url_prefix='/api/tickets')
    app.register_blueprint(mpesa_bp, url_prefix='/api/mpesa')
    app.register_blueprint(users_bp, url_prefix='/api/users')
    app.register_blueprint(analytics_bp, url_prefix='/api/analytics')
    app.register_blueprint(moderation_bp, url_prefix='/api/moderation')
    app.register_blueprint(reviews_bp, url_prefix='/api/reviews')
    app.register_blueprint(export_bp, url_prefix='/api/export')
    app.register_blueprint(reports_bp, url_prefix='/api/reports')
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Resource not found'}, 404
    
    @app.errorhandler(422)
    def unprocessable_entity(error):
        print(f"422 Error: {error}")
        return {'error': 'Unprocessable entity', 'message': str(error)}, 422
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        print(f"500 Error: {error}")
        return {'error': 'Internal server error'}, 500
    

    # Health check
    @app.route('/api/health')
    def health_check():
        return {'status': 'ok', 'message': 'EventHub API is running'}

    # Root endpoint to prevent 404s
    @app.route('/')
    def root():
        return {'status': 'ok', 'message': 'EventHub Backend is running. Access API at /api'}

    # Debug Email Endpoint
    # Debug Email Endpoint
    # Debug Email Endpoint
    @app.route('/api/debug/email', methods=['POST'])
    def debug_email():
        try:
            import resend
            
            data = request.get_json() or {}
            recipient = data.get('email', os.environ.get('MAIL_USERNAME'))
            
            api_key = app.config.get('RESEND_API_KEY')
            if not api_key:
                return jsonify({'error': 'RESEND_API_KEY not configured'}), 500
                
            resend.api_key = api_key
            
            if not recipient:
                return jsonify({'error': 'No recipient specified'}), 400
            
            # Send using Resend
            params = {
                "from": "EventHub <onboarding@resend.dev>",
                "to": [recipient],
                "subject": "EventHub Debug Email (Resend)",
                "html": "<p>This is a test email from EventHub backend using <strong>Resend API</strong>.</p>"
            }
            
            email = resend.Emails.send(params)
            
            return jsonify({
                'message': f'Test email sent successfully to {recipient}',
                'resend_id': email.get('id'),
                'provider': 'Resend API'
            }), 200
        except Exception as e:
            print(f"Debug Email Error: {e}")
            return jsonify({
                'error': str(e),
                'provider': 'Resend API'
            }), 500
    
    return app


# Create app instance
app = create_app()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=os.environ.get('FLASK_ENV') == 'development')
