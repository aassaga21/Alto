# Étape 8 : la génération de Python

**Qui :** Arthur. **Fichiers :** `alto/emetteur.py`, `alto/generateur.py`, `alto/compilateur.py`, `tests/test_etape_08_generation.py`. **Énoncé :** `langage/etapes/08_generation.md`.

> **En une phrase :** transformer l'arbre vérifié en **texte Python**, l'exécuter, et obtenir **exactement** la sortie de chaque fichier `.attendu`.

**Tu as besoin de :** `noeuds.py` (Luca). Tu peux commencer tout de suite en construisant les arbres à la main ; le test central, lui, attendra le parser (Fatoumata) et l'analyse (Luca).

## 1. Comprendre

On parcourt l'arbre et, pour chaque nœud, on écrit le Python équivalent :

| Alto | Python généré |
|---|---|
| `var x = 3;` | `x = 3` |
| `ecris a, b;` | `_ecris(a, b)` |
| `si c { … } sinon si d { … } sinon { … }` | `if c:` … `elif d:` … `else:` … |
| `tantque c { … }` | `while c:` … |
| `pour i de 1 jusqua n { … }` | `for i in range(1, n + 1):` … ← **borne incluse** |
| `fonction f(a) { … }` | `def f(a):` … |
| `rends x;` | `return x` |
| `vrai` / `faux` / `rien` | `True` / `False` / `None` |
| `a et b`, `a ou b`, `non a` | `a and b`, `a or b`, `not a` |
| `taille(l)`, `ajoute(l, x)`, `texte(x)` | `_taille(l)`, `_ajoute(l, x)`, `_texte(x)` |

Par exemple, `exemples/02_factorielle.alt` devient :

```python
def factorielle(n):
    if n <= 1:
        return 1
    return n * factorielle(n - 1)
def factorielle_boucle(n):
    resultat = 1
    for i in range(2, n + 1):
        resultat = resultat * i
    return resultat
for k in range(0, 5 + 1):
    _ecris(k, factorielle(k), factorielle_boucle(k))
_ecris(factorielle(20))
```

précédé d'un **prélude** : les fonctions `_ecris`, `_texte`… qui affichent « à la façon d'Alto ».

### Les quatre problèmes à régler

1. **Les priorités ne sont pas celles de Python.** `a < b < c` est une comparaison chaînée en Python, mais `(a < b) < c` en Alto. Solution simple : **mettre entre parenthèses toute opération qui est à l'intérieur d'une autre** : `(a < b) < c`.
2. **Les noms qui gênent.** Un programme Alto peut avoir une variable `print`, `list` ou `class`. On les renomme `_v_print`, `_v_list`, `_v_class`. Comme le lexer interdit les noms commençant par `_`, aucune collision n'est possible.
3. **L'affichage.** `print(True)` affiche `True`, mais Alto veut `vrai`. D'où le prélude.
4. **Les globales modifiées.** Grâce à l'analyse (étape 7), on écrit `global appels` en tête des fonctions qui modifient une globale.

## 2. Le Python à connaître

### Un context manager pour l'indentation

```python
with e.bloc():          # niveau d'indentation +1
    e.ligne("x = 1")    # écrit "    x = 1"
# niveau d'indentation revenu à la normale, même en cas d'exception
```

### `match` / `case` sur des dataclasses

```python
match noeud:
    case Binaire(op, gauche, droite):   # vérifie le type ET récupère les champs
        ...
    case Entier(valeur):
        ...
    case _:
        assert_never(noeud)
```

Les champs sont récupérés **dans l'ordre de leur déclaration** dans la dataclass.

### `assert_never` : mypy vérifie qu'on n'a rien oublié

Dans le dernier `case _:`, `assert_never(noeud)` dit à mypy « on ne doit jamais arriver ici ». Si Luca ajoute un nouveau nœud à `Expr` et que tu oublies son `case`, **mypy te le signale**.

### `repr` d'un texte : un littéral Python sûr

```python
repr('il a dit "oui"\n')   # "'il a dit \"oui\"\\n'" : un littéral Python valide, échappements compris
```

