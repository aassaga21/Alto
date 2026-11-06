"""Le serveur MCP d'Alto : un assistant peut exécuter, vérifier, transpiler et formater du code Alto.

Comme la CLI et le REPL, il ne passe que par la façade `alto.compilateur`. La bibliothèque `mcp`
n'est importée que par `creer_serveur` : le reste d'Alto fonctionne sans elle.
"""

from __future__ import annotations

import io
import sys
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
from types import FrameType
from typing import TYPE_CHECKING, Any, Literal, TypedDict

from alto.compilateur import NOM_FICHIER, compiler, executer_sortie, transpiler
from alto.erreurs import ErreurAlto, ErreursMultiples, formater

if TYPE_CHECKING:
    from _typeshed import TraceFunction
    from mcp.server.mcpserver import MCPServer

RACINE = Path(__file__).resolve().parent.parent
SPECIFICATION = RACINE / "specification.md"
EXEMPLES = RACINE / "exemples"
FICHIER_SOURCE = "<mcp>"  # le nom de fichier affiché dans les messages d'erreur

#: Au-delà de ce nombre de lignes exécutées, on arrête le programme (boucle infinie ?).
ETAPES_MAX = 1_000_000

INSTRUCTIONS = (
    "Alto est un petit langage aux mots-clés français (var, si, sinon, tantque, pour … de … "
    "jusqua, fonction, rends, ecris), transpilé en Python. Chaque instruction simple finit par "
    "« ; », les blocs sont entre accolades, et les bornes d'une boucle pour sont incluses. "
    "Lis la ressource alto://specification avant d'écrire du code, puis utilise verifier_alto "
    "et executer_alto pour le tester."
)


# --- Les résultats renvoyés aux clients (sortie structurée MCP) --------------------------


class ErreurJson(TypedDict):
    genre: str  # "erreur lexicale", "erreur de syntaxe", "erreur sémantique"…
    message: str
    ligne: int | None
    colonne: int | None  # None si elle est inconnue (erreurs d'exécution)
    texte: str  # le message complet, tel que l'affiche la ligne de commande


class ResultatExecution(TypedDict):
    ok: bool
    sortie: str  # ce que le programme a affiché (même s'il s'est arrêté sur une erreur)
    erreurs: list[ErreurJson]


class ResultatVerification(TypedDict):
    ok: bool
    erreurs: list[ErreurJson]


class ResultatCode(TypedDict):
    ok: bool
    code: str  # vide s'il y a des erreurs
    erreurs: list[ErreurJson]


# --- Les outils, utilisables aussi sans MCP ----------------------------------------------


def _erreurs_json(erreur: ErreurAlto, source: str) -> list[ErreurJson]:
    """Une erreur (ou un groupe d'erreurs) sous une forme simple à lire pour un programme."""
    if isinstance(erreur, ErreursMultiples):
        return [e for sous_erreur in erreur.erreurs for e in _erreurs_json(sous_erreur, source)]
    pos = erreur.position
    return [
        {
            "genre": erreur.genre,
            "message": erreur.message,
            "ligne": pos.ligne if pos and pos.ligne else None,
            "colonne": pos.colonne if pos and pos.colonne else None,
            "texte": formater(erreur, source, FICHIER_SOURCE),
        }
    ]


class LimiteDEtapes(Exception):
    """Le programme a exécuté trop de lignes : sans doute une boucle infinie."""


@contextmanager
def limite_d_etapes(maximum: int) -> Iterator[None]:
    """Compte les lignes exécutées dans le code généré, et l'arrête au-delà de `maximum`."""
    compte = 0

    def locale(frame: FrameType, evenement: str, arg: Any) -> TraceFunction | None:
        nonlocal compte
        if evenement == "line":
            compte += 1
            if compte > maximum:
                raise LimiteDEtapes(f"le programme a dépassé {maximum} étapes (boucle infinie ?)")
        return locale

    def globale(frame: FrameType, evenement: str, arg: Any) -> TraceFunction | None:
        # on ne suit que le code généré, pas le reste de Python
        return locale if frame.f_code.co_filename == NOM_FICHIER else None

    precedente = sys.gettrace()
    sys.settrace(globale)
    try:
        yield
    finally:
        sys.settrace(precedente)


def executer_alto(source: str, backend: Literal["python", "ast"] = "python") -> ResultatExecution:
    """Exécute un programme Alto et renvoie ce qu'il affiche."""
    return executer_avec_limite(source, backend, ETAPES_MAX)


