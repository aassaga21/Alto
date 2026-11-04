"""La ligne de commande : python -m alto run|transpile|check|repl."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from alto.compilateur import compiler, executer, transpiler
from alto.erreurs import ErreurAlto, ErreurExecution, formater

OK, ERREUR_COMPILATION, ERREUR_EXECUTION = 0, 1, 3


def _construire_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="alto", description="Le langage Alto.")
    commandes = parser.add_subparsers(dest="commande", required=True)

    run = commandes.add_parser("run", help="exécute un programme")
    run.add_argument("fichier", type=Path)

    transpile = commandes.add_parser("transpile", help="affiche le Python généré")
    transpile.add_argument("fichier", type=Path)
    transpile.add_argument("-o", "--sortie", type=Path, help="écrit le Python dans ce fichier")

    check = commandes.add_parser("check", help="vérifie sans exécuter")
    check.add_argument("fichier", type=Path)

    commandes.add_parser("repl", help="session interactive")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _construire_parser().parse_args(argv)

    if args.commande == "repl":
        # À remplacer par `from alto.repl import lancer; lancer(); return OK`
        # quand le générateur (étape 8) sera sur main.
        print("alto : le REPL n'est pas encore disponible (étape 8)", file=sys.stderr)
        return ERREUR_COMPILATION

    fichier: Path = args.fichier
    try:
        source = fichier.read_text(encoding="utf-8")
    except OSError:
        print(f"alto : fichier introuvable : {fichier}", file=sys.stderr)
        return ERREUR_COMPILATION

    try:
        if args.commande == "run":
            executer(source)
        elif args.commande == "check":
            compiler(source)
        elif args.commande == "transpile":
            code = transpiler(source).code
            if args.sortie is None:
                print(code, end="")
            else:
                args.sortie.write_text(code, encoding="utf-8")
    # l'ordre compte : ErreurExecution est une sous-classe d'ErreurAlto
    except ErreurExecution as erreur:
        print(formater(erreur, source, str(fichier)), file=sys.stderr)
        return ERREUR_EXECUTION
    except ErreurAlto as erreur:
        print(formater(erreur, source, str(fichier)), file=sys.stderr)
        return ERREUR_COMPILATION
    return OK