Jamais le contenu d'un texte Alto ne pourra devenir du code Python.

## 3. Pas à pas

### 3.1 L'émetteur (`alto/emetteur.py`)

```python
"""Produit du code indenté, ligne par ligne."""

from collections.abc import Iterator
from contextlib import contextmanager


class Emetteur:
    def __init__(self, indentation: str = "    ") -> None:
        self._lignes: list[str] = []
        self._indentation = indentation
        self.niveau = 0

    def ligne(self, texte: str = "") -> None:
        """Ajoute une ligne au niveau d'indentation courant."""
        self._lignes.append(self._indentation * self.niveau + texte)

    @contextmanager
    def bloc(self, vide: str | None = "pass") -> Iterator[None]:
        avant = len(self._lignes)
        self.niveau += 1
        try:
            yield
            if len(self._lignes) == avant and vide is not None:
                self.ligne(vide)  # un bloc Python ne peut pas être vide
        finally:
            self.niveau -= 1

    def texte(self) -> str:
        return "\n".join(self._lignes) + "\n"
```

`si vrai { }` donnera `if True:` / `    pass`.

### 3.2 Le prélude et les noms (`alto/generateur.py`)

```python
"""Traduction de l'arbre Alto en texte Python."""

from __future__ import annotations

import builtins
import keyword
from typing import assert_never

from alto.emetteur import Emetteur
from alto.noeuds import (
    Affectation, Appel, Binaire, Bloc, Booleen, Decimal, Declaration, Ecris, Entier, Expr,
    ExprInstr, Fonction, Index, Instr, Liste, Pour, Programme, Rends, Rien, Si, TantQue, Texte,
    Unaire, Variable,
)
from alto.semantique import PREDEFINIES, Analyse

PRELUDE = '''\
def _texte(valeur):
    if valeur is True:
        return "vrai"
    if valeur is False:
        return "faux"
    if valeur is None:
        return "rien"
    if isinstance(valeur, list):
        return "[" + ", ".join(_texte(v) for v in valeur) + "]"
    return str(valeur)


def _ecris(*valeurs):
    print(" ".join(_texte(v) for v in valeurs))


def _taille(valeur):
    return len(valeur)


def _ajoute(liste, valeur):
    liste.append(valeur)
'''

NOMS_RESERVES = set(keyword.kwlist) | set(keyword.softkwlist) | set(dir(builtins))

OPERATEURS = {"et": "and", "ou": "or", "non": "not"}


def nom_python(nom: str) -> str:
    """Renomme les noms qui gêneraient en Python (`print`, `class`, `list`...)."""
    return f"_v_{nom}" if nom in NOMS_RESERVES else nom
```

> Pourquoi `valeur is True` et pas `valeur == True` ? Parce que `1 == True` est vrai en Python : `ecris 1;` afficherait `vrai` !

### 3.3 Les expressions

```python
class GenerateurPython:
    def __init__(self, analyse: Analyse) -> None:
        self.analyse = analyse
        self.e = Emetteur()

    def sous(self, expr: Expr) -> str:
        """Une sous-expression : parenthésée si c'est une opération."""
        code = self.expr(expr)
        return f"({code})" if isinstance(expr, (Binaire, Unaire)) else code

    def expr(self, expr: Expr) -> str:
        match expr:
            case Entier(valeur):
                return str(valeur)
            case Texte(valeur):
                return repr(valeur)
            case Booleen(valeur):
                return "True" if valeur else "False"
            case Variable(nom):
                return nom_python(nom)
            case Binaire(op, gauche, droite):
                return f"{self.sous(gauche)} {OPERATEURS.get(op, op)} {self.sous(droite)}"
            # ... à compléter
            case _:
                assert_never(expr)
```

À toi : `Decimal` (`repr(valeur)`), `Rien` (`case Rien():`), `Liste`, `Unaire` (`not …` ou `-…`, avec `self.sous`), `Appel` (une prédéfinie devient `_taille`… ; sinon `nom_python(nom)`), `Index` (`f"{self.sous(cible)}[{self.expr(indice)}]"`).

