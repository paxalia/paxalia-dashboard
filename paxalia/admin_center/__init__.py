"""Paxalia Admin: Django-native administration inside the Paxalia Dashboard."""

from .adapter import PaxaliaModelAdapter
from .registry import PaxaliaAdminRegistry, PaxaliaModelCapabilities, PaxaliaModelDefinition, registry

__all__ = [
    "PaxaliaAdminRegistry",
    "PaxaliaModelAdapter",
    "PaxaliaModelCapabilities",
    "PaxaliaModelDefinition",
    "registry",
]

