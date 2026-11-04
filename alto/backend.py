"""Le contrat commun à tous les backends.

Ce module ne doit importer ni le générateur ni le formateur : ce sont eux qui l'importent
(sinon, import circulaire).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from alto.noeuds import Programme
from alto.semantique import Analyse


@dataclass(frozen=True, slots=True)
class Sortie:
    """Ce que produit un backend."""

    code: str
    #: ligne du code produit -> ligne du source Alto (pour les erreurs d'exécution)
    correspondance: dict[int, int] = field(default_factory=dict)


class Backend(Protocol):
    """Une « prise » du compilateur : toute classe qui a ces attributs et cette méthode
    est un backend, sans avoir besoin d'hériter de quoi que ce soit."""

    nom: str
    extension: str
    executable: bool  # le code produit est-il du Python exécutable ?

    def generer(self, programme: Programme, analyse: Analyse) -> Sortie: ...
