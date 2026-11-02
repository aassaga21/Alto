# Étape 4 : l'arbre syntaxique (AST)

**Qui :** Luca. **Fichiers :** `alto/noeuds.py`, `tests/test_etape_04_ast.py`. **Énoncé :** `langage/etapes/04_ast.md`.

> **En une phrase :** créer une petite classe Python pour chaque construction d'Alto (une addition, un `si`, une boucle…), pour que le parser puisse représenter un programme comme un arbre d'objets.

⚡ **Priorité équipe :** Fatoumata (parser), Arthur (générateur) et toi-même (sémantique) utilisez ces classes. Pousse les dataclasses **le jour 1**, `afficher_arbre` peut attendre.

## 1. Comprendre

Le texte `1 + 2 * x` est une suite de caractères. Pour le traduire ou le vérifier, on a besoin de sa **structure** : « une addition dont la gauche est 1 et la droite une multiplication ». C'est un arbre :

```
        Binaire '+'
        /         \
   Entier 1     Binaire '*'
                 /       \
            Entier 2   Variable x
```

En Python, ça s'écrit :

```python
Binaire("+", Entier(1), Binaire("*", Entier(2), Variable("x")))
```

Il y a deux familles de nœuds :

| Famille | Ce que c'est | Nœuds d'Alto |
|---|---|---|
| **`Expr`** (expressions) | ce qui a une **valeur** | `Entier`, `Decimal`, `Texte`, `Booleen`, `Rien`, `Variable`, `Liste`, `Unaire`, `Binaire`, `Appel`, `Index` |
| **`Instr`** (instructions) | ce qui **s'exécute** | `Declaration`, `Affectation`, `Ecris`, `Si`, `TantQue`, `Pour`, `Fonction`, `Rends`, `ExprInstr` |

