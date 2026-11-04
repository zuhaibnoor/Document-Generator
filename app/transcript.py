import base64


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
