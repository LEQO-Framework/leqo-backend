import os
import sys
from importlib.util import find_spec

# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

# set system path to /leqo-backend/
sys.path.insert(0, os.path.abspath("../"))


def find_module_paths(module_name: str) -> list[str]:
    spec = find_spec(module_name)
    if spec is None:
        return []

    if spec.origin is None:
        return []

    return [os.path.dirname(spec.origin)]


project = "LEQO-Backend"
copyright = "2025, LEQO Backend Team"
author = "Arne Gabriel, Johannes Heugel, Lukas Kurz, Len Lazarus, Louis Radek"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "myst_parser",
    "sphinx.ext.duration",
    "sphinx.ext.doctest",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.intersphinx",
    "sphinxcontrib.openapi",
    "autoapi.extension",
]

# https://sphinx-autoapi.readthedocs.io/en/latest/reference/config.html
autoapi_options = [
    "undoc-members",
]
autoapi_dirs = [*find_module_paths("openqasm3"), "../app"]
autoapi_ignore = ["*migrations*", "*_antlr*"]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master/", None),
    "fastapi": ("https://fastapi.tiangolo.com/", None),
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
}

intersphinx_disabled_domains = ["std"]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
# uncomment if static files are needed: html_static_path = ["_static"]

suppress_warnings = ["autoapi.python_import_resolution", "autoapi.not_readable"]
