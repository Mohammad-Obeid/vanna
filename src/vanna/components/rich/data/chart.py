"""Chart component for data visualization."""

import math
from typing import Any, Dict, Optional, Union
from pydantic import Field, field_validator
from ....core.rich_component import RichComponent, ComponentType


def sanitize_chart_value(val: Any) -> Any:
    """Sanitize a value for JSON serialization in charts."""
    if val is None:
        return None
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return None
    if isinstance(val, list):
        return [sanitize_chart_value(v) for v in val]
    if isinstance(val, dict):
        return {k: sanitize_chart_value(v) for k, v in val.items()}
    return val


class ChartComponent(RichComponent):
    """Chart component for data visualization."""

    type: ComponentType = ComponentType.CHART
    chart_type: str  # "line", "bar", "pie", "scatter", etc.
    data: Dict[str, Any]  # Chart data in format expected by frontend
    title: Optional[str] = None
    width: Optional[Union[str, int]] = None
    height: Optional[Union[str, int]] = None
    config: Dict[str, Any] = Field(default_factory=dict)  # Chart-specific config

    @field_validator('data', mode='before')
    @classmethod
    def sanitize_data(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize chart data to handle NaN, Infinity values."""
        return sanitize_chart_value(v)
