from sqlalchemy.orm import Session
from models import CerSession, CerSessionLog, SessionStatusEnum
from schemas import CerSessionCreate

def create_cer_session(db: Session, session_data: CerSessionCreate) -> CerSession:
    new_session = CerSession(
        user_id=session_data.user_id,
        collection_id=session_data.collection_id,
        title=session_data.title,
        key_events=session_data.key_events,
        model_name=session_data.model_name,
        relevance_score_threshold=session_data.relevance_score_threshold,
        status=SessionStatusEnum.queued
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    log = CerSessionLog(session_id=new_session.id, status=new_session.status)
    db.add(log)
    db.commit()
    db.refresh(new_session)
    return new_session

def get_session_by_id(db: Session, session_id: int) -> CerSession:
    return db.query(CerSession).filter(CerSession.id == session_id).first()

def get_session_by_id_and_user(db: Session, session_id: int, user_id: int) -> CerSession:
    return db.query(CerSession).filter(
        CerSession.id == session_id,
        CerSession.user_id == user_id
    ).first()

def get_sessions_by_user(db: Session, user_id: int) -> list[CerSession]:
    return db.query(CerSession).filter(CerSession.user_id == user_id).all()

def delete_session(db: Session, session_obj: CerSession) -> None:
    db.delete(session_obj)
    db.commit()
