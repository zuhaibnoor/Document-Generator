import os

from google import genai
from google.genai import types

from app.models import ScopeRow, ScopeSheet, ScopeSheetRequest

PROMPT = """
You turn a scope call transcript into a scope sheet.

Include only work the transcript supports. Do not invent features.
Use the same business_process name for features that belong together, and keep those rows together.
Write a plain description of what will be delivered, in one or two sentences.
Put unresolved questions in assumptions. Leave assumptions empty when there are none.
""".strip()


async def ask_gemini(request: ScopeSheetRequest, transcript: str) -> ScopeSheet:
    """Ask Gemini for scope rows that match the ScopeSheet shape."""
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Set GEMINI_API_KEY in local.settings.json, then restart func start.")

    notes = request.notes.strip() if request.notes else "None."
    user_message = f"""
    Client: {request.client_name}
    Project: {request.project_name}
    Source file: {request.file_name}
    Notes: {notes}

    Transcript:
    {transcript}
    """.strip()

    client = genai.Client(api_key=api_key)
    try:
        response = await client.aio.models.generate_content(
            model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=PROMPT,
                response_mime_type="application/json",
                response_schema=ScopeSheet,
            ),
        )
        sheet = ScopeSheet.model_validate_json(response.text)
    except Exception as exc:
        raise RuntimeError("Gemini did not return a usable scope sheet.") from exc

    if not sheet.rows:
        raise RuntimeError("Gemini returned a scope sheet with no rows.")
    return _group_rows(sheet)


def _group_rows(sheet: ScopeSheet) -> ScopeSheet:
    grouped: dict[str, list[ScopeRow]] = {}
    for row in sheet.rows:
        grouped.setdefault(row.business_process.strip(), []).append(row)
    return ScopeSheet(
        rows=[row for process_rows in grouped.values() for row in process_rows],
        assumptions=[item.strip() for item in sheet.assumptions if item.strip()],
    )
