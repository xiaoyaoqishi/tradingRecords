from pydantic import BaseModel


class RecycleResponse(BaseModel):
    ok: bool = True
