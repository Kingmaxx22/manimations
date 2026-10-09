"""Manimations — an automated 2D educational motion-graphics system.

Public API::

    from manimations import ExplainerScene, components, theme, config

Topic projects import the framework, never the other way around.
"""

from . import components, helpers, theme
from .config import ConfigError, ProjectConfig, SceneSpec
from .scene import ExplainerScene
from .theme import THEME, Theme, apply_theme

__version__ = "0.1.0"

__all__ = [
    "ExplainerScene",
    "Theme",
    "THEME",
    "apply_theme",
    "components",
    "helpers",
    "theme",
    "ProjectConfig",
    "SceneSpec",
    "ConfigError",
    "__version__",
]
