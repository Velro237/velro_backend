# xy Platform Backend

Django + DRF backend for a two-sided luggage/package exchange platform.

## Features
- JWT & OAuth2 authentication
- Modular app structure (users, listings, bookings, messaging)
- PostgreSQL database
- Ready for Docker/Render deployment

## Setup
1. Create and activate a virtual environment
2. Install dependencies: `pip install -r requirements.txt`
3. Configure `.env` with your secrets and DB info
4. Run migrations: `python manage.py migrate`
5. Start the server: `python manage.py runserver`
