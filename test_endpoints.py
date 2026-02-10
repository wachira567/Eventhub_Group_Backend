"""Test the backend endpoints"""

from app import create_app
from models import db, User, UserRole, Event, Category, TicketTypeModel, Ticket

app = create_app()

with app.app_context():
    # Create test client
    client = app.test_client()
    
    # Test 1: Get user tickets (no auth)
    print("\n=== Test 1: GET /api/tickets/my-tickets (no auth) ===")
    response = client.get('/api/tickets/my-tickets')
    print(f"Status: {response.status_code}")
    print(f"Response: {response.get_json()}")
    
    # Test 2: Login and get token
    print("\n=== Test 2: POST /api/auth/login ===")
    response = client.post('/api/auth/login', json={
        'email': 'test@example.com',
        'password': 'password123'
    })
    if response.status_code == 200:
        token = response.get_json().get('access_token')
        print(f"Login successful, token: {token[:20]}...")
    else:
        print(f"Login failed: {response.get_json()}")
        token = None
    
    if token:
        headers = {'Authorization': f'Bearer {token}'}
        
        # Test 3: Get my tickets
        print("\n=== Test 3: GET /api/tickets/my-tickets (with auth) ===")
        response = client.get('/api/tickets/my-tickets', headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.get_json()}")
        
        # Test 4: Get all tickets (admin)
        print("\n=== Test 4: GET /api/tickets (admin) ===")
        response = client.get('/api/tickets', headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.get_json()}")
        
        # Test 5: Get saved events
        print("\n=== Test 5: GET /api/events/saved ===")
        response = client.get('/api/events/saved', headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.get_json()}")
        
        # Test 6: Update profile
        print("\n=== Test 6: PUT /api/auth/profile ===")
        response = client.put('/api/auth/profile', json={
            'name': 'Updated Name'
        }, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.get_json()}")
    
    print("\n=== All tests completed ===")
