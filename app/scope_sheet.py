import base64
import os
import re
from io import BytesIO

from google import genai
from google.genai import types
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from app.models import ScopeRow, ScopeSheet, ScopeSheetRequest, ScopeSheetResponse

XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

PROMPT = """
You turn a scope call transcript into a scope sheet.

Include only work the transcript supports. Do not invent features.
Use the same business_process name for features that belong together, and keep those rows together.
Write a plain description of what will be delivered, in one or two sentences.
Put unresolved questions in assumptions. Leave assumptions empty when there are none.
""".strip()


def decode_transcript(transcript_base64: str) -> str:
    """Turn the base64 text from the request into a normal string."""
    raw = transcript_base64.strip()
    if raw.startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        text = base64.b64decode(raw).decode("utf-8").strip()
    except Exception as exc:
        raise ValueError("transcript_base64 must be base64-encoded UTF-8 text.") from exc
    if not text:
        raise ValueError("The transcript is empty.")
    return text


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


def build_response(sheet: ScopeSheet, request: ScopeSheetRequest) -> ScopeSheetResponse:
    """Build the Excel file in memory and return it as base64."""
    return ScopeSheetResponse(
        file_name=_file_name(request.client_name, request.project_name),
        content_type=XLSX_TYPE,
        content_base64=base64.b64encode(_workbook_bytes(sheet, request)).decode("ascii"),
        row_count=len(sheet.rows),
    )


def _group_rows(sheet: ScopeSheet) -> ScopeSheet:
    grouped: dict[str, list[ScopeRow]] = {}
    for row in sheet.rows:
        grouped.setdefault(row.business_process.strip(), []).append(row)
    return ScopeSheet(
        rows=[row for process_rows in grouped.values() for row in process_rows],
        assumptions=[item.strip() for item in sheet.assumptions if item.strip()],
    )


def _workbook_bytes(sheet: ScopeSheet, request: ScopeSheetRequest) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Scope Sheet"

    border = Border(
        left=Side(style="thin", color="BFCBD9"),
        right=Side(style="thin", color="BFCBD9"),
        top=Side(style="thin", color="BFCBD9"),
        bottom=Side(style="thin", color="BFCBD9"),
    )
    wrap = Alignment(wrap_text=True, vertical="center")

    worksheet.merge_cells("A1:C1")
    title = worksheet["A1"]
    title.value = f"{request.client_name} - {request.project_name}"
    title.font = Font(bold=True, color="FFFFFF", size=16)
    title.fill = PatternFill("solid", fgColor="1F4E79")

    for column, header in enumerate(("Business process", "Feature", "Description"), start=1):
        cell = worksheet.cell(2, column, header)
        cell.font = Font(bold=True, color="1F4E79")
        cell.fill = PatternFill("solid", fgColor="D6E3F0")
        cell.border = border

    for index, row in enumerate(sheet.rows, start=3):
        values = (row.business_process, row.feature, row.description)
        for column, value in enumerate(values, start=1):
            cell = worksheet.cell(index, column, value)
            cell.alignment = wrap
            cell.border = border

    _merge_same_process(worksheet, len(sheet.rows))

    if sheet.assumptions:
        start = len(sheet.rows) + 4
        worksheet.cell(start, 1, "Assumptions and open questions").font = Font(bold=True, color="1F4E79")
        for offset, assumption in enumerate(sheet.assumptions, start=1):
            worksheet.merge_cells(start_row=start + offset, start_column=1, end_row=start + offset, end_column=3)
            worksheet.cell(start + offset, 1, assumption).alignment = wrap

    worksheet.column_dimensions["A"].width = 32
    worksheet.column_dimensions["B"].width = 36
    worksheet.column_dimensions["C"].width = 72
    worksheet.freeze_panes = "A3"

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _merge_same_process(worksheet, row_count: int) -> None:
    start = 3
    for row_number in range(4, row_count + 4):
        previous = worksheet.cell(row_number - 1, 1).value
        current = worksheet.cell(row_number, 1).value if row_number <= row_count + 2 else None
        if current == previous:
            continue
        if row_number - 1 > start:
            worksheet.merge_cells(start_row=start, start_column=1, end_row=row_number - 1, end_column=1)
        start = row_number


def _file_name(client_name: str, project_name: str) -> str:
    def clean(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_") or "scope"

    return f"{clean(client_name)}_{clean(project_name)}_scope_sheet.xlsx"
