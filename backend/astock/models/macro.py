from sqlmodel import Field, SQLModel


class MacroValue(SQLModel, table=True):
    """全球宏观月度指标长表：按 region + period + metric 存储。"""

    __tablename__ = "macro_value"

    region: str = Field(primary_key=True, description="区域 cn / us")
    period: str = Field(primary_key=True, description="所属月份 YYYY-MM")
    metric: str = Field(primary_key=True, description="指标代码")
    value: float = Field(description="指标数值")
    cached_at: str


# 指标代码常量（不入库展示名）
METRIC_CPI_YOY = "cpi_yoy"
METRIC_PPI_YOY = "ppi_yoy"
METRIC_PMI_MFG = "pmi_manufacturing"
METRIC_PMI_NON_MFG = "pmi_non_manufacturing"
METRIC_CONSUMER_CONFIDENCE = "consumer_confidence"
METRIC_FED_RATE_UPPER = "fed_rate_upper"

REGION_CN = "cn"
REGION_US = "us"
