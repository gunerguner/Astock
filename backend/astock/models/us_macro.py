from sqlmodel import Field, SQLModel


class UsMacroPoint(SQLModel, table=True):
    """美国宏观月度序列：CPI 同比 + 联邦基金目标利率上限。"""

    __tablename__ = "us_macro_point"

    period: str = Field(primary_key=True, description="所属月份 YYYY-MM")
    cpi_yoy: float | None = Field(default=None, description="CPI 同比 %")
    fed_rate_upper: float | None = Field(default=None, description="联邦基金目标利率上限 %")
    cached_at: str
