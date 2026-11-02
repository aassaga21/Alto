# Étape 10 : qualité et extension (`Backend`, formateur, mypy)

**Qui :** Fatoumata (backend et formateur) + Arthur (`mypy --strict` sur tout le paquet). **Fichiers :** `alto/backend.py`, `alto/formateur.py`, `alto/generateur.py`, `alto/compilateur.py`, `alto/cli.py`, `tests/test_etape_10_qualite.py`. **Énoncé :** `langage/etapes/10_qualite.md`.

> **En une phrase :** pouvoir ajouter une nouvelle « sortie » au compilateur (ici un **formateur** qui réécrit le code Alto proprement) **sans modifier** la CLI, et faire passer tout le projet au vérificateur de types `mypy --strict`.

## 1. Comprendre

Aujourd'hui, le compilateur n'a qu'une sortie : du Python. On veut pouvoir en brancher d'autres, comme des prises électriques : la CLI ne connaît que la **forme de la prise** (le `Protocol`), pas l'appareil branché dessus.

```
                     ┌──────────────────┐
compiler(source) ──▶ │ BACKENDS["python"]    │──▶ code Python  (exécutable)
                     │ BACKENDS["formateur"] │──▶ code Alto bien présenté (pas exécutable)
                     │ BACKENDS[...]         │──▶ demain : JSON, JavaScript…
                     └──────────────────┘
```

Le **formateur** prend un programme mal présenté :

```
var   x=(1+2)*3 ;si x>2{ecris x ,"grand";}sinon{ecris((x));}
```

et le réécrit :

```
var x = (1 + 2) * 3;
si x > 2 {
    ecris x, "grand";
} sinon {
    ecris x;
}
```

Les parenthèses inutiles autour de `x` disparaissent ; celles de `(1 + 2)` restent, car elles changent le sens.

## 2. Le Python à connaître

### `Protocol` : une interface sans héritage

```python
from typing import Protocol

class Volant(Protocol):
    def voler(self) -> str: ...

class Oiseau:                    # n'hérite de rien !
    def voler(self) -> str:
        return "flap flap"

def faire_voler(v: Volant) -> str:
    return v.voler()

faire_voler(Oiseau())            # mypy accepte : Oiseau a « la bonne forme »
```

### Le principe ouvert/fermé

Ajouter un backend = écrire **une classe** + ajouter **une entrée** dans `BACKENDS`. On ne touche ni à la CLI, ni au générateur existant.

### `mypy --strict`

mypy lit les annotations de types et trouve des bugs **sans exécuter le code** : un `None` oublié, un `case` manquant (grâce à `assert_never`), un appel avec un mauvais type. En mode strict, **tout** doit être annoté.

## 3. Pas à pas

### 3.1 Le contrat (`alto/backend.py`, Fatoumata)

```python
"""Le contrat commun à tous les backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from alto.noeuds import Programme
from alto.semantique import Analyse


@dataclass(frozen=True, slots=True)
class Sortie:
    code: str
    correspondance: dict[int, int] = field(default_factory=dict)


class Backend(Protocol):
    nom: str
    extension: str
    executable: bool  # le code produit est-il du Python exécutable ?

    def generer(self, programme: Programme, analyse: Analyse) -> Sortie: ...
```

`Sortie` **déménage** ici depuis `compilateur.py` (supprime-la de là-bas).

### 3.2 Le générateur Python devient un backend (`alto/generateur.py`)

Ajoute `from alto.backend import Sortie` en haut, et à la fin du fichier :

```python
class BackendPython:
    nom = "python"
    extension = ".py"
    executable = True

    def generer(self, programme: Programme, analyse: Analyse) -> Sortie:
        generateur = GenerateurPython(analyse)
        corps = generateur.programme(programme)
        decalage = PRELUDE.count("\n")  # les lignes du prélude passent avant
        correspondance = {
            ligne + decalage: ligne_source
            for ligne, ligne_source in generateur.e.correspondance.items()
        }
        return Sortie(PRELUDE + corps, correspondance)
```

C'est le code qui était dans `transpiler` à l'étape 9, simplement déplacé.

### 3.3 La façade choisit le backend (`alto/compilateur.py`)

