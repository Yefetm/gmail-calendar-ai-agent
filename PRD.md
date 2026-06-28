# PRD — Gmail & Calendar AI Agent

## Product Name
Gmail & Calendar AI Agent

## Goal
Build an AI-based agent that connects Gmail and Google Calendar. The agent should scan recent emails, detect meeting requests written in free text, extract meeting information, check availability, and respond accordingly.

## Target User
A student or knowledge worker who receives meeting requests by email and wants automated calendar management.

## Problem
Meeting requests often arrive in unstructured email text. The user needs to manually read the email, understand the requested time, check calendar availability, and create an event or reply that the time is unavailable.

## Solution
The agent automates the process:
1. Reads recent Gmail messages.
2. Detects meeting invitations.
3. Extracts meeting details.
4. Checks Google Calendar availability.
5. Creates a calendar event if available.
6. Creates an unavailable response draft if busy.

## Functional Requirements
| ID | Requirement | Status |
|---|---|---|
| FR1 | Authenticate with Google OAuth | Done |
| FR2 | Connect to Gmail API | Done |
| FR3 | Connect to Calendar API | Done |
| FR4 | Scan emails from the last two days | Implemented |
| FR5 | Identify meeting requests | Implemented, rule-based |
| FR6 | Extract date/time/location/participants | Implemented, basic regex |
| FR7 | Check calendar availability | Implemented |
| FR8 | Create calendar event if free | Implemented |
| FR9 | Create reply draft if busy | Implemented |
| FR10 | Add LLM-based extraction | Future improvement |

## Non-Functional Requirements
- Secure authentication using token-based OAuth.
- Do not expose client secrets or tokens.
- Clear README for reproduction.
- Project should run with `uv run main.py`.

## Success Criteria
- Running the project scans Gmail.
- At least one meeting email is detected.
- Calendar free/busy is checked.
- Event or draft response is created.
