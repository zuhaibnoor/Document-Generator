from fastapi import FastAPI, HTTPException

from app.gemini import ask_gemini
from app.models import ScopeSheetRequest, ScopeSheetResponse
from app.transcript import decode_transcript
from app.csv_sheet import build_response

app = FastAPI()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/generate-scope-sheet", response_model=ScopeSheetResponse)
async def generate_scope_sheet(body: ScopeSheetRequest):
    try:
        transcript = decode_transcript(body.transcript_base64)
        sheet = await ask_gemini(body, transcript)
        return build_response(sheet, body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
