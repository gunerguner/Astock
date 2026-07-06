from typing import Annotated

from fastapi import Depends
from sqlmodel import Session

from astock.core.database import get_db

DbSession = Annotated[Session, Depends(get_db)]
