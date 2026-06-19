import os
from datetime import datetime, timezone

from bson import ObjectId
from pymongo import MongoClient


DEFAULT_MONGO_URI = "mongodb://127.0.0.1:27017"
DEFAULT_MONGO_DB = "voucher_creator"
DEFAULT_COLLECTION = "extraction_jobs"


def _utc_now():
    return datetime.now(timezone.utc)


def _collection():
    client = MongoClient(os.environ.get("MONGO_URI", DEFAULT_MONGO_URI))
    database = client[os.environ.get("MONGO_DB", DEFAULT_MONGO_DB)]
    return database[os.environ.get("MONGO_EXTRACTION_JOBS_COLLECTION", DEFAULT_COLLECTION)]


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
    _collection().update_one(
        {"_id": ObjectId(job_id)},
        {
            "$set": {
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
