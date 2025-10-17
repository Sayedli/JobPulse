# JobPulse

JobPulse is a Django web app that monitors the [Simplify Jobs – New Grad Positions](https://github.com/SimplifyJobs/New-Grad-Positions) feed, prepares tailored application materials with LLM assistance, and tracks submissions on a NeuralField-inspired dashboard.

## Highlights
- Normalises the Simplify Jobs README into a local datastore with periodic refresh support.
- Authenticated dashboard so each user maintains their own applications, checklists, resume variants, and cover letters.
- Per-application history surfaces every tailored resume and cover letter version with quick downloads.
- Tailor resumes and cover letters via a pluggable LLM layer (OpenAI by default) with graceful fallbacks when keys are absent.
- Upload PDF resumes directly; JobPulse extracts the text, archives the source, and outputs tailored PDFs ready to download.
- On-demand job descriptions pulled from the original application link give additional context alongside Simplify notes.
- Cover letters are generated as polished PDFs with downloadable history per application.
- Experimental Selenium automation opens application portals behind explicit consent, logging every attempt.
- Containerised deployment with Docker + Gunicorn, styled using `static/css/neuralfield.css` to match the NeuralField aesthetic.

## Getting Started (Dev)
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py fetch_jobs   # pulls the latest Simplify listings
python manage.py runserver
```

- Visit http://localhost:8000/ and create an account (or run `python manage.py createsuperuser`).
- Tailored resumes are saved as PDFs under `generated/resumes/<user_id>/` (the uploaded source PDF remains in `source/`).
- Cover letters are generated as PDFs and linked per application for quick download.

## LLM Configuration
- Install dependencies (already covered by `requirements.txt`).
- Provide an API key, e.g.:
  ```bash
  export OPENAI_API_KEY="sk-..."
  export LLM_MODEL="gpt-4o-mini"
  ```
- Without credentials, JobPulse falls back to deterministic templates so development remains frictionless.

## Auto-Apply Automation (Selenium)
- Disabled by default: set `AUTO_APPLY_ENABLED=true` only when you are ready.
- WebDriver options:
  1. **Remote grid** – set `WEBDRIVER_REMOTE_URL` to a Selenium Grid / Browserless endpoint.
  2. **Local** – ensure Chrome/Chromium or Firefox libraries exist; `webdriver-manager` will fetch the driver binary automatically.
- The current implementation opens the application URL and records the attempt. Extend `applications/services/auto_apply.py` with company-specific scripts for full automation.

## Docker Workflow
```bash
cp .env.docker.example .env.docker
docker compose up --build
# App available on http://localhost:8000
```

The entrypoint handles migrations, static collection, job ingestion, and then boots Gunicorn. Update `.env.docker` with OpenAI keys, automation toggles, and database credentials. The provided Compose file spins up Postgres 16 and mounts the project directory for rapid iteration.

## Management Commands
- `python manage.py fetch_jobs [--url <override>]` – syncs jobs from the Simplify Jobs README (master branch by default).

## Project Layout
- `applications/` – domain models, services (LLM, automation, ingestion), views, and management commands.
- `accounts/` – lightweight auth flows (login, logout, signup).
- `templates/` & `static/css/neuralfield.css` – NeuralField themed UI components.
- `docs/` – design notes including `docs/architecture.md`.

## Contributing Workflow (Example PR)
1. Create a feature branch: `git checkout -b docs/contributing-notes`.
2. Make a focused change (documentation tweak, bug fix, etc.).
3. Run tests or linters if relevant (skip for docs-only updates).
4. Stage and commit: `git add README.md && git commit -m "docs: add contributing workflow"`.
5. Push: `git push origin docs/contributing-notes`.
6. Open a pull request with a concise summary and supporting context/screenshots.

## Roadmap
- Add additional job sources (Lever/Greenhouse feeds, company-specific scrapers).
- Persist automation credentials per site and implement scripted form submissions.
- Provide reminders/calendar sync for interviews and follow-ups.
