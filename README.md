
**Author: Ishan Pandita**

---

## Getting Started

### Clone the Repository
```bash
git clone https://github.com/ishanpandita/I_agent.git
cd I_agent
```

---

## Libraries Required
- pdfplumber
- pdf2image
- pytesseract
- poppler

---

## Install System Dependencies

**If windows:**
as i am using we have to install these manually and add in system path in system variables
- Tesseract → https://github.com/UB-Mannheim/tesseract/wiki
- Poppler → https://github.com/oschwartz10612/poppler-windows/releases

**else in Mac:**
```bash
brew install poppler tesseract
```

---

## Verify Installations

**Windows:**
```bash
tesseract --version
pdftoppm -v
```

**Mac:**
```bash
which tesseract
tesseract -v
pdftoppm -v
```

---Create Virtual Environment
```bash
python -m venv venv
```

---

## Install Python Libraries
```bash
pip install -r requirements.txt
```
requirements.txt contains: pdf2image, pytesseract, pdfplumber

---

## Run
```bash
python agent.py --input input_docs --output results
```
This will create a `results/` folder with JSON results for all PDFs in `input_docs/`.

---



Used `pdfplumber` for text-layer PDFs and falls back to `pytesseract` OCR (via `pdf2image`) for image-based or scanned PDFs — handles both automatically.