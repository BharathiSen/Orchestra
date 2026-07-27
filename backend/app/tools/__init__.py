from app.tools.calculator import CalculatorTool
from app.tools.registry import ToolRegistry, default_registry
from app.tools.search import SearchTool
from app.tools.weather import WeatherTool

# Register built-in Day 4 tools once at import time.
_BUILTINS_REGISTERED = False


def ensure_default_tools() -> ToolRegistry:
    global _BUILTINS_REGISTERED
    if not _BUILTINS_REGISTERED:
        for tool in (CalculatorTool(), WeatherTool(), SearchTool()):
            if default_registry.get(tool.name) is None:
                default_registry.register(tool)
        _BUILTINS_REGISTERED = True
    return default_registry


ensure_default_tools()

__all__ = [
    "CalculatorTool",
    "WeatherTool",
    "SearchTool",
    "ToolRegistry",
    "default_registry",
    "ensure_default_tools",
]
