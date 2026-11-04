import csv
import re
from io import StringIO

from app.models import ScopeSheet, ScopeSheetRequest, ScopeSheetResponse


def build_response(sheet: ScopeSheet, request: ScopeSheetRequest) -> ScopeSheetResponse:
    """Turn the scope rows into plain CSV text."""
    return ScopeSheetResponse(
        file_name=_file_name(request.client_name, request.project_name),
        csv=_csv_text(sheet),
        row_count=len(sheet.rows),
    )


def _csv_text(sheet: ScopeSheet) -> str:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Business process", "Feature", "Description"])
    for row in sheet.rows:
        writer.writerow([row.business_process, row.feature, row.description])
    if sheet.assumptions:
        writer.writerow([])
        writer.writerow(["Assumptions and open questions"])
        for assumption in sheet.assumptions:
            writer.writerow([assumption])
    return buffer.getvalue()


def _file_name(client_name: str, project_name: str) -> str:
    def clean(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_") or "scope"

    return f"{clean(client_name)}_{clean(project_name)}_scope_sheet.csv"
