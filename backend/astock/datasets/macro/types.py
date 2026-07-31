"""宏观 region / metric 字面量约束。"""

from typing import Literal

MacroRegion = Literal["cn", "us"]
MacroMetric = Literal[
    "cpi_yoy",
    "ppi_yoy",
    "pmi_manufacturing",
    "pmi_non_manufacturing",
    "consumer_confidence",
    "fed_rate_upper",
]
