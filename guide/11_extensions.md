# Les extensions (au choix, après l'étape 10)

**Qui :** Arthur (11), Luca (12), le premier ou la première libre (13). **Énoncés :** `langage/etapes/11_module_ast.md`, `12_typage_statique.md`, `13_source_maps.md`.

Ne commencez une extension que lorsque **les étapes 1 à 10 marchent de bout en bout** et que le test central est vert. Une chaîne complète vaut plus qu'une extension de plus.

Chaque extension se branche sur ce qui existe déjà, sans le casser : c'est la preuve que le découpage du projet est bon.

---

## Extension 11 : générer du Python avec le module `ast`

> **En une phrase :** au lieu d'écrire du texte Python à la main, construire un **arbre Python** (`ast.Module`) et laisser `ast.unparse` produire le texte.

**Pourquoi c'est mieux :** `ast.unparse` met les parenthèses **là où il faut seulement**, et chaque nœud Python peut porter la ligne Alto d'où il vient (`lineno`) : les erreurs d'exécution pointent la bonne ligne sans `correspondance` à la main.

```python
import ast

arbre = ast.Module(
    body=[ast.Expr(ast.Call(ast.Name("print", ast.Load()), [ast.Constant(42)], []))],
    type_ignores=[],
)
ast.fix_missing_locations(arbre)
print(ast.unparse(arbre))            # print(42)
exec(compile(arbre, "<alto>", "exec"))  # 42
```

**Pas à pas :**

1. `alto/generateur_ast.py` : une classe `GenerateurAst` (`nom = "ast"`, `executable = True`) qui a la forme du `Protocol` `Backend`.
2. Traduire chaque expression : `Entier(v)` → `ast.Constant(v)`, `Variable(n)` → `ast.Name(nom_python(n), ast.Load())`, `Binaire("+", g, d)` → `ast.BinOp(g, ast.Add(), d)`, `Binaire("<", …)` → `ast.Compare(g, [ast.Lt()], [d])`, `et` → `ast.BoolOp(ast.And(), [g, d])`…
3. Traduire chaque instruction : `Declaration` → `ast.Assign([ast.Name(nom, ast.Store())], valeur)`, `Si` → `ast.If` (les `sinon si` deviennent un `ast.If` dans le `orelse`), `Pour` → `ast.For` sur `range(debut, fin + 1)`, `Fonction` → `ast.FunctionDef` (avec un `ast.Global` si besoin)…
4. Réutiliser `PRELUDE` et `nom_python` du générateur texte.
5. Donner à chaque nœud `lineno = noeud.pos.ligne` (puis `ast.fix_missing_locations`).
6. L'ajouter à `BACKENDS` : `--backend ast` apparaît dans la CLI **sans la modifier**.

**Test clé :** le test central (les 5 exemples) passe aussi avec `backend="ast"` — paramétrez-le sur les deux backends.

---

## Extension 12 : le typage statique

> **En une phrase :** permettre d'écrire `var x: entier = 3;` et `fonction f(n: entier) -> texte`, et refuser à la compilation `var x: entier = "a";`.

**Pas à pas :**

1. **Spécification d'abord** : ajouter une section *Types* à `specification.md` : les types (`entier`, `decimal`, `texte`, `booleen`, `liste`, `rien`), la syntaxe des annotations, la règle « un `entier` est accepté là où un `decimal` est attendu », et une table qui donne le type de chaque expression (`entier + entier` → `entier`, `/` → `decimal`, comparaisons → `booleen`…).
2. **Typage graduel** : une valeur sans annotation a le type inconnu `?`, compatible avec tout. On ne signale une erreur que lorsqu'on **sait** que les types ne collent pas. Ainsi, les programmes existants (sans annotations) restent valides.
3. Lexer : ajouter les tokens `:` et `->`, et les mots-clés de types. Parser : les annotations facultatives. Nœuds : un champ `type` facultatif sur `Declaration`, sur les paramètres, sur `Fonction`.
4. `alto/typage.py` : un `Enum` des types et une fonction `compatible(attendu, recu)`.
5. Dans l'analyseur, faire **renvoyer un type** à chaque `expression(...)`, et vérifier : déclarations, affectations, arguments, `rends`, conditions de `si` / `tantque` (`booleen`), bornes de `pour` (`entier`).
6. `ErreurType`, sous-classe d'`ErreurSemantique` : collectée avec les autres erreurs.

**Tests clés :** chaque ligne de la table des types ; les 5 exemples (non annotés) passent toujours ; un exemple annoté de plus dans `exemples/`.

---

## Extension 13 : les source maps

> **En une phrase :** enregistrer dans un fichier JSON la correspondance « ligne Python → ligne Alto » que l'émetteur calcule déjà depuis l'étape 9.

**Pas à pas :**

1. `alto/sourcemap.py` : une dataclass `SourceMap` (le `dict[int, int]`) et un `TypedDict` de sa forme JSON, avec un numéro de version en `Literal[1]` :

   ```python
   class SourceMapJson(TypedDict):
       version: Literal[1]
       source: str
       lignes: dict[str, int]   # les clés JSON sont toujours des chaînes
   ```

2. Remplacer `correspondance: dict[int, int]` par `sourcemap: SourceMap` dans `Sortie`, en tenant compte du décalage du prélude (c'est déjà fait dans `BackendPython`).
3. `transpile --sourcemap` écrit `<sortie>.map.json` à côté du fichier généré.
4. Relire un fichier JSON : **refuser une version inconnue** avec un message clair.
5. Se servir de la `SourceMap` dans `_traduire` (à la place du `dict`).

**Tests clés :** écrire puis relire une source map donne la même ; une version `2` est refusée ; une erreur d'exécution au fond d'une fonction pointe toujours la bonne ligne.
