===============Ishan pandita=================================

Git Clone:
after that cd I_agent

libraries: pdfplumber pdf2image pytesseract poppler 

if windows:
as i am using windows we have to manually install poppler and tesseract add that in system path 
else in mac:
brew install poppler tesseract in terminal 

TO Verify installations:

Windows: "tesseract --version"   and   "pdftoppm -v"

Mac: 
which tesseract — Shows the path (usually /opt/homebrew/bin/tesseract on Apple Silicon).
tesseract -v 
For Poppler:
pdftoppm -v — 



Create virtual environment: python -m venv venv

Install Python Libraries
bash
pip install -r requirements.txt
verify requirements.txt has libraries like pdf2image pytesseract pdfplumber


BASH: 
python agent.py --input input_docs --output results

This will create another folder results which has results of pdf in input_docs




 Used `pdfplumber` for text-layer PDFs and falls back to `pytesseract` OCR (via `pdf2image`) for image-based or scanned PDFs — handles both automatically.