<details>
<summary>▶ Solution</summary>

```python
            case Decimal(valeur):
                return repr(valeur)
            case Rien():
                return "None"
            case Liste(elements):
                return "[" + ", ".join(self.expr(x) for x in elements) + "]"
            case Unaire(op, operande):
                if op == "non":
                    return f"not {self.sous(operande)}"
                return f"-{self.sous(operande)}"
            case Appel(nom, arguments):
                fonction = f"_{nom}" if nom in PREDEFINIES else nom_python(nom)
                return f"{fonction}({', '.join(self.expr(a) for a in arguments)})"
            case Index(cible, indice):
                return f"{self.sous(cible)}[{self.expr(indice)}]"
```

</details>

### 3.4 Les instructions

```python
    def programme(self, programme: Programme) -> str:
        for instr in programme.instructions:
            self.instruction(instr)
        return self.e.texte()

    def bloc(self, bloc: Bloc) -> None:
        with self.e.bloc():
            for instr in bloc.instructions:
                self.instruction(instr)

    def instruction(self, instr: Instr) -> None:
        e = self.e
        match instr:
            case Declaration(nom, valeur):
                e.ligne(f"{nom_python(nom)} = {self.expr(valeur)}")
            case TantQue(condition, corps):
                e.ligne(f"while {self.expr(condition)}:")
                self.bloc(corps)
            case Pour(variable, debut, fin, corps):
                # la borne de fin est INCLUSE en Alto, exclue par range()
                e.ligne(
                    f"for {nom_python(variable)} in range({self.expr(debut)}, {self.sous(fin)} + 1):"
                )
                self.bloc(corps)
            # ... à compléter
            case _:
                assert_never(instr)
```

À toi : `Affectation`, `Ecris` (`_ecris(a, b)`), `Rends` (`return` ou `return x`), `ExprInstr`, `Si` (`if` pour la première branche, `elif` pour les suivantes, puis `else`), et `Fonction` : `def f(a, b):`, puis **dans le bloc**, une ligne `global …` si `self.analyse.globales_modifiees[nom]` n'est pas vide, puis les instructions du corps.

<details>
<summary>▶ Solution</summary>

```python
            case Affectation(cible, valeur):
                e.ligne(f"{self.expr(cible)} = {self.expr(valeur)}")
            case Ecris(valeurs):
                e.ligne(f"_ecris({', '.join(self.expr(v) for v in valeurs)})")
            case Si(branches, sinon):
                for i, branche in enumerate(branches):
                    mot = "if" if i == 0 else "elif"
                    e.ligne(f"{mot} {self.expr(branche.condition)}:")
                    self.bloc(branche.corps)
                if sinon is not None:
                    e.ligne("else:")
                    self.bloc(sinon)
            case Fonction(nom, parametres, corps):
                params = ", ".join(nom_python(p) for p in parametres)
                e.ligne(f"def {nom_python(nom)}({params}):")
                with e.bloc():
                    globales = sorted(self.analyse.globales_modifiees.get(nom, set()))
                    if globales:
                        e.ligne("global " + ", ".join(nom_python(g) for g in globales))
                    for sous_instr in corps.instructions:
                        self.instruction(sous_instr)
            case Rends(valeur):
                e.ligne("return" if valeur is None else f"return {self.expr(valeur)}")
            case ExprInstr(expr):
                e.ligne(self.expr(expr))
```

</details>

### 3.5 Tout assembler (`alto/compilateur.py`)

```python
"""La façade du compilateur (complétée à l'étape 9)."""

from alto.generateur import PRELUDE, GenerateurPython
from alto.parser import parse
from alto.semantique import analyser


def transpiler(source: str) -> str:
    programme = parse(source)
    analyse = analyser(programme)
    return PRELUDE + GenerateurPython(analyse).programme(programme)


def executer(source: str) -> None:
    code = transpiler(source)
    exec(compile(code, "<alto>", "exec"), {"__name__": "__main__"})
```

