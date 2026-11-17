from typing import Literal
from pydantic import BaseModel,ConfigDict

class DesignOptions(BaseModel):
    model_config=ConfigDict(extra='forbid')
    roof: Literal['classic','snowflake','peppermint','stars','hearts']='classic'
    wall: Literal['classic','brick','timber','holly','hearts']='classic'
    tree: Literal['classic','slim','rounded','tiered','star','candy']='classic'
    gift: Literal['classic','stripes','dots','snowflake','holly','stars']='classic'

OPTIONS={
 'roof':[('classic','Kem tuyết & kẹo'),('snowflake','Bông tuyết'),('peppermint','Kẹo bạc hà'),('stars','Đêm sao'),('hearts','Trái tim Noel')],
 'wall':[('classic','Bánh gừng cổ điển'),('brick','Gạch kem'),('timber','Vân gỗ'),('holly','Lá nhựa ruồi'),('hearts','Trái tim đường')],
 'tree':[('classic','Thông Noel cổ điển'),('slim','Thông thanh mảnh'),('rounded','Thông tán tròn'),('tiered','Thông nhiều tầng'),('star','Thông ngôi sao'),('candy','Thông kẹo ngọt')],
 'gift':[('classic','Quà Noel cổ điển'),('stripes','Quà sọc kẹo'),('dots','Quà chấm bi'),('snowflake','Quà bông tuyết'),('holly','Quà lá Noel'),('stars','Quà sao vàng')],
}

def apply_design(t,design):
    values=DesignOptions(**(design or {})).model_dump()
    return {**t,'design':values} if values!=DesignOptions().model_dump() else dict(t)
