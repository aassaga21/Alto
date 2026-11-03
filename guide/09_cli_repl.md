# Étape 9 : la ligne de commande et le REPL

**Qui :** Alexandra. **Fichiers :** `alto/compilateur.py` (suite), `alto/emetteur.py` (ajout), `alto/generateur.py` (petit ajout), `alto/cli.py`, `alto/__main__.py`, `alto/repl.py`, `tests/test_etape_09_cli_repl.py`. **Énoncé :** `langage/etapes/09_cli_repl.md`.

> **En une phrase :** rendre Alto utilisable par un humain : `python -m alto run programme.alt`, des erreurs d'exécution qui montrent **la ligne Alto**, et une session interactive.

**Tu as besoin de :** la chaîne complète de l'étape 8 (Arthur). Tu peux commencer `cli.py` avant, en faisant semblant que `executer` existe.

## 1. Comprendre

À la fin de cette étape :

```bash
$ uv run python -m alto run exemples/02_factorielle.alt
0 1 1
1 1 1
...
$ uv run python -m alto check faux.alt
faux.alt:3:23 : erreur de syntaxe : ';' attendu en fin d'affectation, trouvé '}'
        total = totale + i
                          ^
$ uv run python -m alto repl
Alto — Ctrl-D pour quitter.
alto> var x = 20;
alto> x * 2 + 2
42
alto> si x > 1 {
....> ecris "oui";
....> }
oui
```

Les **codes de retour** (ce que vaut `$?` après la commande) : `0` succès, `1` erreur de compilation (ou fichier introuvable), `3` erreur d'exécution. Le `2` est réservé par `argparse` aux mauvaises options.

## 2. Le Python à connaître

### `argparse` avec des sous-commandes

```python
parser = argparse.ArgumentParser(prog="alto")
commandes = parser.add_subparsers(dest="commande", required=True)
run = commandes.add_parser("run", help="exécute un programme")
run.add_argument("fichier", type=Path)

args = parser.parse_args(["run", "p.alt"])
args.commande   # "run"
args.fichier    # Path("p.alt")
```

`parse_args` accepte une **liste** : on peut tester `main(["run", "p.alt"])` sans lancer de vrai terminal.

### Un générateur qui **reçoit** des valeurs : `send`

```python
def echo() -> Generator[str, str, None]:
    reponse = ""
    while True:
        ligne = yield reponse        # rend `reponse`, puis attend qu'on lui envoie une ligne
        reponse = ligne.upper()

g = echo()
next(g)            # démarre : rend ""
g.send("abc")      # "ABC"
g.send("de")       # "DE"   — le générateur garde son état entre deux appels
```

C'est exactement ce qu'il faut à un REPL.

### `redirect_stdout` : capturer ce que `print` affiche

```python
tampon = io.StringIO()
with redirect_stdout(tampon):
    print("bonjour")
tampon.getvalue()    # "bonjour\n"
```

## 3. Pas à pas

### 3.1 Ramener une erreur d'exécution à la ligne Alto

```
fonction moyenne(l) {
    rends (l[0] + l[1]) / taille(l);      ← ligne 2 : IndexError si l est vide
}
ecris moyenne([]);
```

L'utilisateur ne doit voir ni traceback Python, ni numéro de ligne du code **généré**, mais :

```
p.alt:2 : erreur d'exécution : indice hors limites
        rends (l[0] + l[1]) / taille(l);
```

**Le principe :**

1. pendant la génération, l'émetteur note pour **chaque ligne Python** la ligne Alto d'où elle vient (un `dict[int, int]`) ;
2. on compile le code avec le nom de fichier `"<alto>"` ;
3. quand une exception arrive, on parcourt le traceback **de la frame la plus profonde à la moins profonde**, on prend la première qui vient de `"<alto>"`, et on traduit son numéro de ligne ;
4. on lève une `ErreurExecution` à cette ligne, chaînée à l'exception d'origine (`from exc`).

**Étape a — l'émetteur note les correspondances.** Ajoute dans `Emetteur` :

