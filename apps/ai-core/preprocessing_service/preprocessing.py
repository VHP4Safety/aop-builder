import os
import json
import time
import numpy as np
import re
import spacy
import pymupdf4llm
import fitz
import pymongo
import gridfs
import tempfile
from bson import ObjectId
from sqlalchemy import create_engine, Column, Integer, String, ARRAY
from sqlalchemy.orm import sessionmaker, declarative_base

STORAGE_URL = os.getenv("STORAGE_URL", "mongodb://mongo_db:27017")
DATABASE_URL = os.environ["DATABASE_URL"]
MONGO_DB_NAME = "collection_storage"

Base = declarative_base()

class Collection(Base):
    __tablename__ = "collections"
    id = Column(Integer, primary_key=True, index=True)
    pdf_ids = Column(ARRAY(String), nullable=True)
    status = Column(String, default="unscanned", nullable=False)


engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

mongo_client = pymongo.MongoClient(STORAGE_URL)
mongo_db = mongo_client[MONGO_DB_NAME]
fs = gridfs.GridFS(mongo_db)
_nlp_cache = {}


def extract_doi(text: str):
    if not text:
        return None
    match = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", text, flags=re.IGNORECASE)
    return match.group(0) if match else None


def derive_title_from_first_page(first_page_text: str):
    if not first_page_text:
        return None

    lines = [line.strip() for line in first_page_text.splitlines() if line.strip()]
    for line in lines[:12]:
        if len(line) < 20:
            continue
        if re.search(r"\babstract\b", line, flags=re.IGNORECASE):
            continue
        if re.search(r"\bdoi\b", line, flags=re.IGNORECASE):
            continue
        return line
    return None


def extract_pdf_reference_info(file_id: str, pdf_data: bytes):
    file_doc = mongo_db["fs.files"].find_one({"_id": ObjectId(file_id)})
    filename = file_doc.get("filename") if file_doc else None
    upload_date = file_doc.get("uploadDate") if file_doc else None
    content_type = file_doc.get("contentType") if file_doc else None
    length = file_doc.get("length") if file_doc else None

    embedded_metadata = {}
    first_page_text = ""
    page_count = None

    try:
        pdf = fitz.open(stream=pdf_data, filetype="pdf")
        embedded_metadata = pdf.metadata or {}
        page_count = pdf.page_count
        if page_count and page_count > 0:
            first_page_text = pdf.load_page(0).get_text("text")
        pdf.close()
    except Exception as exc:
        print(f"⚠️ Could not extract PDF metadata for {file_id}: {exc}")

    title = (embedded_metadata.get("title") or "").strip() or derive_title_from_first_page(first_page_text)
    authors = (embedded_metadata.get("author") or "").strip() or None
    subject = (embedded_metadata.get("subject") or "").strip() or None
    keywords = (embedded_metadata.get("keywords") or "").strip() or None
    doi = extract_doi(first_page_text)
    year = upload_date.year if upload_date else None

    return {
        "document_id": file_id,
        "filename": filename or f"document_{file_id}",
        "title": title or filename or f"document_{file_id}",
        "authors": authors,
        "subject": subject,
        "keywords": keywords,
        "doi": doi,
        "year": year,
        "upload_date": upload_date,
        "content_type": content_type,
        "file_size_bytes": length,
        "page_count": page_count,
    }


def save_document_reference_info(reference_info):
    mongo_db["document_references"].replace_one(
        {"document_id": reference_info["document_id"]},
        reference_info,
        upsert=True,
    )


def convert(obj):
    if obj is None:
        return None
    if isinstance(obj, (np.float32, np.float64, float)):
        return float(obj)  # Zorg dat floats echte Python floats zijn
    if isinstance(obj, (np.integer, int)):
        return int(obj)  # Zorg dat integers echte Python ints zijn
    if isinstance(obj, np.ndarray):
        return obj.tolist()  # Zet numpy arrays om in Python lijsten
    if isinstance(obj, str) and obj.isnumeric():
        return int(obj)  # Zet numerieke strings expliciet om in integers
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

# Stap 1: Haal `pdf_ids` op uit PostgreSQL
def get_pdf_ids_from_postgres(collection_id, db_session):
    collection = db_session.query(Collection).filter(Collection.id == collection_id).first()
    if not collection or not collection.pdf_ids:
        raise ValueError(f"❌ Geen documenten gevonden voor collectie {collection_id}")
    return collection.pdf_ids


# Stap 2: Haal PDF's op uit MongoDB via `pdf_ids`
def fetch_pdfs_from_collection(collection_id, db_session):
    pdf_ids = get_pdf_ids_from_postgres(collection_id, db_session)
    pdf_files = []
    for file_id in pdf_ids:
        try:
            pdf_data = fs.get(ObjectId(file_id)).read()
            pdf_files.append({"file_id": file_id, "data": pdf_data})
            print(f"✅ PDF {file_id} opgehaald uit MongoDB.")
        except Exception as e:
            print(f"❌ Fout bij ophalen van PDF {file_id}: {e}")
    if not pdf_files:
        raise ValueError(f"❌ Geen documenten gevonden in MongoDB voor collectie {collection_id}")
    return pdf_files


# Stap 3: Converteer PDF naar Markdown met `pymupdf4llm`
def convert_pdf_with_marker(pdf_data):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_pdf:
        temp_pdf.write(pdf_data)
        temp_pdf_path = temp_pdf.name
    try:
        markdown_text = pymupdf4llm.to_markdown(temp_pdf_path)
    finally:
        os.remove(temp_pdf_path)
    return markdown_text


