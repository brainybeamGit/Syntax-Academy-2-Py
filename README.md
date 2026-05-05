## Syntax Academy 2

**Project Description**

Syntax Academy 2 is a Django-based e-learning platform that provides courses, quizzes, lessons, and enrolment/payment flows for students.

### Project Features

- **Course management:** Create and manage courses with lessons and notes.
- **User registration:** Students can register and enroll in courses.
- **Quizzes & results:** Course quizzes with scoring and results.

### Setup Commands

```bash
# Clone the repository
git clone [repo-url]

# Navigate to project directory
cd [project-name]
ls  # Verify manage.py is present

# Create virtual environment (macOS/Linux)
python3 -m venv .venv

# Activate virtual environment (macOS/Linux)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
python manage.py migrate

# Run seeds.py file to populate database
python manage.py shell < seeds.py

# Run development server
python manage.py runserver
```

### Default Server

- **Local Server:** `http://localhost:8000`

### Screenshots

- 1. Home Page
- 2. [Add more screenshots]

Images (rendered on GitHub):

![Home Page](screenshot/home.png)

![Dashboard](screenshot/dashboard.png)

![Courses](screenshot/courses.png)
# Syntax Academy

Syntax Academy is a Django-based online learning platform demo. It includes a public course catalog, student registration and login, lesson streaming, notes downloads, quizzes, certificates, payment-ready enrollment flows, and a separate admin dashboard for managing content and learner activity.

## Features

- Public home page with featured courses and learner reviews
- Student registration, login, profile, password reset, and course enrollment flows
- Lesson video streaming, downloadable notes, quiz attempts, receipts, and certificates
- Admin dashboard for students, courses, lessons, notes, quizzes, results, reviews, comments, and contacts
- Fresh demo-data seeding for a public-safe local setup
- Environment-based configuration for secrets, email, database path, and Razorpay credentials

## Installation

These steps assume you are starting from zero.

1. Install Python 3.14 on your machine.
2. Open a terminal in this project folder.
3. Create a virtual environment:

```bash
python3.14 -m venv .venv
```

4. Activate it:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

5. Install the project dependencies:

```bash
pip install -r requirements.txt
```

## Environment Setup

1. Copy the sample environment file:

```bash
cp .env.sample .env
```

2. Edit `.env` if you want custom settings.

Important values:

- `DJANGO_SECRET_KEY`: set your own secret for real deployments
- `DJANGO_DEBUG`: use `False` outside local development
- `DJANGO_ALLOWED_HOSTS`: comma-separated hostnames
- `DJANGO_DB_PATH`: lets you store the SQLite database somewhere else if needed
- `EMAIL_BACKEND`: defaults to console output for local development
- `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET`: leave blank if you do not want payment checkout enabled locally

## Database and Demo Setup

1. Run migrations:

```bash
python manage.py migrate
```

2. Load fresh demo data:

```bash
python manage.py seed_demo_data --fresh
```

This command creates:

- demo courses
- lessons, notes, quizzes, reviews, comments, and results
- a default admin user
- a demo student account

Default admin dashboard login:

- Username: `admin`
- Email: `admin@admin.com`
- Password: `admin`

Demo student login:

- Email: `ava@example.com`
- Password: `demo123!`

## Running the Project

Start the development server:

```bash
python manage.py runserver
```

Then open:

- Student site: `http://127.0.0.1:8000/`
- Admin dashboard: `http://127.0.0.1:8000/admin-dashboard/login/`
- Django admin: `http://127.0.0.1:8000/admin/`

## Creating an Admin User

If you do not want to use the built-in demo admin, create your own:

```bash
python manage.py createsuperuser
```

For this project's default demo setup, the seeded admin credentials are:

- Username: `admin`
- Email: `admin@admin.com`
- Password: `admin`

## How to Use the Project

1. Open the home page and browse available courses.
2. Register a new student account or use the demo student login.
3. Enroll in a course.
4. Watch lessons and download notes.
5. Complete all lessons, take the quiz, and unlock the certificate.
6. Sign in to the admin dashboard to manage courses, students, quizzes, and contact messages.

## Troubleshooting

- `ModuleNotFoundError`: make sure the virtual environment is active and run `pip install -r requirements.txt` again.
- `Port already in use`: stop the process using port `8000` or run `python manage.py runserver 8001`.
- `No such table` or migration errors: run `python manage.py migrate`.
- Demo pages look empty: run `python manage.py seed_demo_data --fresh`.
- Emails are not sent: local development uses the console email backend by default, so messages appear in the terminal.
- Payments do not start: add valid `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` values in `.env`.

## Screenshots

### Homepage

![Syntax Academy Homepage](images/screencapture-127-0-0-1-8123-2026-04-09-16_53_05.png)

### Course Catalog

![Syntax Academy All Courses](images/screencapture-127-0-0-1-8123-all-courses-2026-04-09-16_53_58.png)

### Admin Dashboard

![Syntax Academy Admin Dashboard](images/screencapture-127-0-0-1-8123-admin-dashboard-2026-04-09-16_57_42.png)