def executer_avec_limite(source: str, backend: str, etapes_max: int) -> ResultatExecution:
    """`executer_alto`, avec une limite choisie (la limite n'est pas un argument de l'outil MCP :
    un client ne doit pas pouvoir la lever)."""
    capture = io.StringIO()
    try:
        sortie = transpiler(source, backend)
        # ce que le programme affiche ne doit pas aller sur la sortie standard,
        # que le transport stdio de MCP utilise pour ses propres messages
        with redirect_stdout(capture), limite_d_etapes(etapes_max):
            executer_sortie(sortie)
    except ErreurAlto as erreur:
        return {"ok": False, "sortie": capture.getvalue(), "erreurs": _erreurs_json(erreur, source)}
    return {"ok": True, "sortie": capture.getvalue(), "erreurs": []}


def verifier_alto(source: str) -> ResultatVerification:
    """Vérifie un programme Alto sans l'exécuter (lexique, syntaxe, sémantique, types)."""
    try:
        compiler(source)
    except ErreurAlto as erreur:
        return {"ok": False, "erreurs": _erreurs_json(erreur, source)}
    return {"ok": True, "erreurs": []}


def _code(source: str, backend: str) -> ResultatCode:
    try:
        code = transpiler(source, backend).code
    except ErreurAlto as erreur:
        return {"ok": False, "code": "", "erreurs": _erreurs_json(erreur, source)}
    return {"ok": True, "code": code, "erreurs": []}


def transpiler_alto(source: str, backend: Literal["python", "ast"] = "python") -> ResultatCode:
    """Le code Python produit pour un programme Alto."""
    return _code(source, backend)


def formater_alto(source: str) -> ResultatCode:
    """Le programme Alto réécrit proprement (attention : les commentaires sont perdus)."""
    return _code(source, "formateur")


def lire_specification() -> str:
    return SPECIFICATION.read_text(encoding="utf-8")


def noms_des_exemples() -> list[str]:
    return sorted(chemin.stem for chemin in EXEMPLES.glob("*.alt"))


def lire_exemple(nom: str) -> str:
    if nom not in noms_des_exemples():
        raise ValueError(f"exemple inconnu : {nom!r} (voir alto://exemples)")
    return (EXEMPLES / f"{nom}.alt").read_text(encoding="utf-8")


# --- Le serveur MCP -----------------------------------------------------------------------


def creer_serveur() -> MCPServer:
    """Construit le serveur MCP (demande la bibliothèque `mcp`)."""
    from mcp.server.mcpserver import MCPServer

    serveur = MCPServer("alto", instructions=INSTRUCTIONS, version="1.1")

    serveur.tool(description="Exécute un programme Alto et renvoie ce qu'il affiche.")(
        executer_alto
    )
    serveur.tool(description="Vérifie un programme Alto sans l'exécuter.")(verifier_alto)
    serveur.tool(description="Traduit un programme Alto en Python.")(transpiler_alto)
    serveur.tool(description="Réécrit proprement un programme Alto.")(formater_alto)

    @serveur.resource(
        "alto://specification",
        name="specification",
        description="La spécification complète du langage Alto.",
        mime_type="text/markdown",
    )
    def specification() -> str:
        return lire_specification()

    @serveur.resource(
        "alto://exemples",
        name="exemples",
        description="Les noms des programmes d'exemple, un par ligne.",
    )
    def exemples() -> str:
        return "\n".join(noms_des_exemples())

    @serveur.resource(
        "alto://exemples/{nom}",
        name="exemple",
        description="Le code d'un programme d'exemple (par exemple alto://exemples/03_fizzbuzz).",
    )
    def exemple(nom: str) -> str:
        return lire_exemple(nom)

    @serveur.prompt(description="Écrire un programme Alto sur un sujet, puis le tester.")
    def ecrire_programme(sujet: str) -> str:
        return (
            f"Écris un programme Alto qui {sujet}. Lis d'abord la ressource "
            "alto://specification. Vérifie ton programme avec verifier_alto, corrige les "
            "erreurs signalées, puis exécute-le avec executer_alto et montre ce qu'il affiche."
        )

    return serveur


def lancer() -> None:
    """Lance le serveur sur l'entrée et la sortie standard (transport stdio)."""
    creer_serveur().run("stdio")
