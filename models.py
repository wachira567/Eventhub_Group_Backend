# SQLAlchemy Database Models
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from extensions import db


class User(db.Model):
    """User model for authentication and profile"""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20), unique=True)
    role = db.Column(db.String(20), default="attendee")
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    events_organized = db.relationship("Event", backref="organizer", lazy=True)
    tickets = db.relationship("Ticket", backref="user", lazy=True)
    reviews = db.relationship("Review", backref="user", lazy=True)
    mpesa_transactions = db.relationship("MpesaTransaction", backref="user", lazy=True)

    def set_password(self, password):
        """Hash and set user password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if password matches hash"""
        return check_password_hash(self.password_hash, password)


class Category(db.Model):
    """Event category model"""

    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    events = db.relationship("Event", backref="category", lazy=True)


class Event(db.Model):
    """Event model for ticketed events"""

    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    venue = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default="pending")
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    organizer_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    banner_image = db.Column(db.String(500))
    total_capacity = db.Column(db.Integer, default=100)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    ticket_types = db.relationship("TicketType", backref="event", lazy=True)
    tickets = db.relationship("Ticket", backref="event", lazy=True)
    reviews = db.relationship("Review", backref="event", lazy=True)
    saved_by = db.relationship("SavedEvent", backref="event", lazy=True)
    mpesa_transactions = db.relationship("MpesaTransaction", backref="event", lazy=True)


class TicketType(db.Model):
    """Ticket type/model for events (VIP, Regular, etc.)"""

    __tablename__ = "ticket_types"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    quantity_available = db.Column(db.Integer, nullable=False)
    quantity_sold = db.Column(db.Integer, default=0)
    sales_start = db.Column(db.DateTime)
    sales_end = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    tickets = db.relationship("Ticket", backref="ticket_type", lazy=True)


class Ticket(db.Model):
    """Ticket model for purchased tickets"""

    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(50), unique=True, nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    guest_email = db.Column(db.String(255))
    guest_phone = db.Column(db.String(20))
    ticket_type_id = db.Column(db.Integer, db.ForeignKey("ticket_types.id"))
    quantity = db.Column(db.Integer, default=1)
    total_price = db.Column(db.Float, nullable=False)
    payment_status = db.Column(db.String(20), default="pending")
    qr_code = db.Column(db.String(500))
    qr_code_image = db.Column(db.LargeBinary)
    used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def generate_ticket_number(self):
        """Generate unique ticket number"""
        import uuid

        return f"TKT-{uuid.uuid4().hex[:8].upper()}"


class MpesaTransaction(db.Model):
    """M-Pesa transaction records"""

    __tablename__ = "mpesa_transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"))
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.id"))
    amount = db.Column(db.Float, nullable=False)
    phone_number = db.Column(db.String(20), nullable=False)
    transaction_id = db.Column(db.String(100), unique=True)
    mpesa_receipt = db.Column(db.String(100))
    status = db.Column(db.String(20), default="pending")
    result_desc = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Review(db.Model):
    """Event review model"""

    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1-5 stars
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SavedEvent(db.Model):
    """User saved events"""

    __tablename__ = "saved_events"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Unique constraint to prevent duplicate saves
    __table_args__ = (
        db.UniqueConstraint("user_id", "event_id", name="_user_event_uc"),
    )


class EventImage(db.Model):
    """Additional event images"""

    __tablename__ = "event_images"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    image_url = db.Column(db.String(500), nullable=False)
    image_type = db.Column(db.String(50))  # gallery, banner, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