```python
from alto.backend import Backend, Sortie
from alto.erreurs import ErreurAlto, ErreurExecution, Position
from alto.formateur import Formateur
from alto.generateur import BackendPython

BACKENDS: dict[str, Backend] = {b.nom: b for b in (BackendPython(), Formateur())}


def choisir_backend(nom: str) -> Backend:
    if nom not in BACKENDS:
        raise ErreurAlto(f"backend inconnu : {nom!r} (choix possibles : {', '.join(BACKENDS)})")
    return BACKENDS[nom]


def transpiler(source: str, backend: str = "python") -> Sortie:
    choisi = choisir_backend(backend)
    compilation = compiler(source)
    return choisi.generer(compilation.programme, compilation.analyse)


def executer(source: str, backend: str = "python") -> None:
    if not choisir_backend(backend).executable:
        raise ErreurAlto(f"le backend {backend!r} ne produit pas de Python exécutable")
    sortie = transpiler(source, backend)
    code = compile(sortie.code, NOM_FICHIER, "exec")
    try:
        exec(code, {"__name__": "__main__"})
    except Exception as exc:
        raise _traduire(exc, sortie.correspondance) from exc
```

(`compiler`, `_traduire`, `MESSAGES` et `NOM_FICHIER` ne changent pas.)

### 3.4 Le formateur (`alto/formateur.py`, Fatoumata)

