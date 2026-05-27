import datetime
import enum
import json
import os
import re
from typing import Any, Dict, List, Optional

import pika
import pymongo
import requests
from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, create_engine, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

MONGO_URI = os.getenv("STORAGE_URL", "mongodb://mongo_db:27017")
MONGO_DB_NAME = "collection_storage"
DATABASE_URL = os.environ["DATABASE_URL"]
RABBITMQ_HOST = os.getenv("MQ_HOST", "rabbitmq_broker")
OLS_BASE_URL = os.getenv("OLS_BASE_URL", "https://www.ebi.ac.uk/ols4/api").rstrip("/")
OLS_BASE_URL = OLS_BASE_URL or "https://www.ebi.ac.uk/ols4/api"
OLS_SEARCH_ROWS = max(1, int((os.getenv("OLS_SEARCH_ROWS") or "5").strip()))
AOP_MCP_BASE_URL = (os.getenv("AOP_MCP_BASE_URL") or "").rstrip("/")
AOP_MCP_SEARCH_TOOLS = [
    item.strip() for item in (
        os.getenv("AOP_MCP_SEARCH_TOOLS")
        or "search_aops,map_chemical_to_aops,get_aop,list_key_events,list_kers,search_key_events,find_key_events,get_key_event"
    ).split(",")
    if item.strip()
]
HTTP_TIMEOUT_SECONDS = float((os.getenv("ENRICHMENT_REQUEST_TIMEOUT_SECONDS") or "20").strip())

mongo_client = pymongo.MongoClient(MONGO_URI)
mongo_db = mongo_client[MONGO_DB_NAME]
telemetry_collection = mongo_db["session_telemetry"]

Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def ensure_session_status_enum_values():
    expected_values = [status.value for status in SessionStatusEnum]
    try:
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            enum_exists = connection.execute(text("SELECT 1 FROM pg_type WHERE typname = 'sessionstatusenum'")).scalar()
            if not enum_exists:
                return

            existing_values = {
                row[0]
                for row in connection.execute(
                    text(
                        """
                        SELECT e.enumlabel
                        FROM pg_type t
                        JOIN pg_enum e ON t.oid = e.enumtypid
                        WHERE t.typname = 'sessionstatusenum'
                        """
                    )
                )
            }

            for value in expected_values:
                if value not in existing_values:
                    connection.execute(text(f"ALTER TYPE sessionstatusenum ADD VALUE IF NOT EXISTS '{value}'"))
                    print(f"✅ Added missing enum value '{value}' to sessionstatusenum")
    except Exception as exc:
        print(f"⚠️ Could not update sessionstatusenum on startup: {exc}")


class SessionStatusEnum(str, enum.Enum):
    queued = "queued"
    starting = "starting"
    chunking = "chunking"
    waiting = "waiting"
    extracting = "extracting"
    enriching = "enriching"
    finished = "finished"
    canceled = "canceled"


