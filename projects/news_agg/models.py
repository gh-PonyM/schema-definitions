from sqlmodel import Field, SQLModel
from datetime import datetime


class ScrapeResult(SQLModel, table=True):
    id: int = Field(primary_key=True)
    created: datetime
    html: str
    url: str
