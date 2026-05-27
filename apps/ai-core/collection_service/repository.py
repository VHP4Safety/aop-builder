from sqlalchemy.orm import Session
from models import Collection
from schemas import CollectionCreate

class CollectionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_collection(self, collection_data: CollectionCreate) -> Collection:
        collection = Collection(
            user_id=collection_data.user_id,
            name=collection_data.name,
            description=collection_data.description,
            status="unscanned"
        )
        self.db.add(collection)
        self.db.commit()
        self.db.refresh(collection)
        return collection

    def get_collections_by_user(self, user_id: int):
        return self.db.query(Collection).filter(Collection.user_id == user_id).all()

    def get_collection_by_id(self, collection_id: int):
        return self.db.query(Collection).filter(Collection.id == collection_id).first()

    def update_collection_status(self, collection_id: int, new_status: str):
        """Update the status of a collection"""
        collection = self.get_collection_by_id(collection_id)
        if collection:
            collection.status = new_status
            self.db.commit()
            self.db.refresh(collection)
        return collection
