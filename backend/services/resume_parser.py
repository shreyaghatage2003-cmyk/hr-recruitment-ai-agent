import io
import re
from typing import Optional
import pdfplumber
from docx import Document


class ResumeParser:
    """Extracts raw text and key fields from uploaded resume files."""

    def parse(self, file_bytes: bytes, filename: str) -> dict:
        ext = filename.lower().split(".")[-1]
        if ext == "pdf":
            text = self._parse_pdf(file_bytes)
        elif ext in ("docx", "doc"):
            text = self._parse_docx(file_bytes)
        else:
            text = file_bytes.decode("utf-8", errors="ignore")

        return {
            "text": text,
            "email": self._extract_email(text),
            "phone": self._extract_phone(text),
            "name": self._extract_name(text),
        }

    def _parse_pdf(self, data: bytes) -> str:
        text = ""
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
        return text.strip()

    def _parse_docx(self, data: bytes) -> str:
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs).strip()

    def _extract_email(self, text: str) -> Optional[str]:
        match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
        return match.group(0) if match else None

    def _extract_phone(self, text: str) -> Optional[str]:
        match = re.search(r"(\+?\d[\d\s\-().]{7,}\d)", text)
        return match.group(0).strip() if match else None

    def _extract_name(self, text: str) -> str:
        # Heuristic: first non-empty line is usually the name
        for line in text.splitlines():
            line = line.strip()
            if line and len(line.split()) <= 5 and not re.search(r"[@\d]", line):
                return line
        return "Unknown"


resume_parser = ResumeParser()
