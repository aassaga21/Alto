"""Les nœuds de l'arbre syntaxique d'Alto."""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass

from alto.erreurs import SANS_POSITION, Position

# --- Expressions ---------------------------------------------------------------


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
    # Une expression et pas un nom : le parser accepte `f(1)(2)`, et c'est l'analyse
    # sémantique qui le refuse (spécification 1.0 : seule une fonction nommée est appelable).
    fonction: Expr
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


# --- Instructions --------------------------------------------------------------


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
    sinon: Bloc | None  # le sinon final, s'il existe
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


# --- Affichage de l'arbre --------------------------------------------------------


def _est_noeud(valeur: object) -> bool:
    return is_dataclass(valeur) and not isinstance(valeur, type)


def afficher_arbre(noeud: object) -> str:
    """L'arbre sous forme de texte, avec une ligne par nœud (sans les positions)."""
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
