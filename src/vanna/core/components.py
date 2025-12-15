"""
UI component base class.

This module defines the UiComponent class which is the return type for tool executions.
It's placed in core/ because it's a fundamental type that tools return, not just a UI concern.
"""

import json
import math
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class SafeJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles special float values and other non-serializable types."""
    def default(self, obj):
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
        if isinstance(obj, Decimal):
            return float(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, bytes):
            return obj.decode('utf-8', errors='replace')
        if isinstance(obj, Enum):
            return obj.value
        return super().default(obj)


def sanitize_for_json(obj: Any) -> Any:
    """Recursively sanitize an object for JSON serialization."""
    if obj is None:
        return None
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, bytes):
        return obj.decode('utf-8', errors='replace')
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(v) for v in obj]
    return obj


class UiComponent(BaseModel):
    """Base class for UI components streamed to client.

    This wraps both rich and simple component representations,
    allowing tools to return structured UI updates.

    Note: We use Any for component types to avoid circular dependencies.
    Type validation happens at runtime through validators.
    """

    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    rich_component: Any = Field(
        ..., description="Rich component for advanced rendering"
    )
    simple_component: Optional[Any] = Field(
        None, description="Simple component for basic rendering"
    )

    @model_validator(mode="after")
    def validate_components(self) -> "UiComponent":
        """Validate that components are the correct types at runtime."""
        # Import from core - clean imports, no circular dependency
        from .rich_component import RichComponent
        from .simple_component import SimpleComponent

        if not isinstance(self.rich_component, RichComponent):
            raise ValueError(
                f"rich_component must be a RichComponent, got {type(self.rich_component)}"
            )

        if self.simple_component is not None and not isinstance(
            self.simple_component, SimpleComponent
        ):
            raise ValueError(
                f"simple_component must be a SimpleComponent or None, got {type(self.simple_component)}"
            )

        return self

    def model_dump_json(self, **kwargs) -> str:
        """Override to use safe JSON serialization that handles NaN, Infinity, etc."""
        data = self.model_dump(**kwargs)
        sanitized = sanitize_for_json(data)
        return json.dumps(sanitized, cls=SafeJSONEncoder)

    model_config = {"arbitrary_types_allowed": True}
