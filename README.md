# EventHub Backend

A Flask-based backend for an event ticketing and management platform built with Python.

### Eventhub frontnd repository
https://github.com/wachira567/Group6_Eventhub_Frontend.git

## 🛠 Technologies Used

### Core Framework
- **Flask 3.0.0** - Lightweight WSGI web application framework
- **Flask-Migrate 4.0.5** - Database migration management for SQLAlchemy
- **Flask-SQLAlchemy 3.1.1** - ORM for database interactions
- **Flask-CORS 4.0.0** - Cross-Origin Resource Sharing support
- **Flask-JWT-Extended 4.6.0** - JWT authentication
- **Flask-Mail 0.9.1** - Email sending support

### Database
- **SQLAlchemy 2.0.23** - SQL toolkit and ORM
- **PostgreSQL** (via psycopg2-binary) or SQLite for development

### Payment Integration
- **Pympesa 1.0.1** - M-Pesa payment gateway integration

### Utilities
- **python-dotenv 1.0.0** - Environment variable management
- **requests 2.31.0** - HTTP library for API calls
- **python-dateutil 2.8.2** - Date/time utilities
- **marshmallow 3.20.1** - Object serialization/deserialization
- **email-validator 2.1.0** - Email validation
- **phonenumbers 8.13.25** - Phone number parsing/validation

### PDF & QR Generation
- **reportlab 4.0.7** - PDF generation
- **qrcode 7.4.2** - QR code generation
- **pillow 10.1.0** - Image processing

### Development
- **Python 3.10** - Runtime environment

---

## 📁 Project Structure

```
backend_group/
├── app.py                 # Main Flask application factory
├── models.py              # SQLAlchemy database models
├── extensions.py          # Flask extensions initialization
├── Pipfile               # Python dependencies
├── .env                  # Environment variables (create from .env.example)
├── migrations/           # Database migrations
├── routes/               # API route modules
│   ├── auth.py          # Authentication endpoints
│   ├── events.py        # Event management endpoints
│   ├── tickets.py       # Ticket purchase & management
│   ├── mpesa.py         # M-Pesa payment integration
│   ├── users.py         # User profile endpoints
│   ├── analytics.py     # Analytics & reporting
│   ├── moderation.py    # Event moderation
│   ├── reviews.py       # Event reviews
│   ├── export.py        # Data export
│   └── reports.py       # Reports generation
├── services/            # Business logic services
│   ├── email_service.py # Email sending
│   ├── mpesa_service.py # M-Pesa API integration
│   └── pdf_service.py   # PDF ticket generation
└── test_*.py           # Test files
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- pip or pipenv
- PostgreSQL (optional, SQLite used by default)

### Installation

1. **Clone the repository**
   ```bash
   cd backend_group
   ```

2. **Install dependencies**
   ```bash
   pipenv install
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env  # Create from example
   # Edit .env with your configuration
   ```

4. **Set up the database**
   ```bash
   pipenv run flask db upgrade
   ```

5. **Seed categories (optional)**
   ```bash
   pipenv run python seed_categories.py
   ```

### Running the Server

```bash
# Development mode
PIPENV_IGNORE_VIRTUALENVS=1 pipenv run flask run --debug

# Or with environment variables
PIPENV_IGNORE_VIRTUALENVS=1 pipenv run flask run --debug --host 0.0.0.0 --port 5000
```

The server will start at `http://localhost:5000`

---

## 📡 API Endpoints

### Authentication (`/api/auth`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | User login |
| POST | `/api/auth/logout` | User logout |
| GET | `/api/auth/me` | Get current user |
| POST | `/api/auth/verify-email` | Verify email |
| POST | `/api/auth/forgot-password` | Request password reset |
| POST | `/api/auth/reset-password` | Reset password |

### Events (`/api/events`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/events` | List all events |
| POST | `/api/events` | Create event (organizer) |
| GET | `/api/events/<id>` | Get event details |
| PUT | `/api/events/<id>` | Update event |
| DELETE | `/api/events/<id>` | Delete event |
| GET | `/api/events/<id>/tickets` | Get event tickets |
| POST | `/api/events/<id>/ticket-types` | Add ticket type |
| PUT | `/api/events/<id>/ticket-types/<tid>` | Update ticket type |
| POST | `/api/events/<id>/save` | Save event |
| DELETE | `/api/events/<id>/save` | Unsave event |

