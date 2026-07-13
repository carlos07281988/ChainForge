"""Domain errors for ChainForge."""

from __future__ import annotations


class ChainForgeError(Exception):
    """Base error for all ChainForge exceptions."""


class ProviderError(ChainForgeError):
    """An LLM provider returned an error."""


class ToolExecutionError(ChainForgeError):
    """A tool raised during execution."""


class ConfigurationError(ChainForgeError):
    """Invalid configuration."""


class MaxIterationsError(ChainForgeError):
    """Agent exceeded max iterations."""
