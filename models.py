"""
Database Models for EventHub
Event Ticketing & Management Platform
"""

from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import enum


# Import db from extensions to ensure consistent instance
from extensions import db


class UserRole(enum.Enum):
    ADMIN = "admin"
    ORGANIZER = "organizer"
    ATTENDEE = "attendee"
    MODERATOR = "moderator"


class EventStatus(enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class TicketStatus(enum.Enum):
    VALID = "valid"
    USED = "used"
    CANCELLED = "cancelled"


class MpesaTransactionStatus(enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class User(db.Model):
    """User model for authentication and authorization"""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True)
    role = db.Column(db.Enum(UserRole), default=UserRole.ATTENDEE)
    is_active = db.Column(db.Boolean, default=True)
    is_verified = db.Column(db.Boolean, default=False)
    email_verification_token = db.Column(db.String(256), unique=True, nullable=True)
    email_verification_expires = db.Column(db.DateTime, nullable=True)
    password_reset_token = db.Column(db.String(256), unique=True, nullable=True)
    password_reset_expires = db.Column(db.DateTime, nullable=True)
    business_name = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    organized_events = db.relationship(
        "Event",
        backref="organizer_obj",
        lazy="dynamic",
        foreign_keys="Event.organizer_id",
    )
    tickets = db.relationship(
        "Ticket", backref="user", lazy="dynamic", foreign_keys="Ticket.user_id"
    )
    saved_events = db.relationship("SavedEvent", backref="user", lazy="dynamic")
    moderated_events = db.relationship(
        "Event",
        backref="moderator_obj",
        lazy="dynamic",
        foreign_keys="Event.moderated_by",
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "phone": self.phone,
            "role": self.role.value,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "business_name": self.business_name,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Category(db.Model):
    """Event categories"""

    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text)
    icon = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
        }


class Event(db.Model):
    """Event model for event management"""

    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    venue = db.Column(db.String(300))
    address = db.Column(db.String(500))
    city = db.Column(db.String(100), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    tags = db.Column(db.String(500))
    image_url = db.Column(db.String(500))
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.Enum(EventStatus), default=EventStatus.DRAFT)
    organizer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    longitude = db.Column(db.Float, nullable=True)
    latitude = db.Column(db.Float, nullable=True)

    has_tickets = db.Column(db.Boolean, default=False)
    max_attendees = db.Column(db.Integer)
    early_bird_end_date = db.Column(db.DateTime)

    is_published = db.Column(db.Boolean, default=False)
    is_featured = db.Column(db.Boolean, default=False)
    view_count = db.Column(db.Integer, default=0)
    moderated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    moderated_at = db.Column(db.DateTime, nullable=True)
    moderation_notes = db.Column(db.Text)

    ticket_types = db.relationship("TicketTypeModel", backref="event", lazy="dynamic")
    tickets = db.relationship("Ticket", backref="event", lazy="dynamic")
    saved_by = db.relationship("SavedEvent", backref="event", lazy="dynamic")

    def to_dict(self):
        coordinates = None
        if self.longitude is not None and self.latitude is not None:
            coordinates = [self.longitude, self.latitude]

        category_name = None
        if self.category_id:
            category = Category.query.get(self.category_id)
            if category:
                category_name = category.name

        organizer_name = None
        if self.organizer_id:
            organizer = User.query.get(self.organizer_id)
            if organizer:
                organizer_name = organizer.business_name or organizer.name

        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "venue": self.venue,
            "address": self.address,
            "city": self.city,
            "coordinates": coordinates,
            "category_id": self.category_id,
            "category": category_name,
            "tags": self.tags.split(",") if self.tags else [],
            "image_url": self.image_url,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "status": self.status.value if self.status else None,
            "is_published": self.is_published,
            "is_featured": self.is_featured,
            "organizer_id": self.organizer_id,
            "organizer_name": organizer_name,
            "view_count": self.view_count,
            "has_tickets": self.has_tickets,
            "max_attendees": self.max_attendees,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def to_dict_with_organizer(self):
        organizer = User.query.get(self.organizer_id)
        organizer_name = (
            organizer.business_name or organizer.name
            if organizer
            else "Unknown Organizer"
        )
        data = self.to_dict()
        data["organizer_name"] = organizer_name
        return data


