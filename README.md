# Alto

Alto est un petit langage de programmation aux mots-clés français, conçu dans le cadre du cours Python avancé du Geneva Institute of Technology.

Un programme Alto (`.alt`) est traduit en Python puis exécuté :

    python -m alto run programme.alt

Le transpileur est entièrement écrit à la main, sans générateur de parser :
lexer → parser → analyse sémantique → génération de Python.

## Partie Arthur : generation et tests

La generation Python (etape 8) et le generateur AST Python (extension 11) sont implementes.
Ils utilisent les noeuds, le parser et l'analyse semantique actuels du depot.

- `alto/emetteur.py` : indentation et blocs vides.
- `alto/generateur.py` : traduction en Python, affichage Alto et execution.
- `alto/generateur_ast.py` : construction directe d'un `ast.Module` executable.
- `tests/test_etape_08_generation.py` et `tests/test_etape_11_ast.py` : les cinq exemples
  sur les deux generateurs, les portees, les globales et les lignes source.

```bash
python -c "from alto.generateur import executer; executer('ecris 42;')"
```

Python **3.12 minimum**. Voir [README_ARTHUR.md](README_ARTHUR.md) pour les interfaces,
les commandes de verification et les points d'integration restants avec la CLI et les backends.
La CLI est branchee aux deux generateurs :

```bash
python -m alto check exemples/01_bonjour.alt
python -m alto run exemples/04_listes.alt
python -m alto run exemples/04_listes.alt --backend ast
python -m alto transpile exemples/01_bonjour.alt --backend python -o bonjour.py
```

Les erreurs d'execution indiquent la ligne Alto fautive. Le REPL reste a implementer.