### Tickets (`/api/tickets`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tickets/my-tickets` | Get user's tickets |
| POST | `/api/tickets` | Purchase ticket |
| POST | `/api/tickets/guest-initiate-payment` | Guest payment initiation |
| GET | `/api/tickets/<id>` | Get ticket details |
| GET | `/api/tickets/download/<id>` | Download ticket PDF |
| POST | `/api/tickets/confirm-payment` | Confirm payment |
| POST | `/api/tickets/<id>/use` | Use ticket (scan QR) |

### M-Pesa Payments (`/api/mpesa`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/mpesa/stk-push` | Initiate STK Push |
| GET | `/api/mpesa/status/<transaction_id>` | Check payment status |
| POST | `/api/mpesa/simulate-complete/<transaction_id>` | Simulate payment completion (sandbox) |
| POST | `/api/mpesa/callback` | M-Pesa callback URL |

### Users (`/api/users`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/users/profile` | Get user profile |
| PUT | `/api/users/profile` | Update profile |
| PUT | `/api/users/password` | Change password |
| GET | `/api/users/saved-events` | Get saved events |
| GET | `/api/users/organized-events` | Get organized events |

### Analytics (`/api/analytics`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/analytics/organizer` | Organizer analytics |
| GET | `/api/analytics/event/<id>` | Event-specific analytics |
| GET | `/api/analytics/platform` | Platform-wide analytics |

### Moderation (`/api/moderation`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/moderation/pending` | List pending events |
| POST | `/api/moderation/<id>/approve` | Approve event |
| POST | `/api/moderation/<id>/reject` | Reject event |

### Reviews (`/api/reviews`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/reviews/<event_id>` | Add review |
| GET | `/api/reviews/<event_id>` | Get event reviews |

### Export (`/api/export`)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/export/event/<id>/attendees` | Export attendee list |

---

## 💳 M-Pesa Integration

The platform integrates with M-Pesa for mobile payments in Kenya.

### Setup
1. Configure M-Pesa credentials in `.env`:
   ```
   MPESA_CONSUMER_KEY=your_consumer_key
   MPESA_CONSUMER_SECRET=your_consumer_secret
   MPESA_BUSINESS_SHORT_CODE=your_short_code
   MPESA_PASSKEY=your_passkey
   ```

### Payment Flow
1. User selects ticket and enters phone number
2. Backend initiates STK Push to user's phone
3. User enters PIN on their phone
4. M-Pesa processes payment and sends callback
5. Backend confirms payment and activates ticket

### Sandbox Testing
Use the simulation endpoints for testing:
- `POST /api/mpesa/simulate-complete/<transaction_id>`

---

## 📧 Email Service

The system sends transactional emails for:
- Email verification
- Password reset
- Ticket confirmation
- Payment receipts

Configure email in `.env`:
```
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password
```

---

## 🧪 Testing

```bash
# Run all tests
pipenv run python -m pytest

# Run specific test file
pipenv run python test_endpoints.py
```

---

## 🔧 Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key | dev-secret-key |
| `DATABASE_URL` | Database connection URL | sqlite:///eventhub.db |
| `JWT_SECRET_KEY` | JWT signing key | jwt-secret-key |
| `JWT_ACCESS_TOKEN_EXPIRES` | Token expiry in seconds | 3600 |
| `FRONTEND_URL` | Frontend URL | http://localhost:5173 |
| `MAIL_*` | Email configuration | See above |
| `MPESA_*` | M-Pesa configuration | See above |

---

## 📝 Database Models

### User
- `id`, `email`, `password_hash`, `name`, `phone`, `role`, `is_active`, `is_verified`

### Event
- `id`, `title`, `description`, `venue`, `city`, `start_date`, `end_date`, `status`, `organizer_id`

### Ticket
- `id`, `ticket_number`, `event_id`, `user_id`, `quantity`, `total_price`, `payment_status`, `qr_code`

### MpesaTransaction
- `id`, `user_id`, `event_id`, `amount`, `phone_number`, `transaction_id`, `status`

---

## 🔐 Authentication

The API uses JWT (JSON Web Tokens) for authentication.

Include the token in the Authorization header:
```
Authorization: Bearer <your_token>
```

Roles:
- **attendee** - Regular users who can browse and purchase tickets
- **organizer** - Users who can create and manage events
- **moderator** - Users who can moderate events
- **admin** - Platform administrators

---

## 📄 License

MIT License
