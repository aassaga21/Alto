"""Positions dans le source et hiérarchie des erreurs d'Alto."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Position:
    ligne: int
    colonne: int

    def __str__(self) -> str:
        return f"ligne {self.ligne}, colonne {self.colonne}"

    def decalee(self, n: int) -> Position:
        """La même position, n colonnes plus loin (servira à l'étape 6)."""
        return Position(self.ligne, self.colonne + n)


#: Position par défaut des nœuds construits à la main dans les tests (étape 4).
SANS_POSITION = Position(0, 0)


class ErreurAlto(Exception):
    """La racine de toutes nos erreurs."""

    genre = "erreur"

    def __init__(self, message: str, position: Position | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.position = position

    def __str__(self) -> str:
        if self.position is None:
            return f"{self.genre} : {self.message}"
        return f"{self.position} : {self.genre} : {self.message}"


class ErreurLexicale(ErreurAlto):
    genre = "erreur lexicale"


class ErreurSyntaxe(ErreurAlto):
    genre = "erreur de syntaxe"


class ErreurSemantique(ErreurAlto):
    genre = "erreur sémantique"


class ErreurType(ErreurSemantique):
    """Une valeur dont le type ne convient pas (extension 12)."""

    genre = "erreur de type"


class ErreurExecution(ErreurAlto):
    genre = "erreur d'exécution"


class ErreursMultiples(ErreurAlto):
    """Regroupe plusieurs erreurs (parser et analyse sémantique)."""

    def __init__(self, erreurs: list[ErreurAlto]) -> None:
        super().__init__(f"{len(erreurs)} erreur(s)")
        self.erreurs = erreurs


def formater(erreur: ErreurAlto, source: str, fichier: str = "<source>") -> str:
    """Le message complet : `fichier:ligne:colonne : genre : message`, la ligne, puis un `^`."""
    if isinstance(erreur, ErreursMultiples):
        return "\n".join(formater(e, source, fichier) for e in erreur.erreurs)
    if erreur.position is None:
        return f"{fichier} : {erreur.genre} : {erreur.message}"
    pos = erreur.position
    lignes = source.splitlines()
    texte = lignes[pos.ligne - 1] if 0 < pos.ligne <= len(lignes) else ""
    if pos.colonne == 0:  # colonne inconnue (erreur d'exécution, étape 9) : pas de ^
        return f"{fichier}:{pos.ligne} : {erreur.genre} : {erreur.message}\n    {texte}"
    return (
        f"{fichier}:{pos.ligne}:{pos.colonne} : {erreur.genre} : {erreur.message}\n"
        f"    {texte}\n"
        f"    {' ' * (pos.colonne - 1)}^"
    )