# Stap 4: Tekst opschonen
def clean_markdown_text(markdown_text):
    cleaned_text = re.sub(r'^#+\s*references.*', '', markdown_text, flags=re.IGNORECASE | re.DOTALL | re.MULTILINE)
    cleaned_text = re.sub(r'\[.*?\]\(.*?\)', '', cleaned_text)
    pattern = r"\([^)]*et al\.[^)]*\)"
    cleaned_text = re.sub(pattern, "", cleaned_text)
    return cleaned_text


def get_nlp(model_name=None):
    """Load spaCy once per process, with a blank-English fallback for offline resilience."""
    resolved_model = model_name or os.getenv("PREPROCESSING_SPACY_MODEL", "en_core_web_sm")
    if resolved_model in _nlp_cache:
        return _nlp_cache[resolved_model]

    try:
        nlp = spacy.load(resolved_model)
        print(f"✅ Loaded spaCy model '{resolved_model}'")
    except Exception as error:
        print(f"⚠️ Could not load spaCy model '{resolved_model}': {error}. Falling back to blank 'en'.")
        nlp = spacy.blank("en")

    _nlp_cache[resolved_model] = nlp
    return nlp


# Stap 5: Spacy-verwerking (entiteiten verwijderen)
def process_and_clean_markdown_text(markdown_text, model_name=None):
    nlp = get_nlp(model_name)
    doc = nlp(markdown_text)

    matches = re.finditer(r'\((.*?)\)', markdown_text)
    text_as_list = list(markdown_text)

    for match in matches:
        start, end = match.span()
        text_in_brackets = markdown_text[start + 1:end - 1]
        ent_in_brackets = nlp(text_in_brackets)

        has_person = any(ent.label_ == 'PERSON' for ent in ent_in_brackets.ents)
        has_date = any(ent.label_ == 'DATE' for ent in ent_in_brackets.ents)

        if has_person or has_date:
            text_as_list[start:end] = [''] * (end - start)

    for ent in reversed(doc.ents):
        if ent.label_ in ['PERSON', 'ORG', 'GPE']:
            text_as_list[ent.start_char:ent.end_char] = [''] * (ent.end_char - ent.start_char)

    cleaned_text = ''.join(text_as_list)
    cleaned_text = '\n'.join(' '.join(line.split()) for line in cleaned_text.split('\n'))
    return cleaned_text


# Stap 6: Extractie met numerieke conversie
def extract_headings_and_paragraphs(content):
    data = []
    current_heading = None
    current_level = None
    paragraph = ""

    for line in content.splitlines():
        line = line.strip()
        heading_match = re.match(r"^(#+)\s*(.*)", line)

        if heading_match:
            heading_text = heading_match.group(2).strip()

            if re.match(r"^\d+\s+\d+$", heading_text):
                paragraph += f" {heading_text}"
                continue

            if paragraph:
                data.append({
                    "Heading": current_heading,
                    "Level": convert(current_level) if current_level is not None else None,
                    "Content": paragraph.strip(),
                    "Characters": convert(len(paragraph.strip()))
                })
                paragraph = ""

            current_level = len(heading_match.group(1))
            current_heading = heading_match.group(2)

        elif line:
            paragraph += f"{line} "

    if paragraph:
        data.append({
            "Heading": current_heading,
            "Level": convert(current_level) if current_level is not None else None,
            "Content": paragraph.strip(),
            "Characters": convert(len(paragraph.strip()))
        })

    return data


# Stap 7: Opslaan in MongoDB
def save_processed_data(collection_id, processed_documents):
    """Slaat de geëxtraheerde koppen en paragrafen correct op in MongoDB."""
    try:
        print("Data vóór conversie:", json.dumps(processed_documents, default=convert, indent=4))
        processed_documents_serializable = json.loads(json.dumps(processed_documents, default=convert))

        mongo_db["processed_collections"].insert_one({
            "collection_id": collection_id,
            "processed_at": convert(time.time()),
            "documents": processed_documents_serializable
        })
        print(f"✅ Data succesvol opgeslagen voor collectie {collection_id} in MongoDB")
    except Exception as e:
        print(f"❌ Fout bij opslaan van data in MongoDB voor collectie {collection_id}: {e}")


def process_collection(collection_id):
    print(f"Verwerken van collectie {collection_id}...")

    db_session = SessionLocal()
    try:
        pdf_files = fetch_pdfs_from_collection(collection_id, db_session)
    finally:
        db_session.close()

    processed_documents = []
    for pdf in pdf_files:
        try:
            print(f"PDF {pdf['file_id']} wordt verwerkt...")
            reference_info = extract_pdf_reference_info(pdf["file_id"], pdf["data"])
            save_document_reference_info(reference_info)
            markdown_text = convert_pdf_with_marker(pdf["data"])
            cleaned_text = clean_markdown_text(markdown_text)
            processed_text = process_and_clean_markdown_text(cleaned_text)
            extracted_data = extract_headings_and_paragraphs(processed_text)

            processed_documents.append({"document_id": pdf["file_id"], "content": extracted_data})
            print(f"✅ Verwerking voltooid voor PDF {pdf['file_id']}")
        except Exception as e:
            print(f"❌ Fout bij verwerken van PDF {pdf['file_id']}: {e}")

    save_processed_data(collection_id, processed_documents)


if __name__ == "__main__":
    collection_id = int(os.getenv("COLLECTION_ID", "1"))
    process_collection(collection_id)