class CerSession(Base):
    __tablename__ = "cer_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)
    collection_id = Column(Integer, index=True, nullable=False)
    title = Column(String, nullable=False)
    key_events = Column(MutableList.as_mutable(ARRAY(String)), default=[])
    model_name = Column(String, nullable=False)
    relevance_score_threshold = Column(Float, nullable=False)
    status = Column(Enum(SessionStatusEnum, native_enum=False), default=SessionStatusEnum.queued, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    logs = relationship("CerSessionLog", back_populates="session", cascade="all, delete-orphan")


class CerSessionLog(Base):
    __tablename__ = "cer_session_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("cer_sessions.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(Enum(SessionStatusEnum, native_enum=False), nullable=False)

    session = relationship("CerSession", back_populates="logs")


ensure_session_status_enum_values()


def update_session_status(session_id: int, new_status: SessionStatusEnum):
    db: Session = SessionLocal()
    try:
        session = db.query(CerSession).filter(CerSession.id == session_id).first()
        if session:
            session.status = new_status
            session.updated_at = datetime.datetime.utcnow()
            db.commit()
            print(f"✅ Updated session {session_id} status to '{new_status.value}'")
    finally:
        db.close()


def log_session_status(session_id: int, status: SessionStatusEnum):
    db: Session = SessionLocal()
    try:
        log_entry = CerSessionLog(
            session_id=session_id,
            timestamp=datetime.datetime.utcnow(),
            status=status,
        )
        db.add(log_entry)
        db.commit()
        print(f"📝 Log added: '{status.value}' for session {session_id}")
    finally:
        db.close()


def upsert_session_telemetry(session_id: int, payload: Dict[str, Any]):
    telemetry_collection.update_one(
        {"session_id": session_id},
        {"$set": {"session_id": session_id, **payload}},
        upsert=True,
    )


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "entity"


def normalize_label(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def fetch_extracted_relations(session_id: int) -> List[Dict[str, Any]]:
    entry = mongo_db["extracted_causal_relations"].find_one({"session_id": session_id})
    return entry.get("extracted_data", []) if entry else []


def fetch_selected_chunk_map(session_id: int) -> Dict[str, Dict[str, str]]:
    chunk_map: Dict[str, Dict[str, str]] = {}
    entry = mongo_db["selected_chunks"].find_one({"session_id": session_id})
    if not entry:
        return chunk_map

    for document in entry.get("documents", []):
        document_id = document.get("document_id")
        file_metadata = None
        if document_id:
            try:
                file_metadata = mongo_db["fs.files"].find_one({"_id": pymongo.objectid.ObjectId(document_id)})
            except Exception:
                file_metadata = None
        document_name = file_metadata["filename"] if file_metadata and "filename" in file_metadata else document.get("name", "Unknown document")
        for chunk in document.get("chunks", []):
            chunk_map[chunk.get("id")] = {
                "document_name": document_name,
                "text": chunk.get("text", ""),
            }

    return chunk_map


def score_ols_candidate(term: str, candidate: Dict[str, Any]) -> int:
    label = normalize_label(candidate.get("label", ""))
    short_form = normalize_label(candidate.get("short_form", ""))
    normalized_term = normalize_label(term)

    score = 0
    if label.lower() == normalized_term.lower():
        score += 100
    elif normalized_term.lower() in label.lower():
        score += 50

    if short_form and short_form.lower() == normalized_term.lower():
        score += 25

    if candidate.get("is_defining_ontology"):
        score += 5

    return score


def search_ols(term: str) -> Optional[Dict[str, Any]]:
    try:
        response = requests.get(
            f"{OLS_BASE_URL}/search",
            params={"q": term, "rows": OLS_SEARCH_ROWS},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        print(f"⚠️ OLS lookup failed for '{term}': {exc}")
        return None

    docs = payload.get("response", {}).get("docs", [])
    if not docs:
        return None

    best = sorted(docs, key=lambda item: score_ols_candidate(term, item), reverse=True)[0]
    return {
        "label": best.get("label") or term,
        "curie": best.get("short_form"),
        "iri": best.get("iri"),
        "ontology_name": best.get("ontology_name"),
        "description": (best.get("description") or [None])[0] if isinstance(best.get("description"), list) else best.get("description"),
        "is_defining_ontology": best.get("is_defining_ontology"),
        "match_score": score_ols_candidate(term, best),
    }


def mcp_request(method: str, params: Dict[str, Any], request_id: int) -> Optional[Dict[str, Any]]:
    if not AOP_MCP_BASE_URL:
        return None

    try:
        response = requests.post(
            AOP_MCP_BASE_URL,
            json={"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as exc:
        print(f"⚠️ AOP MCP request failed ({method}): {exc}")
        return None


def recursive_collect(payload: Any, field_names: List[str]) -> List[Any]:
    collected: List[Any] = []

    def visit(value: Any):
        if isinstance(value, dict):
            for key, nested in value.items():
                if key in field_names and nested is not None:
                    collected.append(nested)
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(payload)
    return collected


def normalize_aop_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def extract_structured_result(tool_payload: Dict[str, Any]) -> Any:
    result = tool_payload.get("result", {})
    structured = result.get("structuredContent")
    if structured is not None:
        return structured

    content = result.get("content", [])
    if isinstance(content, list):
        text_items = [item.get("text") for item in content if isinstance(item, dict) and item.get("type") == "text"]
        if text_items:
            return {"content": text_items}
    return result


def fetch_aop_details(aop_id: str) -> List[Dict[str, Any]]:
    details_payload = mcp_request("tools/call", {"name": "get_aop", "arguments": {"aop_id": aop_id}}, 3)
    if not details_payload:
        return []

    structured = extract_structured_result(details_payload)
    links = extract_aop_links(structured if isinstance(structured, dict) else {"items": structured})
    if links:
        return links

    return [{"url": f"https://aopwiki.org/aops/{aop_id}", "label": f"AOP {aop_id}"}]


def maybe_fetch_aop_context(term: str) -> List[Dict[str, Any]]:
    if not AOP_MCP_BASE_URL:
        return []

    tools_payload = mcp_request("tools/list", {}, 1)
    if not tools_payload:
        return []

    tools = tools_payload.get("result", {}).get("tools", [])
    tool_names = {tool.get("name") for tool in tools}
    candidate_tool_names = [candidate for candidate in AOP_MCP_SEARCH_TOOLS if candidate in tool_names]
    if not candidate_tool_names:
        return []

    collected_links: List[Dict[str, Any]] = []
    seen_urls = set()

    for tool_name in candidate_tool_names:
        for arguments in ({"query": term}, {"text": term}, {"name": term}, {"key_event": term}, {"event": term}):
            tool_payload = mcp_request("tools/call", {"name": tool_name, "arguments": arguments}, 2)
            if not tool_payload or tool_payload.get("error"):
                continue

            structured = extract_structured_result(tool_payload)
            payload_for_links = structured if isinstance(structured, dict) else {"items": structured}
            for link in extract_aop_links(payload_for_links):
                if link["url"] in seen_urls:
                    continue
                seen_urls.add(link["url"])
                collected_links.append(link)

            for raw_aop_id in recursive_collect(structured, ["aop_id", "aopId", "id"]):
                aop_id = normalize_aop_id(raw_aop_id)
                if not aop_id:
                    continue
                for link in fetch_aop_details(aop_id):
                    if link["url"] in seen_urls:
                        continue
                    seen_urls.add(link["url"])
                    collected_links.append(link)

            if collected_links:
                return collected_links[:5]

    return []


def extract_aop_links(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    links: List[Dict[str, Any]] = []

    def visit(value: Any):
        if isinstance(value, dict):
            url = value.get("url") or value.get("href")
            label = value.get("title") or value.get("label") or value.get("name")
            if isinstance(url, str) and "aopwiki" in url.lower():
                links.append({"url": url, "label": label or url})
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(payload)
    deduped = []
    seen = set()
    for link in links:
        if link["url"] in seen:
            continue
        seen.add(link["url"])
        deduped.append(link)
    return deduped[:5]


def build_enriched_graph(session_id: int) -> Dict[str, Any]:
    raw_relations = fetch_extracted_relations(session_id)
    chunk_map = fetch_selected_chunk_map(session_id)
    node_index: Dict[str, Dict[str, Any]] = {}
    edge_index: Dict[str, Dict[str, Any]] = {}

    for item in raw_relations:
        chunk_id = item.get("id")
        chunk_text = item.get("text", "")
        relationships = item.get("output", {}).get("relationships", [])

        for relation in relationships:
            subject = normalize_label(relation.get("subject", ""))
            obj = normalize_label(relation.get("object", ""))
            verb = normalize_label(relation.get("verb", ""))
            causal_connection = relation.get("causal_connection", "Positive")

            if not subject or not obj or not verb:
                continue

            for label in (subject, obj):
                node = node_index.get(label)
                if not node:
                    ontology_term = search_ols(label)
                    aop_links = maybe_fetch_aop_context(label)
                    node = {
                        "id": slugify(label),
                        "raw_label": label,
                        "display_label": ontology_term.get("label", label) if ontology_term else label,
                        "normalized_label": label.lower(),
                        "ontology_term": ontology_term,
                        "aop_wiki_links": aop_links,
                    }
                    node_index[label] = node

            edge_key = f"{subject}|{verb}|{obj}|{causal_connection}"
            edge = edge_index.get(edge_key)
            if not edge:
                edge = {
                    "id": slugify(edge_key),
                    "source": node_index[subject]["id"],
                    "target": node_index[obj]["id"],
                    "source_label": subject,
                    "target_label": obj,
                    "predicate": verb,
                    "causal_connection": causal_connection,
                    "evidence": [],
                }
                edge_index[edge_key] = edge

            evidence = {
                "chunk_id": chunk_id,
                "chunk_text": chunk_text or chunk_map.get(chunk_id, {}).get("text"),
                "document_name": chunk_map.get(chunk_id, {}).get("document_name"),
            }
            if evidence not in edge["evidence"]:
                edge["evidence"].append(evidence)

    return {
        "session_id": session_id,
        "created_at": datetime.datetime.utcnow(),
        "nodes": list(node_index.values()),
        "edges": list(edge_index.values()),
        "summary": {
            "raw_relationships": sum(
                len(item.get("output", {}).get("relationships", [])) for item in raw_relations
            ),
            "standardized_nodes": len(node_index),
            "standardized_edges": len(edge_index),
            "nodes_with_ontology_match": sum(1 for node in node_index.values() if node.get("ontology_term")),
            "nodes_with_aop_links": sum(1 for node in node_index.values() if node.get("aop_wiki_links")),
        },
        "provenance": {
            "ols_base_url": OLS_BASE_URL,
            "aop_mcp_base_url": AOP_MCP_BASE_URL or None,
        },
    }


def process_and_store(session_id: int):
    upsert_session_telemetry(
        session_id,
        {
            "phase": "enriching",
            "updated_at": datetime.datetime.utcnow(),
            "last_message": "Standardizing entities against ontologies and building enriched graph.",
        },
    )

    graph = build_enriched_graph(session_id)
    mongo_db["enriched_graphs"].replace_one(
        {"session_id": session_id},
        {
            "session_id": session_id,
            "processed_at": datetime.datetime.utcnow(),
            "graph": graph,
        },
        upsert=True,
    )

    upsert_session_telemetry(
        session_id,
        {
            "phase": "finished",
            "updated_at": datetime.datetime.utcnow(),
            "last_message": (
                f"Enrichment finished with {graph['summary']['standardized_nodes']} standardized nodes "
                f"and {graph['summary']['standardized_edges']} edges."
            ),
            "last_error": None,
        },
    )

    update_session_status(session_id, SessionStatusEnum.finished)
    log_session_status(session_id, SessionStatusEnum.finished)


def mark_finished_with_warning(session_id: int, error: str):
    upsert_session_telemetry(
        session_id,
        {
            "phase": "finished",
            "updated_at": datetime.datetime.utcnow(),
            "last_message": "Raw extraction is available, but enrichment did not complete cleanly.",
            "last_error": error,
        },
    )
    update_session_status(session_id, SessionStatusEnum.finished)
    log_session_status(session_id, SessionStatusEnum.finished)