Il ressemble beaucoup au générateur Python, mais **produit de l'Alto**. Il réutilise l'`Emetteur`, avec `vide=None` (un bloc Alto vide n'a pas besoin de `pass`) et des accolades.

**La seule vraie difficulté : les parenthèses minimales.** Règle : une sous-expression a besoin de parenthèses si sa précédence est **plus faible** que celle de l'opérateur parent. Et, comme nos opérateurs sont associatifs à gauche, l'opérande **droit** en a aussi besoin à précédence **égale** :

| Arbre | Écrit | Pourquoi |
|---|---|---|
| `(1 + 2) * 3` | `(1 + 2) * 3` | `+` (5) < `*` (6) : parenthèses nécessaires |
| `1 + (2 * 3)` | `1 + 2 * 3` | `*` (6) > `+` (5) : inutiles |
| `(a - b) - c` | `a - b - c` | à gauche, même niveau : inutiles |
| `a - (b - c)` | `a - (b - c)` | à **droite**, même niveau : nécessaires |

La table des précédences est **partagée avec le parser** (on importe `Precedence`) :

```python
"""Le backend Formateur : réécrit un programme Alto proprement présenté."""

from __future__ import annotations

from typing import assert_never

from alto.backend import Sortie
from alto.emetteur import Emetteur
from alto.noeuds import (
    Affectation, Appel, Binaire, Bloc, Booleen, Decimal, Declaration, Ecris, Entier, Expr,
    ExprInstr, Fonction, Index, Instr, Liste, Pour, Programme, Rends, Rien, Si, TantQue, Texte,
    Unaire, Variable,
)
from alto.parser import Precedence
from alto.semantique import Analyse

PRECEDENCES: dict[str, Precedence] = {
    "ou": Precedence.OU,
    "et": Precedence.ET,
    "==": Precedence.COMPARAISON, "!=": Precedence.COMPARAISON,
    "<": Precedence.COMPARAISON, "<=": Precedence.COMPARAISON,
    ">": Precedence.COMPARAISON, ">=": Precedence.COMPARAISON,
    "+": Precedence.SOMME, "-": Precedence.SOMME,
    "*": Precedence.PRODUIT, "/": Precedence.PRODUIT, "%": Precedence.PRODUIT,
}


def _precedence(expr: Expr) -> int:
    match expr:
        case Binaire(op):
            return PRECEDENCES[op]
        case Unaire(op):
            return Precedence.NON if op == "non" else Precedence.PREFIXE
        case _:
            return Precedence.APPEL + 1  # un atome n'a jamais besoin de parenthèses


def _texte_alto(valeur: str) -> str:
    echappe = (
        valeur.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
    )
    return f'"{echappe}"'


class Formateur:
    nom = "formateur"
    extension = ".alt"
    executable = False

    def generer(self, programme: Programme, analyse: Analyse) -> Sortie:
        return Sortie(self.formater(programme))

    def formater(self, programme: Programme) -> str:
        self.e = Emetteur()
        for instr in programme.instructions:
            self.instruction(instr)
        return self.e.texte()

    def corps(self, bloc: Bloc) -> None:
        with self.e.bloc(vide=None):
            for instr in bloc.instructions:
                self.instruction(instr)

    def expr(self, expr: Expr, parent: int = Precedence.AUCUNE, a_droite: bool = False) -> str:
        code = self._expr(expr)
        p = _precedence(expr)
        if p < parent or (a_droite and p == parent):
            return f"({code})"
        return code
```

À toi : `instruction` (un `match` sur chaque instruction, qui écrit `var x = …;`, `si … {`, `} sinon si … {`, `} sinon {`, `}`…) et `_expr` (un `match` sur chaque expression ; pour un `Binaire`, l'opérande gauche s'écrit `self.expr(gauche, p)` et le droit `self.expr(droite, p, a_droite=True)`).

<details>
<summary>▶ Solution</summary>

```python
    def instruction(self, instr: Instr) -> None:
        e = self.e
        match instr:
            case Declaration(nom, valeur):
                e.ligne(f"var {nom} = {self.expr(valeur)};")
            case Affectation(cible, valeur):
                e.ligne(f"{self.expr(cible)} = {self.expr(valeur)};")
            case Ecris(valeurs):
                e.ligne(f"ecris {', '.join(self.expr(v) for v in valeurs)};")
            case Si(branches, sinon):
                e.ligne(f"si {self.expr(branches[0].condition)} {{")
                self.corps(branches[0].corps)
                for branche in branches[1:]:
                    e.ligne(f"}} sinon si {self.expr(branche.condition)} {{")
                    self.corps(branche.corps)
                if sinon is not None:
                    e.ligne("} sinon {")
                    self.corps(sinon)
                e.ligne("}")
            case TantQue(condition, corps):
                e.ligne(f"tantque {self.expr(condition)} {{")
                self.corps(corps)
                e.ligne("}")
            case Pour(variable, debut, fin, corps):
                e.ligne(f"pour {variable} de {self.expr(debut)} jusqua {self.expr(fin)} {{")
                self.corps(corps)
                e.ligne("}")
            case Fonction(nom, parametres, corps):
                e.ligne(f"fonction {nom}({', '.join(parametres)}) {{")
                self.corps(corps)
                e.ligne("}")
            case Rends(valeur):
                e.ligne("rends;" if valeur is None else f"rends {self.expr(valeur)};")
            case ExprInstr(expr):
                e.ligne(f"{self.expr(expr)};")
            case _:
                assert_never(instr)

    def _expr(self, expr: Expr) -> str:
        match expr:
            case Entier(valeur):
                return str(valeur)
            case Decimal(valeur):
                return repr(valeur)
            case Texte(valeur):
                return _texte_alto(valeur)
            case Booleen(valeur):
                return "vrai" if valeur else "faux"
            case Rien():
                return "rien"
            case Variable(nom):
                return nom
            case Liste(elements):
                return "[" + ", ".join(self.expr(x) for x in elements) + "]"
            case Unaire(op, operande):
                if op == "non":
                    return f"non {self.expr(operande, Precedence.NON)}"
                return f"-{self.expr(operande, Precedence.PREFIXE)}"
            case Binaire(op, gauche, droite):
                p = PRECEDENCES[op]
                return f"{self.expr(gauche, p)} {op} {self.expr(droite, p, a_droite=True)}"
            case Appel(nom, arguments):
                return f"{nom}({', '.join(self.expr(a) for a in arguments)})"
            case Index(cible, indice):
                return f"{self.expr(cible, Precedence.APPEL)}[{self.expr(indice)}]"
            case _:
                assert_never(expr)
```

</details>

### 3.5 La sous-commande `fmt` (`alto/cli.py`)

Dans `_construire_parser`, avant `repl` :

```python
    fmt = commandes.add_parser("fmt", help="réécrit le programme proprement (perd les commentaires)")
    fmt.add_argument("fichier", type=Path)
    fmt.add_argument("--ecrire", action="store_true", help="réécrit le fichier en place")
```

Dans `main`, une branche de plus :

```python
        elif args.commande == "fmt":
            code = transpiler(source, backend="formateur").code
            if args.ecrire:
                fichier.write_text(code, encoding="utf-8")
            else:
                print(code, end="")
```

Ajoute aussi une option `--backend` à `run` et `transpile` (`choices=list(BACKENDS)`) et passe-la à `executer` / `transpiler`. `run --backend formateur` doit être refusé (code 1) : c'est déjà le cas grâce à `executer`.

### 3.6 `mypy --strict` (Arthur, avec chacun sur ses fichiers)

```bash
uv run mypy alto
```

La configuration (`strict = true`) est déjà dans `pyproject.toml`. Les erreurs les plus fréquentes :

| Message de mypy | Correction |
|---|---|
| `Function is missing a return type annotation` | ajouter `-> None` (ou le bon type) |
| `Missing type parameters for generic type "dict"` | écrire `dict[str, int]`, pas `dict` |
| `Item "None" of "X \| None" has no attribute …` | vérifier `if x is not None:` avant |
| `Argument 1 to "assert_never" has incompatible type "Pour"` | un `case Pour(…)` manque dans le `match` ! |
| `Returning Any from function declared to return …` | annoter la variable intermédiaire |

Pas de `# type: ignore` sans raison (le seul justifié pour l'instant : `fields(noeud)` dans `afficher_arbre`, qui reçoit un `object`).

## 4. Les tests à écrire

Pour le formateur, deux propriétés suffisent à couvrir presque tout, et se vérifient sur **chaque exemple** :

- **il préserve l'arbre** : `parse(formate(s)) == parse(s)` (c'est ici que `compare=False` sur `pos` prend tout son sens) ;
- **il est idempotent** : `formate(formate(s)) == formate(s)`.

```python
import subprocess
import sys
from pathlib import Path

import pytest

from alto.backend import Sortie
from alto.compilateur import BACKENDS, executer, transpiler
from alto.erreurs import ErreurAlto
from alto.noeuds import Programme
from alto.parser import parse
from alto.semantique import Analyse

RACINE = Path(__file__).parent.parent
EXEMPLES = sorted((RACINE / "exemples").glob("*.alt"))


def formate(source: str) -> str:
    return transpiler(source, backend="formateur").code


def test_la_liste_des_backends() -> None:
    assert set(BACKENDS) == {"python", "formateur"}


def test_un_backend_inconnu_est_refuse() -> None:
    with pytest.raises(ErreurAlto, match="backend inconnu"):
        transpiler("ecris 1;", backend="cobol")


def test_un_nouveau_backend_n_a_besoin_que_du_protocol(monkeypatch: pytest.MonkeyPatch) -> None:
    class Compteur:
        nom = "compteur"
        extension = ".txt"
        executable = False

        def generer(self, programme: Programme, analyse: Analyse) -> Sortie:
            return Sortie(str(len(programme.instructions)))

    monkeypatch.setitem(BACKENDS, "compteur", Compteur())
    assert transpiler("ecris 1; ecris 2;", backend="compteur").code == "2"


@pytest.mark.parametrize("exemple", EXEMPLES, ids=lambda p: p.stem)
def test_le_formateur_preserve_l_arbre(exemple: Path) -> None:
    source = exemple.read_text(encoding="utf-8")
    assert parse(formate(source)) == parse(source)


@pytest.mark.parametrize("exemple", EXEMPLES, ids=lambda p: p.stem)
def test_le_formateur_est_idempotent(exemple: Path) -> None:
    une_fois = formate(exemple.read_text(encoding="utf-8"))
    assert formate(une_fois) == une_fois


@pytest.mark.parametrize(
    ("source", "attendu"),
    [
        ("ecris ((x));", "ecris x;\n"),
        ("ecris (1 + 2) * 3;", "ecris (1 + 2) * 3;\n"),
        ("ecris 1 + (2 * 3);", "ecris 1 + 2 * 3;\n"),
        ("ecris (a - b) - c;", "ecris a - b - c;\n"),
        ("ecris a - (b - c);", "ecris a - (b - c);\n"),
        ("ecris (non a) == b;", "ecris (non a) == b;\n"),
    ],
)
def test_parentheses_minimales(source: str, attendu: str) -> None:
    prefixe = "var x = 1; var a = 1; var b = 2; var c = 3;\n"
    assert formate(prefixe + source).endswith(attendu)


def test_le_formateur_n_est_pas_executable() -> None:
    with pytest.raises(ErreurAlto, match="exécutable"):
        executer("ecris 1;", backend="formateur")


def test_mypy_strict_passe() -> None:
    resultat = subprocess.run(
        [sys.executable, "-m", "mypy", "--strict", str(RACINE / "alto")],
        capture_output=True, text=True,
    )
    assert resultat.returncode == 0, resultat.stdout
```

À ajouter : un texte avec guillemets et `\n` est bien réécrit ; `fmt --ecrire` réécrit le fichier (avec `tmp_path`).

## 5. Pièges fréquents

| Symptôme | Cause |
|---|---|
| `ImportError: cannot import name … (circular import)` | `backend.py` ne doit importer **ni** le générateur **ni** le formateur |
| `a - (b - c)` perd ses parenthèses | `a_droite=True` oublié pour l'opérande droit |
| `(non a) == b` devient `non a == b` (sens différent !) | la précédence de `non` (3) doit être comparée à celle de `==` (4) |
| le formateur n'est pas idempotent | un espace ou une ligne vide en trop quelque part : compare les deux sorties |

## 6. C'est fini quand…

- [ ] `uv run pytest -k etape_10` est vert ;
- [ ] `uv run mypy alto` affiche `Success` ;
- [ ] `uv run python -m alto fmt` remet en forme un fichier laid.
