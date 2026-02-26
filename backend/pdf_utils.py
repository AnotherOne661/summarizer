import os
import re
from typing import List, Dict, Any
from pypdf import PdfReader
from pdf2image import convert_from_path
import pytesseract
from PIL import Image


def clean_ocr_text(text: str) -> str:
    if not text:
        return ""
    # Normalize whitespace
    txt = re.sub(r"\r\n", "\n", text)
    txt = re.sub(r"[ \t]+", " ", txt)
    # Fix common hyphenation at line breaks
    txt = re.sub(r"-\n([a-zA-Z])", r"\1", txt)
    txt = re.sub(r"\n{2,}", "\n\n", txt)
    return txt.strip()


def ocr_image(img: Image.Image, lang: str = "spa+eng") -> str:
    # Use pytesseract to OCR a PIL image
    try:
        text = pytesseract.image_to_string(img, lang=lang)
        return clean_ocr_text(text)
    except Exception as e:
        print(f"[WARN] OCR failed: {e}")
        return ""


async def extract_pdf_chunks(pdf_path: str, filename: str = "unknown") -> List[Dict[str, Any]]:
    """
    Extract text per page from a PDF. If text extraction yields empty for a page,
    fallback to rendering that page to an image and OCRing it.

    Returns a list of chunks where each chunk is a dict with keys: `text`, `page`.
    """
    chunks: List[Dict[str, Any]] = []
    try:
        reader = PdfReader(pdf_path)
    except Exception as e:
        print(f"Error opening PDF: {e}")
        return chunks

    num_pages = len(reader.pages)

    for i in range(num_pages):
        page_num = i + 1
        page = reader.pages[i]
        text = ""
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""

        if not text or len(text.strip()) < 20:
            # Render page to image and OCR
            try:
                images = convert_from_path(pdf_path, dpi=200, first_page=page_num, last_page=page_num)
                if images:
                    text = ocr_image(images[0])
            except Exception as e:
                print(f"[WARN] Failed to render/ocr page {page_num}: {e}")

        text = clean_ocr_text(text)

        if text:
            # Split long page text into sub-chunks of ~3000 chars
            max_chars = 3000
            start = 0
            while start < len(text):
                part = text[start:start + max_chars]
                chunks.append({"text": part, "page": page_num, "filename": filename})
                start += max_chars

    return chunks
