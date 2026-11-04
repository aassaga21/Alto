"""Les types d'Alto (extension 12) : typage statique graduel."""

from __future__ import annotations

from enum import Enum


class Type(Enum):
    ENTIER = "entier"
    DECIMAL = "decimal"
    TEXTE = "texte"
    BOOLEEN = "booleen"
    LISTE = "liste"
    RIEN = "rien"
    #: le type d'une valeur sans annotation : compatible avec tout (typage graduel)
    INCONNU = "?"

    def __str__(self) -> str:
        return self.value


#: Les types qu'on peut écrire dans une annotation, indexés par leur nom : {"entier": ...}
TYPES: dict[str, Type] = {t.value: t for t in Type if t is not Type.INCONNU}

NUMERIQUES = frozenset({Type.ENTIER, Type.DECIMAL})
ADDITIONNABLES = NUMERIQUES | {Type.TEXTE, Type.LISTE}

#: Pour `< <= > >=` : deux valeurs de la même famille se comparent. Un booléen se compare à
#: un nombre (`a < b < c` se lit `(a < b) < c`, spécification 1.0) ; `rien` ne se compare pas.
FAMILLES: dict[Type, str] = {
    Type.ENTIER: "nombre",
    Type.DECIMAL: "nombre",
    Type.BOOLEEN: "nombre",
    Type.TEXTE: "texte",
    Type.LISTE: "liste",
}


def compatible(attendu: Type, recu: Type) -> bool:
    """Une valeur de type `recu` peut-elle aller là où on attend `attendu` ?"""
    if Type.INCONNU in (attendu, recu):
        return True  # on ne signale que ce qu'on SAIT être faux
    if attendu is recu:
        return True
    return attendu is Type.DECIMAL and recu is Type.ENTIER  # un entier est un décimal


def _connus_parmi(permis: frozenset[Type], *types: Type) -> bool:
    """Vrai si chaque type connu est dans `permis` (les inconnus passent)."""
    return all(t is Type.INCONNU or t in permis for t in types)


def _arithmetique(gauche: Type, droite: Type) -> Type:
    """entier op entier -> entier ; s'il y a un décimal -> décimal ; sinon on ne sait pas."""
    if Type.INCONNU in (gauche, droite):
        return Type.INCONNU
    return Type.ENTIER if gauche is droite is Type.ENTIER else Type.DECIMAL


def type_unaire(op: str, operande: Type) -> Type | None:
    """Le type de `op operande`, ou None si l'opération est impossible."""
    if op == "non":
        return Type.BOOLEEN  # `non` s'applique à tout (spécification 1.0) et rend un booléen
    # le `-` unaire
    return operande if _connus_parmi(NUMERIQUES, operande) else None


def type_binaire(op: str, gauche: Type, droite: Type) -> Type | None:
    """Le type de `gauche op droite`, ou None si l'opération est impossible."""
    connus = [t for t in (gauche, droite) if t is not Type.INCONNU]
    if op in ("==", "!="):
        return Type.BOOLEEN  # on peut comparer n'importe quoi
    if op in ("et", "ou"):
        # jamais d'erreur (spécification 1.0) ; `1 ou 2` vaut 1, donc pas toujours un booléen
        return Type.BOOLEEN if gauche is droite is Type.BOOLEEN else Type.INCONNU
    if op in ("<", "<=", ">", ">="):
        familles = {FAMILLES.get(t) for t in connus}
        if None in familles or len(familles) > 1:
            return None  # `rien < 1`, `"a" < 1`, `[1] < 2`
        return Type.BOOLEEN
    if op == "+":
        # deux nombres, deux textes ou deux listes
        if not _connus_parmi(ADDITIONNABLES, *connus):
            return None
        if len(connus) == 2:
            if connus[0] in NUMERIQUES and connus[1] in NUMERIQUES:
                return _arithmetique(gauche, droite)
            return connus[0] if connus[0] is connus[1] else None
        return Type.INCONNU
    if op == "/":
        return Type.DECIMAL if _connus_parmi(NUMERIQUES, *connus) else None
    # - * %
    return _arithmetique(gauche, droite) if _connus_parmi(NUMERIQUES, *connus) else None
