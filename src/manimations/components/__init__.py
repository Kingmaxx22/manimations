"""Reusable visual component library.

Everything a scene needs to draw is exported here, grouped by concern.  Topic
projects import from ``manimations.components`` and never build raw primitives
themselves, which is what keeps the visual language consistent.
"""

from . import data, network, surfaces, transitions, typography

__all__ = ["typography", "surfaces", "network", "data", "transitions"]
