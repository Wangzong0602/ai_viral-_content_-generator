"""
内容模板的数据模型（Pydantic v2 响应校验）
"""

import json

from pydantic import BaseModel, Field


class TemplateOut(BaseModel):
    """模板信息（响应用）。"""

    id: int
    name: str
    platform: str
    description: str = ""
    # structure 是 JSON 字符串，转为字典返回给前端展示
    structure: dict = Field(default_factory=dict)

    @classmethod
    def from_model(cls, template) -> "TemplateOut":
        """从 ORM 模型转换（解析 structure JSON）。"""
        try:
            structure = json.loads(template.structure or "{}")
        except json.JSONDecodeError:
            structure = {}
        return cls(
            id=template.id,
            name=template.name,
            platform=template.platform,
            description=template.description,
            structure=structure,
        )
