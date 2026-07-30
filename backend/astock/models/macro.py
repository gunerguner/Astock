from sqlalchemy import Column
from sqlalchemy import Enum as SAEnum
from sqlmodel import Field, SQLModel


class MacroValue(SQLModel, table=True):
    """全球宏观月度指标长表：按 region + period + metric 存储。"""

    __tablename__ = "macro_value"

    region: str = Field(
        description="区域 cn / us",
        sa_column=Column(SAEnum("cn", "us"), primary_key=True),
    )
    period: str = Field(primary_key=True, description="所属月份 YYYY-MM")
    metric: str = Field(
        description="指标代码",
        sa_column=Column(
            SAEnum(
                "cpi_yoy",
                "ppi_yoy",
                "pmi_manufacturing",
                "pmi_non_manufacturing",
                "consumer_confidence",
                "fed_rate_upper",
            ),
            primary_key=True,
        ),
    )
    value: float = Field(description="指标数值")
    cached_at: str
