"""
Events Routes
"""

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from sqlalchemy import or_, and_
from extensions import db
from models import (
    Event, User, Category, TicketTypeModel, Ticket,
    UserRole, SavedEvent, EventReview, EventStatus
)


events_bp = Blueprint('events', __name__)


def is_admin_or_moderator(user):
    """Check if user is admin or moderator"""
    return user.role in [UserRole.ADMIN, UserRole.MODERATOR]


@events_bp.route('', methods=['GET'])
def get_events():
    """Get all events with filtering"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 12, type=int)
        category_id = request.args.get('category', type=int)
        search = request.args.get('q', '').strip()
        city = request.args.get('city', '').strip()
        organizer_id = request.args.get('organizer', type=int)
        status = request.args.get('status', '').strip()
        featured = request.args.get('featured', 'false').lower() == 'true'
        upcoming = request.args.get('upcoming', 'false').lower() == 'true'
        sort = request.args.get('sort', 'date')
        start_date_from = request.args.get('start_date_from', '').strip()
        
        query = Event.query.filter(Event.is_published == True)
        
        if category_id:
            query = query.filter(Event.category_id == category_id)
        
        if search:
            search_term = f'%{search}%'
            query = query.filter(
                or_(
                    Event.title.ilike(search_term),
                    Event.description.ilike(search_term),
                    Event.venue.ilike(search_term)
                )
            )
        
        if city:
            query = query.filter(Event.city.ilike(f'%{city}%'))
        
        if organizer_id:
            query = query.filter(Event.organizer_id == organizer_id)
        
        if status:
            if status == 'ongoing':
                query = query.filter(
                    Event.start_date <= datetime.utcnow(),
                    Event.end_date >= datetime.utcnow()
                )
            elif status == 'upcoming':
                query = query.filter(Event.start_date > datetime.utcnow())
            elif status == 'past':
                query = query.filter(Event.end_date < datetime.utcnow())
        
        if start_date_from:
            try:
                from_date = datetime.fromisoformat(start_date_from)
                query = query.filter(Event.start_date >= from_date)
            except ValueError:
                pass
        
        if featured:
            query = query.filter(Event.is_featured == True)
        
        if upcoming:
            query = query.filter(Event.start_date > datetime.utcnow())
        
        if sort == 'date':
            query = query.order_by(Event.start_date.asc())
        elif sort == 'popularity':
            query = query.order_by(Event.view_count.desc())
        elif sort == 'price':
            query = query.join(TicketTypeModel).order_by(TicketTypeModel.price.asc())
        
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'events': [event.to_dict() for event in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@events_bp.route('/<int:event_id>', methods=['GET'])
def get_event(event_id):
    """Get single event details"""
    try:
        event = Event.query.get_or_404(event_id)
        
        # Get ticket types for this event
        ticket_types = TicketTypeModel.query.filter_by(event_id=event_id).all()
        
        event.view_count += 1
        db.session.commit()
        
        return jsonify({
            'event': event.to_dict(),
            'ticket_types': [tt.to_dict() for tt in ticket_types]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@events_bp.route('', methods=['POST'])
@jwt_required()
def create_event():
    """Create a new event"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        if user.role not in [UserRole.ADMIN, UserRole.ORGANIZER]:
            return jsonify({'error': 'Only organizers can create events'}), 403
        
        data = request.get_json()
        print(f"Received event data: {data}")
        
        required_fields = ['title', 'description', 'start_date', 'end_date']
        for field in ['title', 'description', 'start_date', 'end_date']:
            if not data.get(field):
                print(f"Missing required field: {field}")
                return jsonify({'error': f'{field} is required'}), 400
        
        # Handle category (can be integer ID or string name)
        category_id = data.get('category_id')
        category_name = data.get('category')
        
        if not category_id and not category_name:
            print("Missing required field: category")
            return jsonify({'error': 'category is required'}), 400
        
        if category_id:
            category = Category.query.get(int(category_id))
        else:
            # Case-insensitive lookup
            category = Category.query.filter(Category.name.ilike(category_name)).first()
        
        if not category:
            # Debug: show available categories
            all_cats = Category.query.all()
            available = [c.name for c in all_cats]
            print(f"Invalid category: id={category_id}, name={category_name}")
            print(f"Available categories: {available}")
            return jsonify({'error': 'Invalid category'}), 400
        
        category_id = category.id
        
        try:
            start_date = datetime.fromisoformat(data['start_date'].replace('Z', '+00:00'))
            end_date = datetime.fromisoformat(data['end_date'].replace('Z', '+00:00'))
            # Make naive for comparison with utcnow()
            if start_date.tzinfo is not None:
                start_date = start_date.replace(tzinfo=None)
            if end_date.tzinfo is not None:
                end_date = end_date.replace(tzinfo=None)
        except ValueError:
            return jsonify({'error': 'Invalid date format. Use ISO format.'}), 400
        
        if start_date >= end_date:
            return jsonify({'error': 'End date must be after start date'}), 400
        
        if start_date < datetime.utcnow():
            return jsonify({'error': 'Start date cannot be in the past'}), 400
        
        if data.get('early_bird_end_date'):
            try:
                early_bird_end = datetime.fromisoformat(data['early_bird_end_date'].replace('Z', '+00:00'))
                if early_bird_end >= start_date:
                    return jsonify({'error': 'Early bird end date must be before event start date'}), 400
            except ValueError:
                return jsonify({'error': 'Invalid early bird end date format'}), 400
        
        event = Event(
            organizer_id=user.id,
            title=data['title'].strip(),
            description=data.get('description', '').strip(),
            category_id=category_id,
            venue=data.get('venue', '').strip(),
            address=data.get('address', '').strip(),
            city=data.get('city', '').strip(),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            start_date=start_date,
            end_date=end_date,
            early_bird_end_date=datetime.fromisoformat(data['early_bird_end_date'].replace('Z', '+00:00')) if data.get('early_bird_end_date') else None,
            is_published=data.get('is_published', False),
            is_featured=data.get('is_featured', False),
            image_url=data.get('image_url', '').strip(),
            max_attendees=data.get('max_attendees'),
            has_tickets=data.get('has_tickets', False)
        )
        
        db.session.add(event)
        db.session.flush()
        
        ticket_types_data = data.get('ticket_types', [])
        if ticket_types_data:
            for tt_data in ticket_types_data:
                if not tt_data.get('name') or tt_data.get('price') is None:
                    continue
                ticket_type = TicketTypeModel(
                    event_id=event.id,
                    name=tt_data['name'].strip(),
                    description=tt_data.get('description', '').strip(),
                    price=float(tt_data['price']),
                    quantity=tt_data.get('quantity'),
                    benefits=tt_data.get('benefits', [])
                )
                db.session.add(ticket_type)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Event created successfully',
            'event': event.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating event: {e}")
        return jsonify({'error': str(e)}), 500


