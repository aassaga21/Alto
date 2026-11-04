"""La ligne de commande : python -m alto run|transpile|check|repl."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from alto.backends import BACKENDS
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

    for commande in (run, transpile):
        commande.add_argument("--backend", choices=sorted(BACKENDS), default="python")

    check = commandes.add_parser("check", help="vérifie sans exécuter")
    check.add_argument("fichier", type=Path)

    fmt = commandes.add_parser(
        "fmt", help="réécrit le programme proprement (perd les commentaires)"
    )
    fmt.add_argument("fichier", type=Path)
    fmt.add_argument("--ecrire", action="store_true", help="réécrit le fichier en place")

    commandes.add_parser("repl", help="session interactive")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _construire_parser().parse_args(argv)

    if args.commande == "repl":
        from alto.repl import lancer

        lancer()
        return OK

    fichier: Path = args.fichier
    try:
        source = fichier.read_text(encoding="utf-8")
    except OSError:
        print(f"alto : fichier introuvable : {fichier}", file=sys.stderr)
        return ERREUR_COMPILATION

    try:
        if args.commande == "run":
            executer(source, backend=args.backend)
        elif args.commande == "check":
            compiler(source)
        elif args.commande == "transpile":
            code = transpiler(source, backend=args.backend).code
            if args.sortie is None:
                print(code, end="")
            else:
                args.sortie.write_text(code, encoding="utf-8")
        elif args.commande == "fmt":
            code = transpiler(source, backend="formateur").code
            if args.ecrire:
                fichier.write_text(code, encoding="utf-8")
            else:
                print(code, end="")
    # l'ordre compte : ErreurExecution est une sous-classe d'ErreurAlto
    except ErreurExecution as erreur:
        print(formater(erreur, source, str(fichier)), file=sys.stderr)
        return ERREUR_EXECUTION
    except ErreurAlto as erreur:
        print(formater(erreur, source, str(fichier)), file=sys.stderr)
        return ERREUR_COMPILATION
    return OK
