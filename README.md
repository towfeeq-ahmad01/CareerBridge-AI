# CareerBridge AI

CareerBridge AI is a student-focused career and internship platform built with
Flask, MySQL-compatible relational models, and explainable machine-learning
recommendations. It brings profile building, opportunity discovery, resume
feedback, interview practice, skill-gap analysis, and application tracking into
one responsive application.

> **Scope note:** This is a complete college-project implementation with starter
> catalog data. It does not connect to third-party job boards, send applications
> to employers, or claim a live deployment. Add real listings and your own
> production database before launch.

## Features

- Password-hashed registration and login, signed sessions, CSRF protection,
  student/admin authorization, and profile editing.
- Searchable jobs and internships, skill-aware recommendations, saved listings,
  and application status/notes tracking.
- PDF resume text extraction and skill detection. Suggestions and the
  0–100 completeness indicator use transparent keyword, section, and word-count
  rules; they are not predictive hiring scores.
- Skill-gap comparison against the bundled skills catalog and a progress-
  trackable learning roadmap.
- Technical and HR interview question bank with saved responses and
  rule-based STAR/answer-structure feedback (not factual grading).
- Admin dashboard for account role management, listing creation/visibility, and
  platform totals.
- JSON APIs, MySQL schema, repeatable sample catalog seeding, and a Render-ready
  Gunicorn entry point.

## Recommendation algorithm

Recommendations are deterministic, not random. For each job or internship:

1. Calculate the fraction of required catalog skills found in the student's
   profile.
2. Calculate TF-IDF cosine similarity with scikit-learn between profile text
   and opportunity title/category/description.
3. Combine them as **70% skill overlap + 30% text similarity**, clamp to 0–100,
   and show matched/missing skills with an explanation.

This is a portfolio-project ranking aid, not an employment probability.
Resume scoring and interview-answer feedback are rule-based rather than ML.

## Important files

| File/folder | Purpose |
|---|---|
| `app.py` | WSGI entry point (`app`) and local development runner |
| `config.py`, `.env.example` | Environment-based secrets, database, upload, and cookie settings |
| `backend/__init__.py` | App factory, extensions, database CLI commands |
| `backend/models.py` | Relational SQLAlchemy models and foreign-key relationships |
| `backend/routes.py` | HTML pages, authentication, validation, and JSON API endpoints |
| `backend/seed.py` | Repeatable sample jobs, internships, skills, and interview questions |
| `models/career_ai.py` | Skill extraction, resume checks, TF-IDF matching, and feedback logic |
| `templates/` | Server-rendered page templates |
| `static/` | Responsive CSS and small browser-side form enhancements |
| `frontend/README.md` | Frontend asset layout and serving note |
| `database/schema.sql` | Additive MySQL 8+ schema (does not drop existing tables) |
| `documentation/API.md` | API paths, access levels, and CSRF usage |
| `tests/test_app.py` | Registration, authorization, recommendation, tracking, and validation tests |
| `uploads/` | Private PDF upload storage; excluded from Git |

## Requirements

- Python 3.10+ (developed with Python 3.11)
- MySQL 8+ for MySQL deployments; SQLite is the local no-configuration demo
  default.
- A modern browser. Bootstrap 5 is loaded from jsDelivr; custom styles are local.

## Run locally (Windows PowerShell)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set a unique `SECRET_KEY` in `.env`. For a quick local demo, leave
`DATABASE_URL` empty to use `instance/careerbridge.db` (SQLite). Initialize
tables and starter listings, then run:

```powershell
flask --app app init-db
flask --app app run --debug
```

Open `http://127.0.0.1:5000`. Register a student account normally. To create an
administrator, use the protected CLI password prompt:

```powershell
flask --app app create-admin admin@your-domain.test
```

Or promote an existing user:

```powershell
flask --app app make-admin student@your-domain.test
```

The CLI commands must use the same environment/database as the running server.
`init-db` creates missing tables and adds starter catalog rows without deleting
existing records. SQLAlchemy `create_all` is not a schema migration system: if
you already have tables with different columns, inspect and back up that
database, then plan a migration before running against it.

## MySQL setup

Create a dedicated database and least-privilege application user in MySQL,
then set a URL in `.env`:

```dotenv
DATABASE_URL=mysql+pymysql://careerbridge:URL_ENCODED_PASSWORD@localhost:3306/careerbridge?charset=utf8mb4
SECRET_KEY=use-a-long-random-secret
```

Use your database provider's TLS connection parameters when required. Do not
commit `.env`, passwords, or real resume files. The schema file is additive and
can be applied to a newly selected database:

```powershell
mysql -u careerbridge -p careerbridge < database\schema.sql
```

Alternatively, `flask --app app init-db` creates the same tables using the
application models and then seeds the catalog. **Inspect an existing database
before applying any schema changes**; the supplied workspace contained no SQL
or database files at implementation time.

## Tests

The test suite uses an isolated in-memory SQLite database and does not connect
to or modify your development database:

```powershell
python -m unittest discover -s tests -v
```

Resume tests cover input validation and text-analysis API behavior. To manually
exercise PDF extraction, upload a small, text-based PDF from the Resume Analyzer
page. Image-only/scanned PDFs are reported as unsupported.

## API

See [documentation/API.md](documentation/API.md). Browser/API state-changing
requests must send the CSRF token from `GET /api/csrf-token` in
`X-CSRFToken`. The REST surface includes job and internship search,
recommendations, skill gaps, resume text analysis, application tracking, and
admin statistics.

## Render deployment

1. Push the project to a private or public GitHub repository without `.env`,
   uploads, or database dumps.
2. Create a Render Web Service connected to that repository.
3. Set **Build Command** to `pip install -r requirements.txt`.
4. Set **Start Command** to `gunicorn app:app`.
5. Configure `SECRET_KEY`, `DATABASE_URL`, and `FLASK_ENV=production` in
   Render's environment settings.
6. Provision a MySQL-compatible database (Render does not provide a native
   managed MySQL service); use a trusted external provider, TLS, a dedicated
   user, and the provider's private connection URL when available.
7. Initialize the schema and sample catalog once with
   `flask --app app init-db` in an environment using the production database,
   then create an administrator with `flask --app app create-admin EMAIL`.
8. Configure a health check path of `/healthz`. It returns success only when
   the database responds.

The web process's local filesystem is ephemeral on typical Render services.
Uploads are stored outside the static directory but will not be durable across
deploys/restarts; use private persistent object storage before accepting
production resumes. This repository has not been deployed and no live URL is
claimed.

## Screenshots

Add your own screenshots here after running the application locally, for
example:

- Home and opportunity search
- Student dashboard and recommendations
- Resume feedback and learning roadmap
- Application tracker and admin dashboard