class TicketTypeModel(db.Model):
    """Ticket type model for different pricing tiers"""

    __tablename__ = "ticket_types"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    sold_quantity = db.Column(db.Integer, default=0)
    benefits = db.Column(db.Text)
    sales_start = db.Column(db.DateTime)
    sales_end = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def available(self):
        return self.quantity - self.sold_quantity

    def to_dict(self):
        import json

        return {
            "id": self.id,
            "event_id": self.event_id,
            "name": self.name,
            "description": self.description,
            "price": float(self.price) if self.price else 0,
            "quantity": self.quantity,
            "quantity_total": self.quantity,
            "sold_quantity": self.sold_quantity,
            "available": self.available,
            "benefits": json.loads(self.benefits) if self.benefits else [],
            "sales_start": self.sales_start.isoformat() if self.sales_start else None,
            "sales_end": self.sales_end.isoformat() if self.sales_end else None,
        }


class Ticket(db.Model):
    """Ticket model for purchased tickets"""

    __tablename__ = "tickets"

    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(20), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    ticket_type_id = db.Column(
        db.Integer, db.ForeignKey("ticket_types.id"), nullable=False
    )
    quantity = db.Column(db.Integer, default=1)
    total_price = db.Column(db.Numeric(10, 2), nullable=False)
    payment_status = db.Column(db.String(10), default="pending")
    mpesa_receipt = db.Column(db.String(100))
    purchased_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_guest = db.Column(db.Boolean, default=False)
    guest_email = db.Column(db.String(120), nullable=True)
    guest_name = db.Column(db.String(100), nullable=True)
    is_used = db.Column(db.Boolean, default=False)
    used_at = db.Column(db.DateTime, nullable=True)
    verified_by = db.Column(db.Integer, nullable=True)
    qr_code = db.Column(db.Text, nullable=True)
    qr_data = db.Column(db.String(255), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "ticket_number": self.ticket_number,
            "event_id": self.event_id,
            "user_id": self.user_id,
            "ticket_type_id": self.ticket_type_id,
            "quantity": self.quantity,
            "total_price": float(self.total_price) if self.total_price else 0,
            "payment_status": self.payment_status,
            "mpesa_receipt": self.mpesa_receipt,
            "purchased_at": self.purchased_at.isoformat()
            if self.purchased_at
            else None,
            "is_guest": self.is_guest,
            "guest_email": self.guest_email,
            "guest_name": self.guest_name,
            "is_used": self.is_used,
            "used_at": self.used_at.isoformat() if self.used_at else None,
            "verified_by": self.verified_by,
            "qr_code": self.qr_code,
            "qr_data": self.qr_data,
        }


class MpesaTransaction(db.Model):
    """MPESA transaction records"""

    __tablename__ = "mpesa_transactions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True
    )  # Nullable for guest transactions
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    ticket_type_id = db.Column(
        db.Integer, db.ForeignKey("ticket_types.id"), nullable=False
    )
    ticket_id = db.Column(
        db.Integer, db.ForeignKey("tickets.id"), nullable=True
    )  # Links to the specific ticket
    quantity = db.Column(db.Integer, default=1)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    phone_number = db.Column(db.String(20))
    transaction_id = db.Column(db.String(100))
    checkout_request_id = db.Column(db.String(100))
    mpesa_receipt = db.Column(db.String(100))
    status = db.Column(db.String(50), default="pending")
    reference = db.Column(db.String(100))
    result_desc = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "event_id": self.event_id,
            "ticket_type_id": self.ticket_type_id,
            "ticket_id": self.ticket_id,
            "quantity": self.quantity,
            "amount": float(self.amount) if self.amount else 0,
            "phone_number": self.phone_number,
            "transaction_id": self.transaction_id,
            "mpesa_receipt": self.mpesa_receipt,
            "status": self.status,
            "reference": self.reference,
            "result_desc": self.result_desc,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
        }


class SavedEvent(db.Model):
    """User saved events"""

    __tablename__ = "saved_events"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "event_id", name="_user_event_uc"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "event_id": self.event_id,
            "event": self.event.to_dict() if self.event else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class EventReview(db.Model):
    """Event reviews and feedback"""

    __tablename__ = "event_reviews"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def to_dict(self):
        user = User.query.get(self.user_id)
        return {
            "id": self.id,
            "event_id": self.event_id,
            "user_id": self.user_id,
            "user_name": user.name if user else None,
            "rating": self.rating,
            "comment": self.comment,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
