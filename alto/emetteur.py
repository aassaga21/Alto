"""Émission de texte Python indenté."""

from collections.abc import Iterator
from contextlib import contextmanager


class Emetteur:
    def __init__(self, indentation: str = "    ") -> None:
        self._lignes: list[str] = []
        self._indentation = indentation
        self.niveau = 0
        self.source = 0
        self.correspondance: dict[int, int] = {}

    def ligne(self, texte: str = "") -> None:
        self._lignes.append(self._indentation * self.niveau + texte)
        if self.source > 0:
            self.correspondance[len(self._lignes)] = self.source

    @contextmanager
    def bloc(self, vide: str | None = "pass") -> Iterator[None]:
        avant = len(self._lignes)
        self.niveau += 1
        try:
            yield
            if len(self._lignes) == avant and vide is not None:
                self.ligne(vide)
        finally:
            self.niveau -= 1

    def texte(self) -> str:
        return "\n".join(self._lignes) + ("\n" if self._lignes else "")
