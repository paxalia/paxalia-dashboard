"""Backward-compatible import facade for Paxalia authentication views.

The canonical implementation lives in ``paxalia.views.auth``. Keeping this
module as a facade prevents the package from carrying a second, divergent
authentication implementation with different session semantics.
"""
from __future__ import annotations

from .views.auth import *  # noqa: F401,F403
