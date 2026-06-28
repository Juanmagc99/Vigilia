from typing import Annotated, Generator

from fastapi import Depends
from sqlalchemy import create_engine
from sqlmodel import Session

from app.core.config import settings


engine = create_engine(settings.database_url, echo=False)

def get_session() -> Generator[Session]:
    with Session(engine) as session:
        yield session

DatabaseSession = Annotated[Session, Depends(get_session)]