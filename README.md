# P2P Kilo Sales Platform Backend

A Django REST Framework backend for the P2P Kilo Sales platform, connecting travelers with package senders.

## Features

- User Authentication (Email/Password, Google, Apple)
- Profile Management with Identity Verification
- Travel Listings
- Package Requests
- Messaging System
- Admin Dashboard

## Setup Instructions

1. Clone the repository:
```bash
git clone <repository-url>
cd p2pkilosales_backend
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root with the following variables:
```env
# Django settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database settings
DB_NAME=p2pkilosales
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=localhost
DB_PORT=5432

# Email settings
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-specific-password

# OAuth2 settings
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
APPLE_CLIENT_ID=your-apple-client-id
APPLE_CLIENT_SECRET=your-apple-client-secret

# CORS settings
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

5. Set up the database:
```bash
python manage.py migrate
```

6. Create a superuser:
```bash
python manage.py createsuperuser
```

7. Run the development server:
```bash
python manage.py runserver
```

## API Endpoints

### Authentication
- `POST /api/users/token/` - Get JWT token
- `POST /api/users/token/refresh/` - Refresh JWT token
- `POST /api/users/users/register/` - Register new user
- `POST /api/users/users/verify-otp/` - Verify OTP
- `POST /api/users/users/resend-otp/` - Resend OTP
- `POST /api/users/users/forgot-password/` - Request password reset
- `POST /api/users/users/change-password/` - Change password

### User Profile
- `GET /api/users/users/me/` - Get current user profile
- `PUT /api/users/profile/` - Update profile
- `POST /api/users/users/accept-privacy-policy/` - Accept privacy policy

## Development

### Running Tests
```bash
python manage.py test
```

### Code Style
The project follows PEP 8 style guide. Use black for code formatting:
```bash
black .
```

## Deployment

1. Set `DEBUG=False` in `.env`
2. Update `ALLOWED_HOSTS` with your domain
3. Set up a production database
4. Configure email settings
5. Set up OAuth2 credentials
6. Run migrations
7. Collect static files:
```bash
python manage.py collectstatic
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request