```python
    def __init__(self, indentation: str = "    ") -> None:
        self._lignes: list[str] = []
        self._indentation = indentation
        self.niveau = 0
        self._ligne_source = 0
        #: numéro de ligne produite (à partir de 1) -> ligne du source Alto
        self.correspondance: dict[int, int] = {}

    def ligne(self, texte: str = "") -> None:
        self._lignes.append(self._indentation * self.niveau + texte)
        if self._ligne_source:
            self.correspondance[len(self._lignes)] = self._ligne_source

    @contextmanager
    def depuis(self, ligne_source: int) -> Iterator[None]:
        """Les lignes émises dans ce `with` viennent de `ligne_source`."""
        precedente = self._ligne_source
        self._ligne_source = ligne_source
        try:
            yield
        finally:
            self._ligne_source = precedente
```

**Étape b — le générateur s'en sert** (demande à Arthur, ou fais une petite PR sur `generateur.py`) : renomme sa méthode `instruction` en `_instruction`, et ajoute :

```python
    def instruction(self, instr: Instr) -> None:
        with self.e.depuis(instr.pos.ligne):
            self._instruction(instr)
```

**Étape c — la façade.** `alto/compilateur.py` devient :

```python
"""La façade : le seul module qu'utilisent la CLI et le REPL."""

from __future__ import annotations

import traceback
from dataclasses import dataclass

from alto.erreurs import ErreurExecution, Position
from alto.generateur import PRELUDE, GenerateurPython
from alto.noeuds import Programme
from alto.parser import parse
from alto.semantique import Analyse, analyser

NOM_FICHIER = "<alto>"

MESSAGES = {
    ZeroDivisionError: "division par zéro",
    IndexError: "indice hors limites",
    TypeError: "opération impossible sur ces valeurs",
    RecursionError: "trop d'appels récursifs",
}


@dataclass(frozen=True, slots=True)
class Compilation:
    programme: Programme
    analyse: Analyse


@dataclass(frozen=True, slots=True)
class Sortie:
    code: str
    correspondance: dict[int, int]


def compiler(source: str) -> Compilation:
    """Analyse syntaxique puis sémantique. Lève `ErreursMultiples`."""
    programme = parse(source)
    return Compilation(programme, analyser(programme))


def transpiler(source: str) -> Sortie:
    """Le code Python, et la correspondance de ses lignes avec le source."""
    compilation = compiler(source)
    generateur = GenerateurPython(compilation.analyse)
    corps = generateur.programme(compilation.programme)
    decalage = PRELUDE.count("\n")  # les lignes du prélude passent avant
    correspondance = {
        ligne + decalage: ligne_source
        for ligne, ligne_source in generateur.e.correspondance.items()
    }
    return Sortie(PRELUDE + corps, correspondance)


def executer(source: str) -> None:
    """Compile et exécute `source` ; l'affichage va sur `sys.stdout`."""
    sortie = transpiler(source)
    code = compile(sortie.code, NOM_FICHIER, "exec")
    try:
        exec(code, {"__name__": "__main__"})
    except Exception as exc:
        raise _traduire(exc, sortie.correspondance) from exc


def _traduire(exc: Exception, correspondance: dict[int, int]) -> ErreurExecution:
    message = next((m for genre, m in MESSAGES.items() if isinstance(exc, genre)), str(exc))
    for frame in reversed(traceback.extract_tb(exc.__traceback__)):
        if frame.filename == NOM_FICHIER and frame.lineno in correspondance:
            # colonne 0 = inconnue : `formater` n'affichera pas de ^
            return ErreurExecution(message, Position(correspondance[frame.lineno], 0))
    return ErreurExecution(message)
```

> ⚠️ `transpiler` renvoie maintenant une `Sortie` et plus un `str` : dans les tests de l'étape 8, remplace `transpiler(...)` par `transpiler(...).code`.

**Plus rien d'autre ne doit appeler directement le lexer, le parser ou le générateur** : la CLI, le REPL (et plus tard le serveur MCP) passent par ces trois fonctions.