Plus trois nœuds « de structure » : `Bloc` (une suite d'instructions entre accolades), `Branche` (une condition et son bloc, pour `si`) et `Programme` (la racine).

### Comment passer de la grammaire aux nœuds

- Une règle qui **assemble des morceaux** devient une dataclass, avec un champ par morceau **utile** (pas les mots-clés ni la ponctuation) :
  `pour = "pour" IDENT "de" expression "jusqua" expression bloc` → `Pour(variable: str, debut: Expr, fin: Expr, corps: Bloc)`.
- Une règle qui n'est qu'un **choix** (`instruction = declaration | si | …`) devient une **union** de types.
- Les règles de priorité (`somme`, `produit`…) **disparaissent** : elles deviennent toutes des `Binaire`, avec l'opérateur dans le champ `op`.

## 2. Le Python à connaître

### `field(...)` pour régler un champ

```python
from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class Entier:
    valeur: int
    pos: Position = field(default=SANS_POSITION, compare=False, repr=False)
```

- `default=SANS_POSITION` : on peut écrire `Entier(1)` sans position (pratique dans les tests).
- `compare=False` : deux `Entier(1)` à des positions différentes sont **égaux**. Ainsi, un test peut comparer l'arbre produit par le parser à un arbre écrit à la main.
- `repr=False` : la position n'encombre pas l'affichage.

### Les unions de types avec `type`

```python
type Expr = Entier | Decimal | Texte | Binaire | ...
```

Ça veut dire : « une `Expr`, c'est un `Entier` **ou** un `Decimal` **ou**… ». L'union peut être récursive (`Binaire` contient des `Expr`).

### Les enfants multiples dans des `tuple`

On écrit `arguments: tuple[Expr, ...]` et pas `list[Expr]` : un tuple est immuable, donc tout l'arbre l'est.

## 3. Pas à pas

### 3.1 Les expressions

```python
"""Les nœuds de l'arbre syntaxique d'Alto."""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass

from alto.erreurs import SANS_POSITION, Position


@dataclass(frozen=True, slots=True)
class Entier:
    valeur: int
    pos: Position = field(default=SANS_POSITION, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Decimal:
    valeur: float
    pos: Position = field(default=SANS_POSITION, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Texte:
    valeur: str
    pos: Position = field(default=SANS_POSITION, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Booleen:
    valeur: bool
    pos: Position = field(default=SANS_POSITION, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Rien:
    pos: Position = field(default=SANS_POSITION, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Variable:
    nom: str
    pos: Position = field(default=SANS_POSITION, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Liste:
    elements: tuple[Expr, ...]
    pos: Position = field(default=SANS_POSITION, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Unaire:
    op: str  # "-" ou "non"
    operande: Expr
    pos: Position = field(default=SANS_POSITION, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Binaire:
    op: str  # le lexème : "+", "==", "et", ...
    gauche: Expr
    droite: Expr
    pos: Position = field(default=SANS_POSITION, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Appel:
    nom: str  # seule une fonction nommée peut être appelée
    arguments: tuple[Expr, ...]
    pos: Position = field(default=SANS_POSITION, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Index:
    cible: Expr
    indice: Expr
    pos: Position = field(default=SANS_POSITION, compare=False, repr=False)


type Expr = (
    Entier | Decimal | Texte | Booleen | Rien | Variable | Liste | Unaire | Binaire | Appel | Index
)
```

> `Binaire` utilise `Expr`, défini plus bas : c'est `from __future__ import annotations` qui rend cela possible.

### 3.2 Les instructions (à toi de jouer)

Sur le même modèle, écris : `Bloc(instructions)`, `Declaration(nom, valeur)`, `Affectation(cible, valeur)`, `Ecris(valeurs)`, `Branche(condition, corps)`, `Si(branches, sinon)`, `TantQue(condition, corps)`, `Pour(variable, debut, fin, corps)`, `Fonction(nom, parametres, corps)`, `Rends(valeur)`, `ExprInstr(expr)`, puis l'union `Instr` et `Programme`.

Questions à se poser pour chaque champ : quel type ? peut-il être absent (`| None`) ? y en a-t-il plusieurs (`tuple[..., ...]`) ?

<details>
<summary>▶ Solution</summary>

```python
@dataclass(frozen=True, slots=True)
class Bloc:
    instructions: tuple[Instr, ...]
    pos: Position = field(default=SANS_POSITION, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Declaration:
    nom: str
    valeur: Expr
    pos: Position = field(default=SANS_POSITION, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Affectation:
    cible: Variable | Index  # x = ... ou t[i] = ...
    valeur: Expr
    pos: Position = field(default=SANS_POSITION, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Ecris:
    valeurs: tuple[Expr, ...]
    pos: Position = field(default=SANS_POSITION, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Branche:
    condition: Expr
    corps: Bloc
    pos: Position = field(default=SANS_POSITION, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Si:
    branches: tuple[Branche, ...]  # le si, puis chaque sinon si
    sinon: Bloc | None              # le sinon final, s'il existe
    pos: Position = field(default=SANS_POSITION, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class TantQue:
    condition: Expr
    corps: Bloc
    pos: Position = field(default=SANS_POSITION, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Pour:
    variable: str
    debut: Expr
    fin: Expr
    corps: Bloc
    pos: Position = field(default=SANS_POSITION, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Fonction:
    nom: str
    parametres: tuple[str, ...]
    corps: Bloc
    pos: Position = field(default=SANS_POSITION, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class Rends:
    valeur: Expr | None  # `rends;` sans valeur
    pos: Position = field(default=SANS_POSITION, compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class ExprInstr:
    """Une expression utilisée comme instruction : `ajoute(l, 3);`"""

    expr: Expr
    pos: Position = field(default=SANS_POSITION, compare=False, repr=False)


type Instr = Declaration | Affectation | Ecris | Si | TantQue | Pour | Fonction | Rends | ExprInstr


@dataclass(frozen=True, slots=True)
class Programme:
    instructions: tuple[Instr, ...]
```

</details>

**Pourquoi un nœud `Si` avec une liste de branches ?** Parce que `si … sinon si … sinon si … sinon` se traduira directement en `if … elif … elif … else` à l'étape 8.

### 3.3 `afficher_arbre` : voir l'arbre

On veut obtenir, pour `si n <= 1 { rends n * 2; }` :

```
Si sinon=None
└── branches[0]: Branche
    ├── condition: Binaire op='<='
    │   ├── gauche: Variable nom='n'
    │   └── droite: Entier valeur=1
    └── corps: Bloc
        └── instructions[0]: Rends
            └── valeur: Binaire op='*'
                ├── gauche: Variable nom='n'
                └── droite: Entier valeur=2
```

**Sans écrire une ligne par type de nœud.** L'outil : `dataclasses.fields(noeud)` donne la liste des champs de **n'importe quelle** dataclass. Pour chaque champ :

- si c'est un nœud (une dataclass), ou un tuple de nœuds → c'est un **enfant** : on l'affiche sur les lignes suivantes, en récursion ;
- sinon (un `str`, un `int`, `None`…) → c'est un **attribut** : on l'affiche sur la même ligne (`op='+'`).

Les préfixes : `├── ` pour un enfant qui n'est pas le dernier, `└── ` pour le dernier ; et pour les petits-enfants on ajoute `│   ` (ou `    ` sous le dernier).

<details>
<summary>▶ Solution</summary>

```python
def _est_noeud(valeur: object) -> bool:
    return is_dataclass(valeur) and not isinstance(valeur, type)


def afficher_arbre(noeud: object) -> str:
    lignes: list[str] = []
    _afficher(noeud, "", "", "", lignes)
    return "\n".join(lignes)


def _afficher(
    noeud: object, etiquette: str, prefixe: str, prefixe_enfants: str, lignes: list[str]
) -> None:
    attributs: list[str] = []
    enfants: list[tuple[str, object]] = []
    for f in fields(noeud):  # type: ignore[arg-type]
        if f.name == "pos":
            continue
        valeur = getattr(noeud, f.name)
        if _est_noeud(valeur):
            enfants.append((f.name, valeur))
        elif isinstance(valeur, tuple) and valeur and all(_est_noeud(v) for v in valeur):
            enfants.extend((f"{f.name}[{i}]", v) for i, v in enumerate(valeur))
        else:
            attributs.append(f"{f.name}={valeur!r}")

    titre = type(noeud).__name__ + "".join(" " + a for a in attributs)
    lignes.append(prefixe + (f"{etiquette}: " if etiquette else "") + titre)

    for i, (nom, enfant) in enumerate(enfants):
        dernier = i == len(enfants) - 1
        _afficher(
            enfant,
            nom,
            prefixe_enfants + ("└── " if dernier else "├── "),
            prefixe_enfants + ("    " if dernier else "│   "),
            lignes,
        )
```

</details>

## 4. Les tests à écrire

`tests/test_etape_04_ast.py` :

```python
import dataclasses

import pytest

from alto.erreurs import Position
from alto.noeuds import Binaire, Entier, Variable, afficher_arbre


def test_les_noeuds_sont_immuables() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        Entier(1).valeur = 2  # type: ignore[misc]


def test_la_position_n_intervient_pas_dans_l_egalite() -> None:
    assert Entier(1, Position(1, 1)) == Entier(1, Position(5, 9))
    assert "Position" not in repr(Entier(1, Position(1, 1)))


def test_afficher_arbre() -> None:
    arbre = Binaire("+", Entier(1), Binaire("*", Variable("x"), Entier(2)))
    assert afficher_arbre(arbre) == (
        "Binaire op='+'\n"
        "├── gauche: Entier valeur=1\n"
        "└── droite: Binaire op='*'\n"
        "    ├── gauche: Variable nom='x'\n"
        "    └── droite: Entier valeur=2"
    )


def test_asdict_fonctionne() -> None:
    assert dataclasses.asdict(Entier(3))["valeur"] == 3
```

À ajouter : un nœud construit sans position est accepté ; `afficher_arbre` sur un `Si` avec un `sinon`, et sur un `Appel` à plusieurs arguments (`arguments[0]`, `arguments[1]`).

## 5. Pièges fréquents

| Symptôme | Cause |
|---|---|
| `NameError: Expr` | il manque `from __future__ import annotations` en tête du fichier |
| `TypeError: non-default argument follows default argument` | `pos` (qui a une valeur par défaut) doit être le **dernier** champ |
| deux arbres identiques ne sont pas égaux dans un test | `compare=False` oublié sur `pos` |
| un module nommé `ast.py` casse des choses bizarres | il faut l'appeler `noeuds.py` |

## 6. C'est fini quand…

- [ ] `uv run pytest -k etape_04` est vert ;
- [ ] chaque construction de la grammaire a son nœud ;
- [ ] la PR est fusionnée → **préviens Fatoumata et Arthur**.
- [ ] Tu peux passer à l'étape 7 (sémantique) **sans attendre le parser** : construis tes arbres à la main dans les tests.
