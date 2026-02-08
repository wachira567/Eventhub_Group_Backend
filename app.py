# Main Flask Application Factory
import os
from flask import Flask
from dotenv import load_dotenv
from extensions import db, migrate, jwt, mail, CORS

# Load environment variables
load_dotenv()


def create_app():
    """Application factory pattern for Flask app"""
    app = Flask(__name__)

    # Configuration
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "sqlite:///eventhub.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "jwt-secret-key")
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = int(
        os.getenv("JWT_ACCESS_TOKEN_EXPIRES", 3600)
    )
    app.config["MAIL_SERVER"] = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    app.config["MAIL_PORT"] = int(os.getenv("MAIL_PORT", 587))
    app.config["MAIL_USE_TLS"] = os.getenv("MAIL_USE_TLS", "True") == "True"
    app.config["MAIL_USERNAME"] = os.getenv("MAIL_USERNAME")
    app.config["MAIL_PASSWORD"] = os.getenv("MAIL_PASSWORD")
    app.config["FRONTEND_URL"] = os.getenv("FRONTEND_URL", "http://localhost:5173")

    # Initialize extensions
    CORS(app, origins=app.config["FRONTEND_URL"])
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    mail.init_app(app)

    # Import and register blueprints
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

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(events_bp, url_prefix="/api/events")
    app.register_blueprint(tickets_bp, url_prefix="/api/tickets")
    app.register_blueprint(mpesa_bp, url_prefix="/api/mpesa")
    app.register_blueprint(users_bp, url_prefix="/api/users")
    app.register_blueprint(analytics_bp, url_prefix="/api/analytics")
    app.register_blueprint(moderation_bp, url_prefix="/api/moderation")
    app.register_blueprint(reviews_bp, url_prefix="/api/reviews")
    app.register_blueprint(export_bp, url_prefix="/api/export")
    app.register_blueprint(reports_bp, url_prefix="/api/reports")

    # Health check endpoint
    @app.route("/health")
    def health_check():
        return {"status": "healthy"}, 200

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