### 3.2 La ligne de commande (`alto/cli.py`)

```python
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
    transpile.add_argument("-o", "--sortie", type=Path)

    check = commandes.add_parser("check", help="vérifie sans exécuter")
    check.add_argument("fichier", type=Path)

    commandes.add_parser("repl", help="session interactive")
    return parser
```

À toi : `main(argv: Sequence[str] | None = None) -> int`. Elle :

1. lit les arguments ;
2. si la commande est `repl`, lance le REPL et rend `OK` ;
3. lit le fichier (`fichier.read_text(encoding="utf-8")`) ; s'il n'existe pas (`OSError`), affiche `alto : fichier introuvable : …` **sur `sys.stderr`** et rend `ERREUR_COMPILATION` ;
4. selon la commande : `executer`, `compiler` ou `transpiler` (afficher le code, ou l'écrire dans `args.sortie`) ;
5. attrape `ErreurExecution` → message formaté sur `stderr`, rend `ERREUR_EXECUTION` ; puis `ErreurAlto` → rend `ERREUR_COMPILATION`. (**L'ordre compte** : `ErreurExecution` est une sous-classe d'`ErreurAlto`.)

<details>
<summary>▶ Solution</summary>

```python
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
            executer(source)
        elif args.commande == "check":
            compiler(source)
        elif args.commande == "transpile":
            code = transpiler(source).code
            if args.sortie is None:
                print(code, end="")
            else:
                args.sortie.write_text(code, encoding="utf-8")
    except ErreurExecution as erreur:
        print(formater(erreur, source, str(fichier)), file=sys.stderr)
        return ERREUR_EXECUTION
    except ErreurAlto as erreur:
        print(formater(erreur, source, str(fichier)), file=sys.stderr)
        return ERREUR_COMPILATION
    return OK
```

</details>

### 3.3 `python -m alto` (`alto/__main__.py`)

```python
import sys

from alto.cli import main

sys.exit(main())
```

```bash
uv run python -m alto run exemples/04_listes.alt
uv run python -m alto transpile exemples/04_listes.alt
```

### 3.4 Le REPL (`alto/repl.py`)

Deux difficultés :

- **Garder l'état.** Si on tape `var x = 20;` puis `x * 2`, l'analyse sémantique doit savoir que `x` existe. On garde donc le **source de toutes les saisies acceptées**, et on analyse `acceptees + nouvelle_saisie`. Mais on n'**exécute** que les nouvelles instructions, dans un dictionnaire (l'« espace de noms » Python) qui survit d'une saisie à l'autre.
- **Une saisie sur plusieurs lignes.** Tant qu'il reste des `{` non fermées, on accumule les lignes et on affiche l'invite `....> `. On compte les accolades **avec le lexer** (pas avec `str.count`, qui compterait les `{` à l'intérieur des textes).

Et une commodité : si la saisie ne se termine ni par `;` ni par `}` (par exemple `x * 2`), on l'enveloppe dans `ecris …;`.

<details>
<summary>▶ Solution</summary>

```python
"""Le REPL d'Alto : un générateur qui reçoit des lignes et rend des réponses."""

from __future__ import annotations

import io
from collections.abc import Generator
from contextlib import redirect_stdout
from dataclasses import dataclass

from alto.erreurs import ErreurAlto, ErreurLexicale, formater
from alto.generateur import PRELUDE, GenerateurPython
from alto.lexer import tokenize
from alto.noeuds import Programme
from alto.parser import parse
from alto.semantique import analyser
from alto.tokens import TokenKind as T

INVITE = "alto> "
SUITE = "....> "


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
    exec(PRELUDE, espace)
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

        nouvelles = Programme(programme.instructions[nb_instructions:])
        code = GenerateurPython(analyse).programme(nouvelles)
        tampon_sortie = io.StringIO()
        try:
            with redirect_stdout(tampon_sortie):
                exec(compile(code, "<alto>", "exec"), espace)
        except Exception as exc:
            sortie = tampon_sortie.getvalue() + f"erreur d'exécution : {exc}\n"
            continue
        sortie = tampon_sortie.getvalue()
        acceptees = source
        nb_instructions = len(programme.instructions)


def lancer() -> None:
    """Branche le générateur sur le clavier."""
    session = repl()
    reponse = next(session)
    print("Alto — Ctrl-D pour quitter.")
    while True:
        try:
            ligne = input(reponse.invite)
        except EOFError:
            print()
            return
        reponse = session.send(ligne)
        print(reponse.sortie, end="")
```

</details>

## 4. Les tests à écrire

```python
import inspect
import subprocess
import sys
from pathlib import Path

import pytest

from alto.cli import main
from alto.compilateur import executer
from alto.erreurs import ErreurExecution
from alto.repl import repl

RACINE = Path(__file__).parent.parent


def ecrire(tmp_path: Path, source: str) -> str:
    """Écrit un programme dans un dossier temporaire (fourni par pytest)."""
    fichier = tmp_path / "p.alt"
    fichier.write_text(source, encoding="utf-8")
    return str(fichier)


def test_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", ecrire(tmp_path, "ecris 1 + 1;")]) == 0
    assert capsys.readouterr().out == "2\n"


def test_erreur_de_compilation(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", ecrire(tmp_path, "ecris x;")]) == 1
    assert "p.alt:1:7" in capsys.readouterr().err


def test_erreur_d_execution_ramenee_a_la_ligne_alto(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source = "fonction f(l) {\n    rends l[5];\n}\necris f([1]);\n"
    assert main(["run", ecrire(tmp_path, source)]) == 3
    assert "p.alt:2 : erreur d'exécution : indice hors limites" in capsys.readouterr().err


def test_erreur_d_execution_chainee() -> None:
    with pytest.raises(ErreurExecution) as erreur:
        executer("ecris 1 / 0;")
    assert isinstance(erreur.value.__cause__, ZeroDivisionError)


def test_fichier_introuvable(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["run", "nexiste_pas.alt"]) == 1
    assert "introuvable" in capsys.readouterr().err


def test_python_m_alto() -> None:
    resultat = subprocess.run(
        [sys.executable, "-m", "alto", "run", "exemples/01_bonjour.alt"],
        cwd=RACINE, capture_output=True, text=True,
    )
    assert resultat.returncode == 0
    assert resultat.stdout.startswith("Bonjour, Alto !")


def test_le_repl_garde_l_etat_et_survit_aux_erreurs() -> None:
    session = repl()
    assert inspect.isgenerator(session)
    next(session)
    session.send("var x = 20;")
    assert "n'est pas déclaré" in session.send("ecris y;").sortie
    assert session.send("x * 2 + 2").sortie == "42\n"


def test_le_repl_attend_la_fin_du_bloc() -> None:
    session = repl()
    next(session)
    assert session.send("si vrai {").invite == "....> "
    assert session.send('ecris "oui";').sortie == ""
    assert session.send("}").sortie == "oui\n"
```

À ajouter : `transpile` à l'écran et avec `-o` (vérifie le fichier écrit), `check` d'un programme correct (code 0, rien sur `stderr`), une commande inconnue (`pytest.raises(SystemExit)`), une erreur d'exécution au fond d'un appel récursif.

## 5. Pièges fréquents

| Symptôme | Cause |
|---|---|
| l'erreur d'exécution pointe une ligne du prélude | le décalage `PRELUDE.count("\n")` est oublié |
| code 1 au lieu de 3 pour une erreur d'exécution | `except ErreurAlto` placé **avant** `except ErreurExecution` |
| le REPL ré-affiche les anciens `ecris` | il ré-exécute tout le programme au lieu des nouvelles instructions seulement |
| le REPL oublie `x` après une erreur | une saisie refusée a écrasé `acceptees` |

## 6. C'est fini quand…

- [ ] `uv run pytest -k etape_09` est vert ;
- [ ] `uv run python -m alto run`, `transpile`, `check` et `repl` marchent à la main ;
- [ ] les messages d'erreur ressemblent à ceux de la section 1.