@events_bp.route('/<int:event_id>', methods=['PUT'])
@jwt_required()
def update_event(event_id):
    """Update an event"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        event = Event.query.get_or_404(event_id)
        
        if user.role not in [UserRole.ADMIN, UserRole.ORGANIZER]:
            return jsonify({'error': 'Permission denied'}), 403
        
        if user.role != UserRole.ADMIN and event.organizer_id != user.id:
            return jsonify({'error': 'You can only update your own events'}), 403
        
        data = request.get_json()
        
        if 'title' in data:
            if not data['title'].strip():
                return jsonify({'error': 'Title cannot be empty'}), 400
            event.title = data['title'].strip()
        
        if 'description' in data:
            event.description = data['description'].strip()
        
        if 'category_id' in data:
            category = Category.query.get(data['category_id'])
            if not category:
                return jsonify({'error': 'Invalid category'}), 400
            event.category_id = data['category_id']
        
        if 'venue' in data:
            event.venue = data['venue'].strip()
        
        if 'address' in data:
            event.address = data['address'].strip()
        
        if 'city' in data:
            event.city = data['city'].strip()
        
        if 'latitude' in data:
            event.latitude = data['latitude']
        
        if 'longitude' in data:
            event.longitude = data['longitude']
        
        if 'start_date' in data:
            try:
                event.start_date = datetime.fromisoformat(data['start_date'].replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'error': 'Invalid start date format'}), 400
        
        if 'end_date' in data:
            try:
                event.end_date = datetime.fromisoformat(data['end_date'].replace('Z', '+00:00'))
            except ValueError:
                return jsonify({'error': 'Invalid end date format'}), 400
        
        if event.start_date >= event.end_date:
            return jsonify({'error': 'End date must be after start date'}), 400
        
        if 'early_bird_end_date' in data:
            if data['early_bird_end_date']:
                try:
                    event.early_bird_end_date = datetime.fromisoformat(data['early_bird_end_date'].replace('Z', '+00:00'))
                except ValueError:
                    return jsonify({'error': 'Invalid early bird end date format'}), 400
            else:
                event.early_bird_end_date = None
        
        if 'is_published' in data:
            if user.role == UserRole.ADMIN:
                event.is_published = data['is_published']
            elif event.organizer_id == user.id:
                if event.status != EventStatus.APPROVED:
                    return jsonify({'error': 'Cannot publish event until approved by admin'}), 400
                event.is_published = data['is_published']
        
        if 'is_featured' in data and user.role == UserRole.ADMIN:
            event.is_featured = data['is_featured']
        
        if 'image_url' in data:
            event.image_url = data['image_url'].strip()
        
        if 'max_attendees' in data:
            event.max_attendees = data['max_attendees']
        
        if 'has_tickets' in data:
            event.has_tickets = data['has_tickets']
        
        event.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Event updated successfully',
            'event': event.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@events_bp.route('/<int:event_id>', methods=['DELETE'])
@jwt_required()
def delete_event(event_id):
    """Delete an event"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        event = Event.query.get_or_404(event_id)
        
        if user.role not in [UserRole.ADMIN, UserRole.ORGANIZER]:
            return jsonify({'error': 'Permission denied'}), 403
        
        if user.role != UserRole.ADMIN and event.organizer_id != user.id:
            return jsonify({'error': 'You can only delete your own events'}), 403
        
        db.session.delete(event)
        db.session.commit()
        
        return jsonify({'message': 'Event deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@events_bp.route('/<int:event_id>/save', methods=['POST'])
@jwt_required()
def save_event(event_id):
    """Save an event to user's saved list"""
    try:
        user_id = get_jwt_identity()
        event = Event.query.get_or_404(event_id)
        
        existing = SavedEvent.query.filter_by(user_id=user_id, event_id=event_id).first()
        if existing:
            return jsonify({'error': 'Event already saved'}), 400
        
        saved = SavedEvent(user_id=user_id, event_id=event_id)
        db.session.add(saved)
        db.session.commit()
        
        return jsonify({'message': 'Event saved successfully'}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@events_bp.route('/<int:event_id>/unsave', methods=['DELETE'])
@jwt_required()
def unsave_event(event_id):
    """Remove event from user's saved list"""
    try:
        user_id = get_jwt_identity()
        saved = SavedEvent.query.filter_by(user_id=user_id, event_id=event_id).first_or_404()
        
        db.session.delete(saved)
        db.session.commit()
        
        return jsonify({'message': 'Event removed from saved'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@events_bp.route('/saved', methods=['GET'])
@jwt_required()
def get_saved_events():
    """Get user's saved events"""
    try:
        user_id = get_jwt_identity()
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 12, type=int)
        
        pagination = SavedEvent.query.filter_by(user_id=user_id)\
            .order_by(SavedEvent.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        events = []
        for s in pagination.items:
            try:
                event_data = s.event.to_dict() if s.event else None
                events.append(event_data)
            except Exception:
                events.append(None)
        
        # Filter out None events
        events = [e for e in events if e is not None]
        
        return jsonify({
            'events': events,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@events_bp.route('/<int:event_id>/reviews', methods=['GET'])
def get_event_reviews(event_id):
    """Get reviews for an event"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        pagination = EventReview.query.filter_by(event_id=event_id)\
            .order_by(EventReview.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'reviews': [review.to_dict() for review in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@events_bp.route('/<int:event_id>/reviews', methods=['POST'])
@jwt_required()
def create_event_review(event_id):
    """Create a review for an event"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user.is_verified:
            return jsonify({'error': 'Please verify your email to leave a review'}), 403
        
        data = request.get_json()
        rating = data.get('rating')
        comment = data.get('comment', '').strip()
        
        if not rating or not 1 <= rating <= 5:
            return jsonify({'error': 'Rating must be between 1 and 5'}), 400
        
        existing_review = EventReview.query.filter_by(user_id=user_id, event_id=event_id).first()
        if existing_review:
            return jsonify({'error': 'You have already reviewed this event'}), 400
        
        has_ticket = Ticket.query.join(TicketTypeModel).filter(
            Ticket.user_id == user_id,
            TicketTypeModel.event_id == event_id,
            Ticket.payment_status == 'COMPLETED'
        ).first()
        
        if not has_ticket and user.role != UserRole.ADMIN:
            return jsonify({'error': 'You must have a valid ticket to review this event'}), 403
        
        review = EventReview(
            user_id=user_id,
            event_id=event_id,
            rating=rating,
            comment=comment
        )
        db.session.add(review)
        db.session.commit()
        
        return jsonify({
            'message': 'Review submitted successfully',
            'review': review.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@events_bp.route('/my-events', methods=['GET'])
@jwt_required()
def get_my_events():
    """Get events created by current user"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if user.role not in [UserRole.ADMIN, UserRole.ORGANIZER]:
            return jsonify({'error': 'Only organizers can view their events'}), 403
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 12, type=int)
        status = request.args.get('status', '').strip()
        
        query = Event.query.filter_by(organizer_id=user.id)
        
        if status:
            if status == 'draft':
                query = query.filter(Event.is_published == False)
            elif status == 'published':
                query = query.filter(Event.is_published == True)
            elif status == 'pending':
                query = query.filter(Event.status == EventStatus.PENDING)
            elif status == 'approved':
                query = query.filter(Event.status == EventStatus.APPROVED)
            elif status == 'cancelled':
                query = query.filter(Event.status == EventStatus.CANCELLED)
        
        pagination = query.order_by(Event.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        # Calculate tickets_sold and revenue for each event
        events_data = []
        for event in pagination.items:
            # Calculate tickets sold from TicketTypeModel
            ticket_types = TicketTypeModel.query.filter_by(event_id=event.id).all()
            tickets_sold = sum(tt.sold_quantity or 0 for tt in ticket_types)
            
            # Calculate revenue from completed transactions
            from models import MpesaTransaction
            revenue = db.session.query(db.func.sum(MpesaTransaction.amount)).filter(
                MpesaTransaction.event_id == event.id,
                MpesaTransaction.status == 'COMPLETED'
            ).scalar() or 0
            
            event_dict = event.to_dict()
            event_dict['tickets_sold'] = tickets_sold
            event_dict['revenue'] = float(revenue)
            events_data.append(event_dict)
        
        return jsonify({
            'events': events_data,
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@events_bp.route('/categories', methods=['GET'])
def get_categories():
    """Get all event categories"""
    try:
        categories = Category.query.order_by(Category.name).all()
        return jsonify({
            'categories': [cat.to_dict() for cat in categories]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@events_bp.route('/<int:event_id>/ticket-types', methods=['GET'])
def get_event_ticket_types(event_id):
    """Get ticket types for an event"""
    try:
        event = Event.query.get_or_404(event_id)
        ticket_types = TicketTypeModel.query.filter_by(event_id=event_id).all()
        
        return jsonify({
            'ticket_types': [tt.to_dict() for tt in ticket_types]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@events_bp.route('/<int:event_id>/ticket-types/<int:tt_id>', methods=['GET'])
def get_ticket_type(event_id, tt_id):
    """Get a specific ticket type"""
    try:
        ticket_type = TicketTypeModel.query.filter_by(id=tt_id, event_id=event_id).first_or_404()
        return jsonify({'ticket_type': ticket_type.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
