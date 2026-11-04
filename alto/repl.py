"""Le REPL d'Alto : un générateur qui reçoit des lignes et rend des réponses."""

from __future__ import annotations

import io
from collections.abc import Generator
from contextlib import redirect_stdout
from dataclasses import dataclass

from alto.compilateur import NOM_FICHIER, traduire
from alto.emetteur import Emetteur
from alto.erreurs import ErreurAlto, ErreurLexicale, formater
from alto.generateur import PRELUDE, GenerateurPython
from alto.lexer import tokenize
from alto.noeuds import Programme
from alto.parser import parse
from alto.semantique import Analyse, analyser
from alto.tokens import TokenKind as T

INVITE = "alto> "
SUITE = "....> "
BIENVENUE = "Alto — Ctrl-D (ou Ctrl-Z puis Entrée sous Windows) pour quitter."


@dataclass(frozen=True, slots=True)
class Reponse:
    sortie: str
    invite: str


def _accolades_ouvertes(source: str) -> int:
    """Le nombre de '{' pas encore fermées (compté avec le lexer, pas str.count)."""
    profondeur = 0
    try:
        for token in tokenize(source):
            if token.kind is T.ACC_G:
                profondeur += 1
            elif token.kind is T.ACC_D:
                profondeur -= 1
    except ErreurLexicale:
        return 0  # l'erreur sera signalée à l'analyse
    return profondeur


def repl() -> Generator[Reponse, str, None]:
    acceptees = ""  # le source de toutes les saisies acceptées
    nb_instructions = 0  # combien d'instructions ont déjà été exécutées
    espace: dict[str, object] = {"__name__": "__main__"}
    exec(PRELUDE, espace)  # noqa: S102 (les fonctions _ecris, _taille... de la session)
    # Un seul générateur pour toute la session : il renomme chaque variable (`x` devient
    # `_v_78_1`) et doit se souvenir de ces noms d'une saisie à l'autre.
    generateur = GenerateurPython(Analyse())
    tampon = ""
    sortie = ""

    while True:
        ligne = yield Reponse(sortie, SUITE if tampon else INVITE)
        sortie = ""
        tampon += ligne + "\n"
        if _accolades_ouvertes(tampon) > 0:
            continue  # bloc pas encore fermé : on attend la suite
        saisie, tampon = tampon.strip(), ""
        if not saisie:
            continue
        if not saisie.endswith((";", "}")):
            saisie = f"ecris {saisie};"  # une expression seule : on l'affiche

        source = acceptees + saisie + "\n"
        try:
            programme = parse(source)
            analyse = analyser(programme)
        except ErreurAlto as erreur:
            sortie = formater(erreur, source, "<repl>") + "\n"
            continue  # saisie refusée : `acceptees` ne change pas

        # on ne génère et n'exécute que les nouvelles instructions
        nouvelles = Programme(programme.instructions[nb_instructions:])
        generateur.analyse = analyse
        generateur.e = Emetteur()
        code = generateur.programme(nouvelles)
        capture = io.StringIO()
        try:
            with redirect_stdout(capture):
                exec(compile(code, NOM_FICHIER, "exec"), espace)  # noqa: S102
        except Exception as exc:  # noqa: BLE001 (le REPL doit survivre à toute erreur)
            sortie = capture.getvalue() + f"{traduire(exc, {})}\n"
            continue
        sortie = capture.getvalue()
        acceptees = source
        nb_instructions = len(programme.instructions)


def lancer() -> None:
    """Branche le générateur sur le clavier."""
    session = repl()
    reponse = next(session)
    print(BIENVENUE)
    while True:
        try:
            ligne = input(reponse.invite)
        except (EOFError, KeyboardInterrupt):
            print()
            return
        reponse = session.send(ligne)
        print(reponse.sortie, end="")
