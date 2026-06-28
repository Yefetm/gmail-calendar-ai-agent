# Gmail Calendar Agent Skill

## Purpose
This skill defines how the Gmail & Calendar Agent should handle meeting requests received by email.

## Inputs
- Recent Gmail messages.
- Google Calendar availability.
- User email address.

## Workflow
1. Scan Gmail messages from the last two days.
2. For each email, determine if it is a meeting request.
3. If it is not a meeting request, ignore it.
4. If it is a meeting request, extract:
   - Meeting title
   - Date
   - Time
   - Location
   - Participants
5. Check Google Calendar availability.
6. If free, create a calendar event.
7. If busy, create a Gmail reply draft saying the user is unavailable.

## Decision Rules
- Date and time are mandatory fields for automatic event creation.
- If date or time is missing, the system should skip automatic event creation.
- If calendar is busy, the system should not create a duplicate event.
- Secrets must never be printed or uploaded.

## Future Improvement
Replace the rule-based extraction with an LLM prompt that returns structured JSON:
```json
{
  "is_meeting": true,
  "title": "",
  "date": "",
  "time": "",
  "location": "",
  "participants": []
}
```
