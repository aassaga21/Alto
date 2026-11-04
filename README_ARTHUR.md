# Partie Arthur : generation de Python et extension AST

Implementation adaptee aux noeuds de `alto/noeuds.py` et a la specification actuelle.
Python **3.12 minimum** (le depot utilise les alias `type` de Python 3.12).

## Fichiers realises

- `alto/emetteur.py` : emission indentee, context manager `bloc()`, `pass` pour les blocs vides.
- `alto/generateur.py` : traduction exhaustive avec `match` et `assert_never`, prelude Alto,
  resolution des noms et points d'entree `generer`, `transpiler`, `executer`.
- `alto/generateur_ast.py` : construction directe des noeuds `ast` Python ; seules les fonctions
  du prelude fixe passent par `ast.parse`. Les lignes des noeuds utilisateur viennent du source Alto.
- `tests/test_etape_08_generation.py` : les cinq exemples compares aux fichiers `.attendu`
  pour les deux backends, plus les cas de portee, recursion, listes et erreurs.
- `tests/test_etape_11_ast.py` : compilation de l'arbre, construction directe et ligne
  d'une erreur dans une fonction.
- `.github/workflows/qualite.yml` : pytest, ruff et mypy sur Python 3.12.

## Utilisation

Depuis la racine du depot :

```python
from alto.generateur import executer, transpiler

code_python = transpiler("ecris 7 / 2;")
executer("ecris 7 / 2;")  # 3.5
```

`executer` recoit du **source Alto**, pas du Python deja genere. Pour executer
le resultat de `transpiler`, utiliser `exec(compile(code_python, "<alto>", "exec"), {})`.
`generer(programme)` accepte un AST Alto construit manuellement et le verifie avant generation.

Pour l'extension :

```python
from alto.generateur_ast import generer_ast, transpiler_ast
from alto.parser import parse

arbre_python = generer_ast(parse("ecris 42;"))
exec(compile(arbre_python, "<alto>", "exec"), {"__name__": "__main__"})
code_python = transpiler_ast("ecris 42;")
```

## Regles de traduction

- `/` produit un decimal ; **aucun operateur `div`** dans la specification actuelle.
- `taille`, `ajoute` et `texte` sont les trois fonctions predefinies.
- Les booleens et l'absence de valeur s'affichent `vrai`, `faux`, `rien`, y compris dans les listes.
- Chaque declaration recoit un nom Python distinct : les blocs voisins et les variables locales
  ne peuvent pas modifier une globale homonyme declaree plus tard. Les mots-cles et builtins Python
  restent utilisables comme noms Alto. Les noms sont encodes pour eviter les collisions Unicode.
- Le masquage d'un nom visible est refuse par l'analyse semantique existante.
- Les globales affectees dans une fonction utilisent `Analyse.globales_modifiees`.
- Les operations sont parenthesees pour conserver les priorites et eviter les comparaisons chainees.
- `et` et `ou` conservent leur court-circuit. Les bornes de `pour` sont inclusives, evaluees
  une seule fois et verifiees comme entiers (les booleens sont refuses).

## Verification

Avec uv, si disponible :

```bash
uv sync
uv run pytest
uv run ruff check .
uv run mypy alto
```

Ou dans un environnement Python classique :

```bash
python -m venv .venv
# Activer .venv selon le terminal, puis :
python -m pip install pytest ruff mypy
python -m pytest
python -m ruff check .
python -m mypy alto
```

## Integration avec les autres parties

Aucun noeud provisoire n'est fourni : les generateurs utilisent directement les modules
lexer, parser et semantique du depot. `exemples/04_listes.alt` et sa sortie sont verifies
par le test central sans modification.

La facade CLI d'Alexandra et le contrat `Backend` de Fatoumata sont integres :

- `BackendPython` et `BackendAst` implementent `generer(programme, analyse) -> Sortie`.
- `alto/backends.py` porte le registre `BACKENDS`, separe du contrat pour eviter les cycles.
- `alto.compilateur.transpiler(source, backend="python")` renvoie une `Sortie`, tandis que
  `alto.generateur.transpiler(source)` conserve son interface historique retournant un `str`.
- `alto.compilateur.executer(source, backend="python")` traduit les exceptions Python en
  `ErreurExecution` avec la ligne source. Les lignes du prelude ne sont pas attribuees
  au programme ; une erreur dans une predefinie pointe son appel dans le source.
- La CLI accepte `--backend python` et `--backend ast` pour `run` et `transpile`.
- `tests/test_integration_backends.py` verifie les exemples, les fichiers Python produits,
  les erreurs dans les fonctions/blocs et l'extension du registre sans modifier la facade.

```bash
python -m alto run exemples/04_listes.alt --backend ast
python -m alto transpile exemples/01_bonjour.alt -o bonjour.py
```

Le REPL et le formateur ne sont pas implementes dans cette integration.
