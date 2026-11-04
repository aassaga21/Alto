"""Registre des implementations, separe du contrat pour eviter les cycles."""

from alto.backend import Backend
from alto.formateur import Formateur
from alto.generateur import BackendPython
from alto.generateur_ast import BackendAst

BACKENDS: dict[str, Backend] = {
    "python": BackendPython(),
    "ast": BackendAst(),
    "formateur": Formateur(),
}
