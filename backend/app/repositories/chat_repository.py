from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Conversation, Message


class ConversationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, conversation: Conversation) -> Conversation:
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def get(self, conversation_id: int) -> Conversation | None:
        return self.db.scalar(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(selectinload(Conversation.messages), selectinload(Conversation.project))
        )

    def list_for_project(self, project_id: int) -> list[Conversation]:
        return list(
            self.db.scalars(
                select(Conversation)
                .where(Conversation.project_id == project_id)
                .order_by(Conversation.updated_at.desc())
            ).all()
        )

    def update(self, conversation: Conversation, data: dict) -> Conversation:
        for key, value in data.items():
            setattr(conversation, key, value)
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def delete(self, conversation: Conversation) -> None:
        self.db.delete(conversation)
        self.db.commit()


class MessageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, message: Message) -> Message:
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def list_for_conversation(self, conversation_id: int) -> list[Message]:
        return list(
            self.db.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.asc(), Message.id.asc())
            ).all()
        )
