"""Un flux avec regard en avant, générique."""

from collections import deque
from collections.abc import Iterable, Iterator


class Flux[T]:
    def __init__(self, source: Iterable[T]) -> None:
        self._source: Iterator[T] = iter(source)
        self._tampon: deque[T] = deque()
        self.consommes = 0  # nombre d'éléments consommés (servira à l'étape 6)

    def regarde(self, decalage: int = 0) -> T | None:
        """L'élément situé `decalage` crans plus loin, sans le consommer."""
        while len(self._tampon) <= decalage:
            try:
                self._tampon.append(next(self._source))
            except StopIteration:
                return None
        return self._tampon[decalage]

    def avance(self) -> T:
        """Consomme et renvoie l'élément courant."""
        if self.regarde() is None:
            raise IndexError("le flux est vide")
        self.consommes += 1
        return self._tampon.popleft()
