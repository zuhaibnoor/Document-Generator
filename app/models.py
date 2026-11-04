from pydantic import BaseModel, Field


class ScopeSheetRequest(BaseModel):
    transcript_base64: str = Field(min_length=1)
    file_name: str
    client_name: str
    project_name: str
    notes: str | None = None


class ScopeRow(BaseModel):
    business_process: str
    feature: str
    description: str


class ScopeSheet(BaseModel):
    rows: list[ScopeRow]
    assumptions: list[str] = []


class ScopeSheetResponse(BaseModel):
    file_name: str
    csv: str
    row_count: int
