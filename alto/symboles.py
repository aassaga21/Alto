"""La table des symboles : une pile de portées."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum, auto

from alto.erreurs import Position


class Genre(Enum):
    VARIABLE = auto()
    FONCTION = auto()
    PREDEFINIE = auto()


@dataclass(frozen=True, slots=True)
class Symbole:
    nom: str
    genre: Genre
    pos: Position
    nb_parametres: int = 0  # pour les fonctions


@dataclass
class Portee:
    nom: str
    est_fonction: bool = False
    symboles: dict[str, Symbole] = field(default_factory=dict)


class TableSymboles:
    def __init__(self) -> None:
        self._portees: list[Portee] = []

    @contextmanager
    def portee(self, nom: str = "bloc", *, fonction: bool = False) -> Iterator[Portee]:
        """Ouvre une portée le temps d'un `with`, et la referme même en cas d'exception."""
        portee = Portee(nom, est_fonction=fonction)
        self._portees.append(portee)
        try:
            yield portee
        finally:
            self._portees.pop()

    @property
    def profondeur(self) -> int:
        return len(self._portees)

    def declarer(self, symbole: Symbole) -> None:
        """Ajoute le symbole à la portée du haut."""
        self._portees[-1].symboles[symbole.nom] = symbole

    def chercher(self, nom: str) -> Symbole | None:
        """Cherche le nom de la portée du haut vers celle du bas."""
        for portee in reversed(self._portees):
            if nom in portee.symboles:
                return portee.symboles[nom]
        return None

    def est_globale(self, nom: str) -> bool:
        """Vrai si `nom` désigne un symbole de la portée globale (la plus basse)."""
        for portee in reversed(self._portees[1:]):
            if nom in portee.symboles:
                return False
        return bool(self._portees) and nom in self._portees[0].symboles
