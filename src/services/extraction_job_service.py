import os
from datetime import datetime, timezone

from bson import ObjectId
from pymongo import MongoClient


DEFAULT_MONGO_URI = "mongodb://127.0.0.1:27017"
DEFAULT_MONGO_DB = "voucher_creator"
DEFAULT_COLLECTION = "extraction_jobs"
DEFAULT_SALES_INVOICES_COLLECTION = "sales_invoices"
DEFAULT_PURCHASE_INVOICES_COLLECTION = "purchase_invoices"
DEFAULT_BANK_STATEMENTS_COLLECTION = "bank_statements"


def _utc_now():
    return datetime.now(timezone.utc)


def _database():
    client = MongoClient(os.environ.get("MONGO_URI", DEFAULT_MONGO_URI))
    return client[os.environ.get("MONGO_DB", DEFAULT_MONGO_DB)]


def _collection():
    return _database()[os.environ.get("MONGO_EXTRACTION_JOBS_COLLECTION", DEFAULT_COLLECTION)]


def _completed_document_collection_name(document_type, source):
    if document_type == "bank_statement":
        return os.environ.get("MONGO_BANK_STATEMENTS_COLLECTION", DEFAULT_BANK_STATEMENTS_COLLECTION)

    if document_type == "invoice" and source == "purchase-invoice":
        return os.environ.get("MONGO_PURCHASE_INVOICES_COLLECTION", DEFAULT_PURCHASE_INVOICES_COLLECTION)

    if document_type == "invoice" and source == "sales-invoice":
        return os.environ.get("MONGO_SALES_INVOICES_COLLECTION", DEFAULT_SALES_INVOICES_COLLECTION)

    return None


def _save_completed_document(job_id, extraction, request_payload, now):
    document_type = extraction.get("document_type")
    source = (request_payload or {}).get("source")
    collection_name = _completed_document_collection_name(document_type, source)
    if not collection_name:
        return None

    document = {
        "extraction_job_id": job_id,
        "document_type": document_type,
        "source": source,
        "status": "completed",
        "request": request_payload,
        "result": extraction.get("result"),
        "metadata": extraction.get("metadata"),
        "updated_at": now,
    }
    _database()[collection_name].update_one(
        {"extraction_job_id": job_id},
        {
            "$set": document,
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    return collection_name


def _public_job(document):
    if not document:
        return None

    public = dict(document)
    public["id"] = str(public.pop("_id"))
    return public


def create_extraction_job(payload):
    now = _utc_now()
    document = {
        "status": "queued",
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "completed_at": None,
        "error": None,
        "progress": {
            "stage": "queued",
            "message": "Waiting to process upload.",
        },
        "request": payload,
        "result": None,
        "metadata": None,
    }
    inserted = _collection().insert_one(document)
    return str(inserted.inserted_id)


def mark_job_running(job_id, message="Processing document."):
    now = _utc_now()
    _collection().update_one(
        {"_id": ObjectId(job_id)},
        {
            "$set": {
                "status": "processing",
                "started_at": now,
                "updated_at": now,
                "progress": {
                    "stage": "processing",
                    "message": message,
                },
            }
        },
    )


def mark_job_complete(job_id, extraction):
    now = _utc_now()
    collection = _collection()
    job = collection.find_one({"_id": ObjectId(job_id)}, {"request": 1})
    request_payload = (job or {}).get("request") or {}
    saved_collection = _save_completed_document(job_id, extraction, request_payload, now)

    completion_fields = {
        "status": "completed",
        "updated_at": now,
        "completed_at": now,
        "progress": {
            "stage": "completed",
            "message": "Document extraction completed.",
        },
        "result": extraction.get("result"),
        "metadata": extraction.get("metadata"),
        "document_type": extraction.get("document_type"),
    }
    if saved_collection:
        completion_fields["saved_collection"] = saved_collection

    collection.update_one(
        {"_id": ObjectId(job_id)},
        {
            "$set": completion_fields
        },
    )


def mark_job_failed(job_id, error):
    now = _utc_now()
    _collection().update_one(
        {"_id": ObjectId(job_id)},
        {
            "$set": {
                "status": "failed",
                "updated_at": now,
                "completed_at": now,
                "progress": {
                    "stage": "failed",
                    "message": str(error),
                },
                "error": str(error),
            }
        },
    )


def get_extraction_job(job_id):
    try:
        object_id = ObjectId(job_id)
    except Exception:
        return None

    return _public_job(_collection().find_one({"_id": object_id}))
