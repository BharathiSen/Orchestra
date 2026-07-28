"""Knowledge base business logic and document ingestion pipeline."""

import logging
from pathlib import Path

from fastapi import BackgroundTasks, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.knowledge.chunker import chunk_text
from app.knowledge.embedding import embed_texts
from app.knowledge.upload import extract_text, save_upload
from app.knowledge.vector_store import store_chunks
from app.models import Document, KnowledgeBase, Project, User
from app.repositories.knowledge_repository import KnowledgeRepository
from app.schemas.knowledge import KnowledgeBaseCreate, KnowledgeBaseUpdate

logger = logging.getLogger(__name__)


class KnowledgeService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = KnowledgeRepository(db)

    def _get_owned_project(self, *, project_id: int, user: User) -> Project:
        project = self.db.get(Project, project_id)
        if project is None or project.owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
        return project

    def _get_owned_knowledge_base(self, *, kb_id: int, user: User) -> KnowledgeBase:
        kb = self.repo.get_knowledge_base(kb_id)
        if kb is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
        if kb.project.owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge base not found")
        return kb

    def _get_owned_document(self, *, doc_id: int, user: User) -> Document:
        doc = self.repo.get_document(doc_id)
        if doc is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        if doc.knowledge_base.project.owner_id != user.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        return doc

    def create_knowledge_base(self, *, user: User, payload: KnowledgeBaseCreate) -> KnowledgeBase:
        self._get_owned_project(project_id=payload.project_id, user=user)
        kb = KnowledgeBase(
            project_id=payload.project_id,
            name=payload.name,
            description=payload.description,
        )
        return self.repo.create_knowledge_base(kb)

    def list_knowledge_bases(self, *, user: User, project_id: int) -> list[KnowledgeBase]:
        self._get_owned_project(project_id=project_id, user=user)
        return self.repo.list_knowledge_bases(project_id=project_id)

    def get_knowledge_base(self, *, user: User, kb_id: int) -> KnowledgeBase:
        return self._get_owned_knowledge_base(kb_id=kb_id, user=user)

    def update_knowledge_base(
        self,
        *,
        user: User,
        kb_id: int,
        payload: KnowledgeBaseUpdate,
    ) -> KnowledgeBase:
        kb = self._get_owned_knowledge_base(kb_id=kb_id, user=user)
        data = payload.model_dump(exclude_unset=True)
        return self.repo.update_knowledge_base(kb, data)

    def delete_knowledge_base(self, *, user: User, kb_id: int) -> None:
        kb = self._get_owned_knowledge_base(kb_id=kb_id, user=user)
        self.repo.delete_knowledge_base(kb)

    def list_documents(self, *, user: User, kb_id: int) -> list[Document]:
        self._get_owned_knowledge_base(kb_id=kb_id, user=user)
        return self.repo.list_documents(knowledge_base_id=kb_id)

    def get_document(self, *, user: User, doc_id: int) -> Document:
        return self._get_owned_document(doc_id=doc_id, user=user)

    def list_chunks(self, *, user: User, doc_id: int):
        self._get_owned_document(doc_id=doc_id, user=user)
        return self.repo.list_chunks(document_id=doc_id)

    async def upload_document(
        self,
        *,
        user: User,
        kb_id: int,
        file: UploadFile,
        background_tasks: BackgroundTasks,
    ) -> Document:
        kb = self._get_owned_knowledge_base(kb_id=kb_id, user=user)
        upload_root = Path(settings.upload_dir)
        upload_root.mkdir(parents=True, exist_ok=True)

        try:
            filename, file_path = await save_upload(
                file=file,
                upload_root=upload_root,
                knowledge_base_id=kb.id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        doc = Document(
            knowledge_base_id=kb.id,
            filename=filename,
            content_type=file.content_type,
            file_path=str(file_path),
            status="processing",
            embedding_status="pending",
        )
        doc = self.repo.create_document(doc)
        background_tasks.add_task(_process_document, doc.id)
        return doc

    def delete_document(self, *, user: User, doc_id: int) -> None:
        doc = self._get_owned_document(doc_id=doc_id, user=user)
        if doc.file_path:
            path = Path(doc.file_path)
            if path.exists():
                path.unlink(missing_ok=True)
                if path.parent.exists() and not any(path.parent.iterdir()):
                    path.parent.rmdir()
        self.repo.delete_document(doc)


def _process_document(document_id: int) -> None:
    from app.core.database import SessionLocal

    db = SessionLocal()
    repo = KnowledgeRepository(db)
    doc = repo.get_document(document_id)
    if doc is None or not doc.file_path:
        db.close()
        return

    try:
        raw_text = extract_text(file_path=Path(doc.file_path), filename=doc.filename)
        if not raw_text.strip():
            raise ValueError("No extractable text found in document")

        text_chunks = chunk_text(raw_text)
        if not text_chunks:
            raise ValueError("Document produced no chunks")

        embeddings = embed_texts([chunk.content for chunk in text_chunks])
        payload = [
            (chunk.index, chunk.content, chunk.metadata, embedding)
            for chunk, embedding in zip(text_chunks, embeddings, strict=True)
        ]
        count = store_chunks(db, document_id=doc.id, chunks=payload)

        repo.update_document(
            doc,
            {
                "status": "processed",
                "chunk_count": count,
                "embedding_status": "generated",
                "error_message": None,
            },
        )
        logger.info("Processed document %s with %s chunks", doc.id, count)
    except Exception as exc:
        logger.exception("Failed to process document %s", doc.id)
        repo.update_document(
            doc,
            {
                "status": "failed",
                "embedding_status": "failed",
                "error_message": str(exc),
            },
        )
    finally:
        db.close()
