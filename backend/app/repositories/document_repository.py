import json

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.app.models.document import DocumentRecord


def save_document(
    db: Session,
    document_name: str,
    document_type: str,
    status: str,
    result: dict,
) -> DocumentRecord:

    record = DocumentRecord(
        document_name=document_name,
        document_type=document_type,
        status=status,
        result_json=json.dumps(result),
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return record


def get_all_documents(
    db: Session,
) -> list[DocumentRecord]:

    statement = (
        select(DocumentRecord)
        .order_by(
            desc(DocumentRecord.created_at)
        )
    )

    return list(
        db.scalars(statement).all()
    )


def get_latest_document_by_name(
    db: Session,
    document_name: str,
) -> DocumentRecord | None:

    statement = (
        select(DocumentRecord)
        .where(
            DocumentRecord.document_name
            == document_name
        )
        .order_by(
            desc(DocumentRecord.created_at)
        )
        .limit(1)
    )

    return db.scalars(
        statement
    ).first()