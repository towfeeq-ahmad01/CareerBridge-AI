# API reference

All responses are JSON. Protected endpoints require a signed-in session. Mutating
requests require a CSRF token from `GET /api/csrf-token` in the
`X-CSRFToken` header. The normal HTML forms include the same token automatically.

| Method and path | Access | Purpose |
|---|---|---|
| `GET /api/csrf-token` | Public | Get a CSRF token for browser/API requests |
| `POST /api/auth/register` | Public | JSON `{"full_name":"...","email":"...","password":"..."}` |
| `POST /api/auth/login` | Public | JSON `{"email":"...","password":"..."}` |
| `POST /api/auth/logout` | Student | End the current session |
| `GET /api/auth/me` | Student | Return the current account |
| `GET /api/jobs?q=python` | Public | Search active job listings |
| `GET /api/internships?q=data` | Public | Search active internships |
| `GET /api/recommendations` | Student | Rank jobs and internships for the current profile |
| `POST /api/skill-gap` | Student | JSON `{"required_skills":"Python, SQL"}`; compare recognized skills |
| `GET /api/applications` | Student | List the current user's tracked applications |
| `POST /api/applications` | Student | JSON `{"type":"job","opportunity_id":1}`; track a listing |
| `POST /api/resume-analysis` | Student | JSON `{"text":"..."}`; analyze pasted resume text |
| `GET /api/admin/stats` | Admin | Aggregate platform counts |

Recommendation `match_percent` is a deterministic hybrid: 70% required-skill
overlap and 30% TF-IDF cosine similarity (scikit-learn). It is not a hiring
probability. Resume score and interview feedback are transparent rule-based
checks; neither uses a trained model.
