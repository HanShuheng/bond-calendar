from __future__ import annotations

import importlib
from typing import Any

from .base import SourceAdapter
from .eastmoney import EastmoneyAdapter
from .jisilu import JisiluAdapter


BUILTIN_ADAPTERS: dict[str, type[SourceAdapter]] = {
    "eastmoney": EastmoneyAdapter,
    "jisilu": JisiluAdapter,
}


def resolve_adapter(source: str, settings: dict[str, object]) -> type[SourceAdapter] | None:
    adapter_path = settings.get("class")
    if adapter_path:
        return import_adapter_class(str(adapter_path))
    return BUILTIN_ADAPTERS.get(source)


def import_adapter_class(adapter_path: str) -> type[SourceAdapter]:
    module_name, _, class_name = adapter_path.replace(":", ".").rpartition(".")
    if not module_name or not class_name:
        raise ValueError(f"Adapter class path must look like 'module:Class': {adapter_path!r}")

    module = importlib.import_module(module_name)
    adapter_class: Any = getattr(module, class_name)
    if not callable(adapter_class):
        raise TypeError(f"Adapter target is not callable: {adapter_path!r}")
    return adapter_class


__all__ = [
    "BUILTIN_ADAPTERS",
    "resolve_adapter",
    "SourceAdapter",
    "EastmoneyAdapter",
    "JisiluAdapter",
]
