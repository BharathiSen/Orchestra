"""Knowledge base repository — database operations only."""

from sqlalchemy.orm import Session, joinedload

from app.models import Document, DocumentChunk, KnowledgeBase


class KnowledgeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Knowledge bases ---

    def create_knowledge_base(self, kb: KnowledgeBase) -> KnowledgeBase:
        self.db.add(kb)
        self.db.commit()
        self.db.refresh(kb)
        return kb

    def get_knowledge_base(self, kb_id: int) -> KnowledgeBase | None:
        return (
            self.db.query(KnowledgeBase)
            .options(joinedload(KnowledgeBase.project), joinedload(KnowledgeBase.documents))
            .filter(KnowledgeBase.id == kb_id)
            .first()
        )

    def list_knowledge_bases(self, *, project_id: int) -> list[KnowledgeBase]:
        return (
            self.db.query(KnowledgeBase)
            .options(joinedload(KnowledgeBase.documents))
            .filter(KnowledgeBase.project_id == project_id)
            .order_by(KnowledgeBase.updated_at.desc())
            .all()
        )

    def update_knowledge_base(self, kb: KnowledgeBase, data: dict) -> KnowledgeBase:
        for key, value in data.items():
            setattr(kb, key, value)
        self.db.commit()
        self.db.refresh(kb)
        return kb

    def delete_knowledge_base(self, kb: KnowledgeBase) -> None:
        self.db.delete(kb)
        self.db.commit()

    # --- Documents ---

    def create_document(self, doc: Document) -> Document:
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def get_document(self, doc_id: int) -> Document | None:
        return (
            self.db.query(Document)
            .options(joinedload(Document.knowledge_base).joinedload(KnowledgeBase.project))
            .filter(Document.id == doc_id)
            .first()
        )

    def list_documents(self, *, knowledge_base_id: int) -> list[Document]:
        return (
            self.db.query(Document)
            .filter(Document.knowledge_base_id == knowledge_base_id)
            .order_by(Document.created_at.desc())
            .all()
        )

    def update_document(self, doc: Document, data: dict) -> Document:
        for key, value in data.items():
            setattr(doc, key, value)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def delete_document(self, doc: Document) -> None:
        self.db.delete(doc)
        self.db.commit()

    # --- Chunks ---

    def list_chunks(self, *, document_id: int) -> list[DocumentChunk]:
        return (
            self.db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
            .all()
        )
