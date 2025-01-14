
from pydantic import BaseModel


class QueryRequest(BaseModel):
    sql_query: str
