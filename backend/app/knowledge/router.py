from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.knowledge.service import KnowledgeService
from app.models import User
from app.schemas.knowledge import (
    ChunkResponse,
    DocumentResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdate,
)

router = APIRouter(tags=["knowledge"])


def _kb_response(kb) -> KnowledgeBaseResponse:
    data = KnowledgeBaseResponse.model_validate(kb)
    data.document_count = len(kb.documents)
    return data


@router.get("/knowledge-bases", response_model=list[KnowledgeBaseResponse])
def list_knowledge_bases(
    project_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[KnowledgeBaseResponse]:
    items = KnowledgeService(db).list_knowledge_bases(user=current_user, project_id=project_id)
    return [_kb_response(kb) for kb in items]


@router.post("/knowledge-bases", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
def create_knowledge_base(
    payload: KnowledgeBaseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> KnowledgeBaseResponse:
    kb = KnowledgeService(db).create_knowledge_base(user=current_user, payload=payload)
    return _kb_response(kb)


@router.get("/knowledge-bases/{kb_id}", response_model=KnowledgeBaseResponse)
def get_knowledge_base(
    kb_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> KnowledgeBaseResponse:
    kb = KnowledgeService(db).get_knowledge_base(user=current_user, kb_id=kb_id)
    return _kb_response(kb)


@router.patch("/knowledge-bases/{kb_id}", response_model=KnowledgeBaseResponse)
def update_knowledge_base(
    kb_id: int,
    payload: KnowledgeBaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> KnowledgeBaseResponse:
    kb = KnowledgeService(db).update_knowledge_base(user=current_user, kb_id=kb_id, payload=payload)
    return _kb_response(kb)


@router.delete("/knowledge-bases/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_knowledge_base(
    kb_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    KnowledgeService(db).delete_knowledge_base(user=current_user, kb_id=kb_id)


@router.get("/knowledge-bases/{kb_id}/documents", response_model=list[DocumentResponse])
def list_documents(
    kb_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[DocumentResponse]:
    docs = KnowledgeService(db).list_documents(user=current_user, kb_id=kb_id)
    return [DocumentResponse.model_validate(doc) for doc in docs]


@router.post(
    "/knowledge-bases/{kb_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    kb_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    doc = await KnowledgeService(db).upload_document(
        user=current_user,
        kb_id=kb_id,
        file=file,
        background_tasks=background_tasks,
    )
    return DocumentResponse.model_validate(doc)


@router.get("/documents/{doc_id}", response_model=DocumentResponse)
def get_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentResponse:
    doc = KnowledgeService(db).get_document(user=current_user, doc_id=doc_id)
    return DocumentResponse.model_validate(doc)


@router.get("/documents/{doc_id}/chunks", response_model=list[ChunkResponse])
def list_chunks(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ChunkResponse]:
    chunks = KnowledgeService(db).list_chunks(user=current_user, doc_id=doc_id)
    return [
        ChunkResponse(
            id=chunk.id,
            document_id=chunk.document_id,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            metadata=chunk.chunk_metadata,
            created_at=chunk.created_at,
        )
        for chunk in chunks
    ]


@router.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    doc_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    KnowledgeService(db).delete_document(user=current_user, doc_id=doc_id)
