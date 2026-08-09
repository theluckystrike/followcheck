"""Sphinx configuration for the followcheck documentation."""

import os
import sys

sys.path.insert(0, os.path.abspath("../src"))

project = "followcheck"
author = "Michal Lip"
copyright = "2026, Michal Lip"
release = "0.1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

templates_path = []
exclude_patterns = ["_build"]

html_theme = "alabaster"
html_static_path = []
html_title = "followcheck"
html_baseurl = "https://followcheck.readthedocs.io/"

html_theme_options = {
    "description": "Is that outbound link really followable? Check it, do not assume it.",
    "github_user": "theluckystrike",
    "github_repo": "followcheck",
    "github_button": False,
    "fixed_sidebar": True,
}

autodoc_member_order = "bysource"
autodoc_typehints = "description"
