"""Modèle à copier sous le nom `projet/tests/conftest.py`.

Rend importable le paquet de votre langage (le dossier parent de `tests/`) :
`from monlangage.lexer import tokenize` fonctionne alors dans les tests.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
