"""La façade : le seul module qu'utilisent la CLI et le REPL."""

from __future__ import annotations

import traceback
from dataclasses import dataclass

from alto.backend import Sortie
from alto.backends import BACKENDS
from alto.erreurs import ErreurAlto, ErreurExecution, Position
from alto.noeuds import Programme
from alto.parser import parse
from alto.semantique import Analyse, analyser

NOM_FICHIER = "<alto>"

MESSAGES: dict[type[Exception], str] = {
    ZeroDivisionError: "division par zéro",
    IndexError: "indice hors limites",
    TypeError: "opération impossible sur ces valeurs",
    RecursionError: "trop d'appels récursifs",
}


@dataclass(frozen=True, slots=True)
class Compilation:
    programme: Programme
    analyse: Analyse


def compiler(source: str) -> Compilation:
    """Analyse syntaxique puis sémantique. Lève `ErreursMultiples`."""
    programme = parse(source)
    return Compilation(programme, analyser(programme))


def transpiler(source: str, backend: str = "python") -> Sortie:
    """Genere avec le backend choisi, apres verification du programme."""
    compilation = compiler(source)
    try:
        generateur = BACKENDS[backend]
    except KeyError:
        raise ErreurAlto(f"backend inconnu : {backend}") from None
    return generateur.generer(compilation.programme, compilation.analyse)


def executer(source: str, backend: str = "python") -> None:
    """Compile et execute le source avec le backend choisi."""
    sortie = transpiler(source, backend)
    if not BACKENDS[backend].executable:
        raise ErreurAlto(f"le backend {backend} ne produit pas du code executable")
    executer_sortie(sortie)


def executer_sortie(sortie: Sortie) -> None:
    """Exécute du code déjà généré ; une exception devient une `ErreurExecution`."""
    code = compile(sortie.code, NOM_FICHIER, "exec")
    try:
        exec(code, {"__name__": "__main__"})  # noqa: S102 (exécuter le code généré est le but)
    except Exception as exc:
        raise _traduire(exc, sortie.correspondance) from exc


def _traduire(exc: Exception, correspondance: dict[int, int]) -> ErreurExecution:
    message = next((m for genre, m in MESSAGES.items() if isinstance(exc, genre)), str(exc))
    # de la frame la plus profonde à la moins profonde : la première qui vient du code généré
    for frame in reversed(traceback.extract_tb(exc.__traceback__)):
        if frame.filename == NOM_FICHIER and frame.lineno in correspondance:
            # colonne 0 = inconnue : `formater` n'affichera pas de ^
            return ErreurExecution(message, Position(correspondance[frame.lineno], 0))
    return ErreurExecution(message)
