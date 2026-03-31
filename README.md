# Rendi Backend — Django REST API

Readiness scoring backend for the Rendi home-buying MVP.  
Stack: **Django 5 · Django REST Framework · SimpleJWT · PostgreSQL**

---

## Project Structure

```
rendi_backend/
├── manage.py
├── requirements.txt
├── .env.example
├── rendi_backend/          # Django project config
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── apps/
│   ├── users/              # Custom user model + JWT auth
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   └── apps.py
│   └── assessments/        # Scoring engine + assessment records
│       ├── rendi_scoring.py   ← core business logic (no Django dependencies)
│       ├── models.py
│       ├── serializers.py
│       ├── views.py
│       ├── urls.py
│       ├── admin.py
│       └── apps.py
└── tests/
    └── test_scoring.py
```

---

## Setup

### 1. Clone & create virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```env
SECRET_KEY=your-very-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=rendi_db
DB_USER=rendi_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432

CORS_ALLOWED_ORIGINS=http://localhost:3000
ACCESS_TOKEN_LIFETIME_MINUTES=60
REFRESH_TOKEN_LIFETIME_DAYS=7
```

### 3. Create the PostgreSQL database

```bash
psql -U postgres
CREATE DATABASE rendi_db;
CREATE USER rendi_user WITH PASSWORD 'your_db_password';
GRANT ALL PRIVILEGES ON DATABASE rendi_db TO rendi_user;
\q
```

### 4. Run migrations

```bash
python manage.py migrate
```

### 5. Create a superuser (for Django admin)

```bash
python manage.py createsuperuser
```

### 6. Run the development server

```bash
python manage.py runserver
```

API is now live at `http://localhost:8000`  
Admin panel at `http://localhost:8000/admin/`

---

## API Endpoints

### Auth

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| POST | `/api/auth/register/` | None | Create account |
| POST | `/api/auth/login/` | None | Get access + refresh tokens |
| POST | `/api/auth/token/refresh/` | None | Refresh access token |
| GET | `/api/auth/profile/` | Bearer | Get user profile |
| PATCH | `/api/auth/profile/` | Bearer | Update name |
| POST | `/api/auth/change-password/` | Bearer | Change password |

### Assessments

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| POST | `/api/assessments/submit/` | Bearer | Run scoring & save result |
| GET | `/api/assessments/latest/` | Bearer | Get most recent assessment |
| GET | `/api/assessments/history/` | Bearer | Get all past assessments |
| GET | `/api/assessments/<id>/` | Bearer | Get single assessment detail |

---

## Example Requests

### Register
```json
POST /api/auth/register/
{
  "email": "jane@example.com",
  "first_name": "Jane",
  "last_name": "Doe",
  "password": "SecurePass123!",
  "password_confirm": "SecurePass123!"
}
```

### Login
```json
POST /api/auth/login/
{
  "email": "jane@example.com",
  "password": "SecurePass123!"
}
```
Response includes `access`, `refresh`, and `user` fields.

### Submit Assessment
```json
POST /api/assessments/submit/
Authorization: Bearer <access_token>

{
  "annual_income": 55000,
  "savings": 22000,
  "target_property_price": 280000,
  "monthly_commitments": 350,
  "has_ccj": false,
  "has_missed_payments": false
}
```

Optional fields: `monthly_commitments`, `has_ccj`, `has_missed_payments`  
(omit them or pass `null` — neutral scores are applied automatically)

### Example Response
```json
{
  "disclaimer": "This is an estimate for information only. It is not financial advice, a mortgage offer, or an eligibility decision.",
  "assessment": {
    "id": 1,
    "score": 55,
    "status": "Getting closer",
    "time_estimate": "Likely 6–18 months away",
    "deposit_needed": 28000,
    "deposit_gap": 6000,
    "estimated_months": 16,
    "breakdown": {
      "deposit": { "points": 15, "max_points": 40, "label": "Needs attention", "value": 7.86 },
      "income":  { "points": 15, "max_points": 30, "label": "Needs attention", "value": 5.09 },
      "commitments": { "points": 15, "max_points": 20, "label": "Okay", "value": 7.64 },
      "credit": { "points": 10, "max_points": 10, "label": "Low impact", "value": -1 }
    },
    "action_plan": [
      "Consider building your deposit over time to strengthen your position.",
      "Consider reviewing your target budget or extending your timeframe based on what you entered.",
      "You can revisit this estimate as your situation changes."
    ],
    "created_at": "2025-01-15T10:23:45Z"
  }
}
```

---

## Running Tests

```bash
python manage.py test tests
```

Tests cover all scoring components, edge cases, status thresholds, deposit helpers, and the disclaimer/action plan guardrails.

---

## Next.js Integration Notes

- Set `Authorization: Bearer <access_token>` header on all protected requests
- Use `POST /api/auth/token/refresh/` with the `refresh` token to silently renew the access token when it expires
- All monetary values are strings in the API response (Django's `DecimalField` serialises as string) — parse with `parseFloat()` on the frontend
- The `breakdown` object is always present and has exactly 4 keys: `deposit`, `income`, `commitments`, `credit`

---

## Scoring Logic Summary

| Component | Max Points | Key Input |
|-----------|-----------|-----------|
| Deposit strength | 40 | `savings / target_property_price` |
| Income vs price | 30 | `target_property_price / annual_income` |
| Commitments | 20 | `monthly_commitments / monthly_income` |
| Credit profile | 10 | `has_ccj`, `has_missed_payments` |

**Status thresholds:** 0–39 = Early stages · 40–69 = Getting closer · 70–100 = Nearly ready

All outputs are informational estimates only. Not financial advice.
