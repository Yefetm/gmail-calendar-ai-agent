# PLAN — Gmail & Calendar AI Agent

## Phase 1 — Google Setup
- Create Google Cloud project.
- Enable Gmail API.
- Enable Google Calendar API.
- Configure OAuth consent screen.
- Create Desktop OAuth client.
- Download credentials file.
- Add test user.

## Phase 2 — Local Python Setup
- Install uv.
- Create project folder.
- Add pyproject.toml.
- Add main.py.
- Run uv sync.

## Phase 3 — API Connectivity Test
- Create Gmail draft.
- Create Google Calendar event.
- Confirm token.json creation.

## Phase 4 — Agent Workflow
- Read emails from the last two days.
- Detect potential meeting requests.
- Extract meeting details.
- Check Google Calendar availability.
- Create event if available.
- Create response draft if busy.

## Phase 5 — Submission Preparation
- Create README.md.
- Create PRD.md.
- Create PLAN.md.
- Create TODO.md.
- Add Skill file.
- Add screenshots.
- Push to public GitHub repository without secrets.
- Submit PDF in Moodle with student names and GitHub link.
