# JobPulse Architecture Notes

## Goals
- Aggregate new-grad software engineering roles from the Simplify Jobs listing on GitHub.
- Support semi-automated job applications: capture job details, tailor resume snippets, generate cover letters, and log application submissions.
- Provide a dashboard with NeuralField-inspired styling to review job pipelines and checklist progress.
- Package the app for local development and containerized deployment via Docker.

## High-Level Architecture
- **Django project (`jobpulse`)**  
  - REST-ish views served via Django + Django templates for the dashboard.  
  - Core app (`applications`) owns job sources, resumes, and application workflow.
- **Periodic ingestion service** to pull job data from Simplify Jobs repository (initially via GitHub raw file fetch + parser).  
  - Future extension: switch to GitHub API or GraphQL for incremental updates.
- **Domain services** for resume tailoring and cover letter generation (initial stub uses templated text with placeholders; later swap for LLM/Resume tailoring microservice).
- **Frontend** uses Django Template Language + Tailwind-style utility classes adapted to "NeuralField" palette/components (will codify in `static/css/neuralfield.css`).
- **Persistence** via SQLite for development, easily swappable to Postgres in Docker.
- **Task queue (future)**: placeholder interface for asynchronous application submissions; initial implementation synchronous to avoid over-engineering.

## Data Model (initial draft)
- `JobSource` – tracks the upstream feed (e.g., SimplifyJobs New Grad list).
- `JobPosting` – normalized information about a single job (title, company, location, requirements, application link, scraped description, status flags).
- `ResumeVariant` – stores tailored resume renderings with metadata (target role, generated_at, file path/reference).
- `Application` – links `JobPosting` with submission metadata (status, applied_on, cover letter path, checklist booleans).
- `ChecklistItem` – optional checklist template per application (e.g., Resume tailored, Cover letter generated, Submitted).

## Key Flows
1. **Job ingestion**  
   `management/commands/fetch_jobs.py` pulls README from SimplifyJobs repo, parses markdown tables, populates `JobPosting`.  
2. **Application prep**  
   On selecting a job, user can request resume tailoring (stub calls `services.resume.tailor_resume(job_posting, base_resume)` which returns text and stores PDF path placeholder).  
   Cover letter generator uses `services.cover_letter.generate_cover_letter(job_posting, user_profile)`.  
3. **Dashboard**  
   Django view renders aggregated pipeline (New, In Progress, Submitted) with interactive checklist toggles (AJAX endpoints for `POST /applications/{id}/checklist`).
4. **Auto-apply (initial stub)**  
   Provide manual link to application plus notes; real automation flagged as future enhancement due to captcha/legal concerns.

## Frontend Styling
- Create a `neuralfield.css` file inspired by user's prior work (gradient backgrounds, glassmorphism cards, neon accent).
- Use Alpine.js or lightweight vanilla JS for interactivity (checklist toggles, modal forms) to keep dependencies minimal.
- Layout: left navigation (pipeline filters), right main panel with cards per job, modals for resume/cover letters.

## Docker & Deployment
- Base image: `python:3.12-slim`.
- Install Node (lightweight) only if Tailwind build needed; otherwise precompiled CSS.  
- Use `docker-compose.yml` for dev: `web` service (Django + gunicorn) + `db` (Postgres).  
- Provide `entrypoint.sh` to run migrations and start server.

## Open Questions
- Where to source resume base file? Placeholder path `data/resume_base.docx`.
- Determine actual "NeuralField" design tokens—need clarification or existing assets.
- Decide on third-party services for real auto-apply workflow (Selenium? APIs?). Start with logging manual submissions.

