import pdfplumber
from pathlib import Path


def extract_text(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        text = ""
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text += t + "\n"
        return text.strip()
    elif ext in (".txt", ".md"):
        return Path(path).read_text(encoding="utf-8").strip()
    else:
        raise ValueError(f"Unsupported file type: {ext}. Use .pdf or .txt")


def extract_text_safe(path: str, max_chars: int = 12000) -> str:
    text = extract_text(path)
    if len(text) > max_chars:
        text = text[:max_chars]
    return text
