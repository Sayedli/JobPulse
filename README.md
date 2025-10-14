# JobPulse

JobPulse is a Django web app that monitors the [Simplify Jobs – New Grad Positions](https://github.com/SimplifyJobs/New-Grad-Positions) feed, prepares tailored application materials, and tracks submission progress with a NeuralField-inspired dashboard.

## Highlights
- Parse the upstream Simplify Jobs README and normalise listings into a local database.
- Spin up an application pipeline per role with checklist tracking, resume tailoring stubs, and cover letter drafts.
- Neon glassmorphism UI powered by `static/css/neuralfield.css` to mirror the expected NeuralField styling.
- Containerised runtime via Docker/Gunicorn with optional Postgres backing store.

## Getting Started (Dev)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py fetch_jobs   # pulls the latest Simplify listings
python manage.py runserver
```

- Access the dashboard at http://localhost:8000/.
- Tailored resumes are written to `generated/resumes/` (replace `data/resume_base.txt` with your real resume text).
- Cover letters are stored on the associated `Application` record for quick review.

## Docker Workflow
```bash
docker compose up --build
# App available on http://localhost:8000
```

The `entrypoint.sh` script runs migrations, collects static files, hydrates job listings, and then serves Gunicorn. Edit `.env.docker` to adjust secrets or database credentials. The default compose file provisions a Postgres 16 instance and mounts the project for rapid iteration.

## Management Commands
- `python manage.py fetch_jobs [--url <override>]` – syncs jobs from Simplify Jobs (defaults to the master branch README).

## Project Layout
- `applications/` – core app (models, services, views, management commands).
- `templates/` & `static/css/neuralfield.css` – NeuralField themed dashboard UI.
- `docs/architecture.md` – architecture notes and future considerations.

## Next Steps
- Integrate a true auto-apply automation path (Selenium/API) gated behind explicit consent.
- Swap resume/cover letter stubs for an LLM-powered content generator.
- Expand the dashboard with filters, metrics, and reminders.