**Le grand moment :**

```bash
uv run python -c "from alto.compilateur import executer; executer(open('exemples/01_bonjour.alt').read())"
```

```
Bonjour, Alto !
version 1.0
actif : vrai valeur : rien
3.5 1 -9
Elle a dit "oui".
```

Pour voir le Python produit : `print(transpiler(...))` au lieu de `executer(...)`.

## 4. Les tests à écrire

### Le test central du projet

```python
from pathlib import Path

import pytest

from alto.compilateur import executer, transpiler
from alto.emetteur import Emetteur

EXEMPLES = Path(__file__).parent.parent / "exemples"


@pytest.mark.parametrize("exemple", sorted(EXEMPLES.glob("*.alt")), ids=lambda p: p.stem)
def test_exemple_produit_sa_sortie_attendue(
    exemple: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    executer(exemple.read_text(encoding="utf-8"))
    attendu = exemple.with_suffix(".attendu").read_text(encoding="utf-8")
    assert capsys.readouterr().out == attendu
```

Ce test **tourne automatiquement sur chaque nouvel exemple** ajouté dans `exemples/`. Il doit rester vert sur `main` en permanence.

### Les autres

```python
def test_l_emetteur_ajoute_pass_a_un_bloc_vide() -> None:
    e = Emetteur()
    e.ligne("if x:")
    with e.bloc():
        pass
    assert e.texte() == "if x:\n    pass\n"


def test_l_emetteur_retrouve_son_niveau_apres_une_exception() -> None:
    e = Emetteur()
    with pytest.raises(ValueError):
        with e.bloc():
            raise ValueError
    assert e.niveau == 0


def test_les_noms_python_sont_renommes(capsys: pytest.CaptureFixture[str]) -> None:
    executer("var print = 2; var list = [print]; ecris print, list;")
    assert capsys.readouterr().out == "2 [2]\n"


def test_comparaison_non_chainee(capsys: pytest.CaptureFixture[str]) -> None:
    executer("ecris 3 > 2 > 1;")  # (3 > 2) > 1  ->  vrai > 1  ->  faux
    assert capsys.readouterr().out == "faux\n"


def test_une_fonction_modifie_une_globale(capsys: pytest.CaptureFixture[str]) -> None:
    executer("var n = 0; fonction f() { n = n + 1; } f(); f(); ecris n;")
    assert capsys.readouterr().out == "2\n"


def test_la_borne_de_fin_est_incluse(capsys: pytest.CaptureFixture[str]) -> None:
    executer("pour i de 1 jusqua 3 { ecris i; }")
    assert capsys.readouterr().out == "1\n2\n3\n"


def test_le_code_genere_compile() -> None:
    compile(transpiler("si vrai { } sinon { ecris 1; }"), "<test>", "exec")
```

> `3 > 2 > 1` vaut `True` en Python (comparaison chaînée), mais `faux` en Alto : ce test prouve que les parenthèses font leur travail.

À ajouter : le texte Python produit pour quelques petits programmes (`assert transpiler("var x = 1;").endswith("x = 1\n")`), `ecris texte(vrai);`, un texte avec des guillemets et un `\n`.

## 5. Pièges fréquents

| Symptôme | Cause |
|---|---|
| `IndentationError` dans le code généré | une instruction écrite hors du `with e.bloc()` |
| `UnboundLocalError` | le `global` n'est pas émis (voir `Analyse.globales_modifiees`) |
| `ecris 1;` affiche `vrai` | `valeur == True` au lieu de `valeur is True` dans le prélude |
| la boucle fait un tour de moins | le `+ 1` de la borne de fin est oublié |
| le test central échoue d'un seul caractère | un `.attendu` sans saut de ligne final, ou un espace en trop : compare avec `-vv` |

## 6. C'est fini quand…

- [ ] **les 5 exemples produisent exactement leur `.attendu`** ;
- [ ] `uv run pytest -k etape_08` est vert ;
- [ ] tu as fait la démo à l'équipe : Alto tourne de bout en bout ! 🎉
