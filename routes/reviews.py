


from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from sqlalchemy import func
from extensions import db
from models import User, UserRole, Event, EventReview, Ticket, TicketTypeModel


reviews_bp = Blueprint('reviews', __name__)


@jwt_required()
@reviews_bp.route('', methods=['GET'])
def get_reviews():
    """Get reviews with filtering"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        event_id = request.args.get('event_id', type=int)
        user_id = request.args.get('user_id', type=int)
        min_rating = request.args.get('min_rating', type=int)
        max_rating = request.args.get('max_rating', type=int)
        
        query = EventReview.query
        
        if event_id:
            query = query.filter_by(event_id=event_id)
        
        if user_id:
            query = query.filter_by(user_id=user_id)
        
        if min_rating:
            query = query.filter(EventReview.rating >= min_rating)
        
        if max_rating:
            query = query.filter(EventReview.rating <= max_rating)
        
        pagination = query.order_by(EventReview.created_at.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        return jsonify({
            'reviews': [review.to_dict() for review in pagination.items],
            'total': pagination.total,
            'pages': pagination.pages,
            'current_page': page,
            'average_rating': db.session.query(func.avg(EventReview.rating)).filter(
                EventReview.event_id == event_id if event_id else True
            ).scalar() or 0
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@jwt_required()
@reviews_bp.route('/<int:review_id>', methods=['GET'])
def get_review(review_id):
    """Get single review"""
    try:
        review = EventReview.query.get_or_404(review_id)
        return jsonify({'review': review.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@jwt_required()
@reviews_bp.route('/<int:review_id>', methods=['PUT'])
def update_review(review_id):
    """Update a review"""
    try:
        user_id = get_jwt_identity()
        review = EventReview.query.get_or_404(review_id)
        
        if review.user_id != user_id:
            return jsonify({'error': 'Permission denied'}), 403
        
        data = request.get_json()
        
        if 'rating' in data:
            if 1 <= data['rating'] <= 5:
                review.rating = data['rating']
            else:
                return jsonify({'error': 'Rating must be between 1 and 5'}), 400
        
        if 'comment' in data:
            review.comment = data['comment'].strip()
        
        review.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Review updated successfully',
            'review': review.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@jwt_required()
@reviews_bp.route('/<int:review_id>', methods=['DELETE'])
def delete_review(review_id):
    """Delete a review"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        review = EventReview.query.get_or_404(review_id)
        
        if review.user_id != user_id and user.role not in [UserRole.ADMIN]:
            return jsonify({'error': 'Permission denied'}), 403
        
        db.session.delete(review)
        db.session.commit()
        
        return jsonify({'message': 'Review deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500


@jwt_required()
@reviews_bp.route('/event/<int:event_id>/stats', methods=['GET'])
def get_event_review_stats(event_id):
    """Get review statistics for an event"""
    try:
        stats = {
            'total_reviews': EventReview.query.filter_by(event_id=event_id).count(),
            'average_rating': db.session.query(func.avg(EventReview.rating)).filter_by(
                event_id=event_id
            ).scalar() or 0,
            'rating_distribution': {}
        }
        
        for i in range(1, 6):
            stats['rating_distribution'][i] = EventReview.query.filter_by(
                event_id=event_id,
                rating=i
            ).count()
        
        return jsonify({'stats': stats}), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500