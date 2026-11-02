# Étape 7 : l'analyse sémantique

**Qui :** Luca. **Fichiers :** `alto/symboles.py`, `alto/semantique.py`, `tests/test_etape_07_semantique.py`. **Énoncé :** `langage/etapes/07_semantique.md`.

> **En une phrase :** parcourir l'arbre pour vérifier ce que la grammaire ne voit pas (variable non déclarée, double déclaration, `rends` hors fonction, mauvais nombre d'arguments…) et noter ce dont le générateur aura besoin.

**Tu as besoin de :** `noeuds.py` (le tien). Tu peux commencer **avant** que le parser soit fini en construisant les arbres à la main ; ensuite, tes tests utiliseront `parse("…")`, beaucoup plus lisible.

## 1. Comprendre

`ecris y;` est **grammaticalement** correct (le parser l'accepte), mais n'a pas de **sens** si `y` n'a jamais été déclaré. C'est le travail de cette étape.

### La table des symboles : une pile de portées

Une **portée**, c'est un dictionnaire « nom → ce qu'on sait de ce nom ». On en empile une à chaque bloc :

```
var a = 1;                    portées : [ globale{taille, ajoute, texte, a} ]
fonction f(n) {               portées : [ globale{…, a, f}, f{n} ]
    si n > 0 {                portées : [ globale{…}, f{n}, bloc{} ]
        var b = n;            portées : [ globale{…}, f{n}, bloc{b} ]
        ecris a, b;           → on cherche `a` du haut vers le bas : trouvé dans globale ✓
    }                         portées : [ globale{…}, f{n} ]       (bloc refermé : b n'existe plus)
    ecris b;                  → `b` introuvable : ERREUR « 'b' n'est pas déclaré »
}
```

- **déclarer** un nom = l'ajouter à la portée du **haut** ;
- **chercher** un nom = le chercher de la portée du haut vers celle du bas.

### Le piège : Python n'a pas de portée de bloc

Alto ouvre une portée à chaque `{ }`, mais **pas Python**. Si on traduisait bêtement :

```
var x = 1;
si vrai { var x = 2; }
ecris x;            # en Alto on attend 1…
```

…le Python `x = 1` / `if True: x = 2` / `print(x)` afficherait `2`. La spécification d'Alto règle ça simplement : **pas de masquage**, on ne peut pas déclarer un nom déjà visible. Ça règle aussi le cas « une fonction lit une globale puis déclare une locale de même nom ».

Il reste un piège, que l'analyse doit **noter** pour le générateur :

```
var appels = 0;
fonction f() { appels = appels + 1; }
```

En Python, `appels = appels + 1` dans une fonction crée une variable **locale** → `UnboundLocalError`. Il faut écrire `global appels` en tête de la fonction. L'analyse note donc, pour chaque fonction, **les globales qu'elle modifie**.

## 2. Le Python à connaître

### `@contextmanager` : du code exécuté à l'entrée et à la sortie d'un `with`

```python
from contextlib import contextmanager

@contextmanager
def portee():
    print("j'ouvre")
    try:
        yield          # ici s'exécute le corps du `with`
    finally:
        print("je ferme")   # exécuté MÊME si une exception traverse le with

with portee():
    print("dedans")
# j'ouvre / dedans / je ferme
```

### `singledispatchmethod` : une méthode différente selon le type de l'argument

Au lieu de :

```python
def instruction(self, noeud):
    if isinstance(noeud, Declaration): ...
    elif isinstance(noeud, Si): ...
    elif ...   # 9 cas !
```

on écrit une méthode par type, et Python choisit la bonne d'après **l'annotation** du paramètre :

```python
from functools import singledispatchmethod

class Analyseur:
    @singledispatchmethod
    def instruction(self, noeud: Instr) -> None:
        raise NotImplementedError(f"instruction non gérée : {type(noeud).__name__}")

    @instruction.register
    def _(self, noeud: Declaration) -> None:   # appelée quand noeud est une Declaration
        ...

    @instruction.register
    def _(self, noeud: Si) -> None:            # appelée quand noeud est un Si
        ...
```

Les variantes peuvent toutes s'appeler `_` : seul compte l'enregistrement.

## 3. Pas à pas

### 3.1 La table des symboles (`alto/symboles.py`)

```python
"""La table des symboles : une pile de portées."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum, auto

from alto.erreurs import Position


class Genre(Enum):
    VARIABLE = auto()
    FONCTION = auto()
    PREDEFINIE = auto()


@dataclass(frozen=True, slots=True)
class Symbole:
    nom: str
    genre: Genre
    pos: Position
    nb_parametres: int = 0  # pour les fonctions


@dataclass
class Portee:
    nom: str
    est_fonction: bool = False
    symboles: dict[str, Symbole] = field(default_factory=dict)


class TableSymboles:
    def __init__(self) -> None:
        self._portees: list[Portee] = []

    @contextmanager
    def portee(self, nom: str = "bloc", *, fonction: bool = False) -> Iterator[Portee]:
        portee = Portee(nom, est_fonction=fonction)
        self._portees.append(portee)
        try:
            yield portee
        finally:
            self._portees.pop()

    @property
    def profondeur(self) -> int:
        return len(self._portees)

    def declarer(self, symbole: Symbole) -> None:
        self._portees[-1].symboles[symbole.nom] = symbole

    def chercher(self, nom: str) -> Symbole | None:
        for portee in reversed(self._portees):
            if nom in portee.symboles:
                return portee.symboles[nom]
        return None

    def est_globale(self, nom: str) -> bool:
        """Vrai si `nom` désigne un symbole de la portée globale (la plus basse)."""
        for portee in reversed(self._portees[1:]):
            if nom in portee.symboles:
                return False
        return bool(self._portees) and nom in self._portees[0].symboles
```

### 3.2 Le squelette de l'analyseur (`alto/semantique.py`)

```python
"""L'analyse sémantique d'Alto."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import singledispatchmethod

from alto.erreurs import SANS_POSITION, ErreurAlto, ErreursMultiples, ErreurSemantique, Position
from alto.noeuds import (
    Affectation, Appel, Binaire, Bloc, Booleen, Decimal, Declaration, Ecris, Entier, Expr,
    ExprInstr, Fonction, Index, Instr, Liste, Pour, Programme, Rends, Rien, Si, TantQue, Texte,
    Unaire, Variable,
)
from alto.symboles import Genre, Symbole, TableSymboles

#: Les fonctions prédéfinies et leur nombre d'arguments.
PREDEFINIES: dict[str, int] = {"taille": 1, "ajoute": 2, "texte": 1}


@dataclass
class Analyse:
    """Ce que le générateur a besoin de savoir."""

    globales_modifiees: dict[str, set[str]] = field(default_factory=dict)


class Analyseur:
    def __init__(self) -> None:
        self.table = TableSymboles()
        self.erreurs: list[ErreurAlto] = []
        self.resultat = Analyse()
        self._fonction: str | None = None  # le nom de la fonction en cours d'analyse

    def analyser(self, programme: Programme) -> Analyse:
        with self.table.portee("globale"):
            for nom, nb in PREDEFINIES.items():
                self.table.declarer(Symbole(nom, Genre.PREDEFINIE, SANS_POSITION, nb))
            for instr in programme.instructions:
                self.instruction(instr)
        return self.resultat

    def erreur(self, message: str, pos: Position) -> None:
        self.erreurs.append(ErreurSemantique(message, pos))  # on NOTE, on ne lève pas

    def declarer(self, nom: str, genre: Genre, pos: Position, nb_parametres: int = 0) -> None:
        existant = self.table.chercher(nom)
        if existant is not None:  # règle « pas de masquage »
            if existant.genre is Genre.PREDEFINIE:
                self.erreur(f"'{nom}' est une fonction prédéfinie, ce nom est réservé", pos)
            else:
                self.erreur(f"'{nom}' est déjà déclaré ({existant.pos})", pos)
            return
        self.table.declarer(Symbole(nom, genre, pos, nb_parametres))

    def bloc(self, bloc: Bloc) -> None:
        with self.table.portee():
            for instr in bloc.instructions:
                self.instruction(instr)
```

> ⚠️ Avec `singledispatchmethod`, **toutes les classes de nœuds doivent être importées** (pas seulement sous `if TYPE_CHECKING`) : Python lit les annotations pour savoir quelle méthode appeler.

Et en bas du fichier, le point d'entrée :

```python
def analyser(programme: Programme) -> Analyse:
    analyseur = Analyseur()
    resultat = analyseur.analyser(programme)
    if analyseur.erreurs:
        raise ErreursMultiples(analyseur.erreurs) from analyseur.erreurs[0]
    return resultat
```

### 3.3 Les instructions

Trois exemples pour comprendre le principe :

```python
    @singledispatchmethod
    def instruction(self, noeud: Instr) -> None:
        raise NotImplementedError(f"instruction non gérée : {type(noeud).__name__}")

    @instruction.register
    def _(self, noeud: Declaration) -> None:
        self.expression(noeud.valeur)  # AVANT de déclarer : `var x = x;` est faux
        self.declarer(noeud.nom, Genre.VARIABLE, noeud.pos)

    @instruction.register
    def _(self, noeud: Pour) -> None:
        self.expression(noeud.debut)
        self.expression(noeud.fin)
        with self.table.portee("pour"):  # la variable n'existe que dans la boucle
            self.declarer(noeud.variable, Genre.VARIABLE, noeud.pos)
            self.bloc(noeud.corps)

    @instruction.register
    def _(self, noeud: Rends) -> None:
        if self._fonction is None:
            self.erreur("'rends' en dehors d'une fonction", noeud.pos)
        if noeud.valeur is not None:
            self.expression(noeud.valeur)
```

À toi : `Ecris` (analyser chaque valeur), `Si` (chaque condition et chaque bloc, plus le `sinon`), `TantQue`, `ExprInstr`. Puis les deux plus délicates :

**`Fonction`** :
1. si `self.table.profondeur > 1`, on n'est pas au niveau global → erreur ;
2. déclarer le nom de la fonction **avant** d'analyser son corps (sinon la récursion `factorielle(n - 1)` ne trouverait pas `factorielle`) ;
3. préparer `self.resultat.globales_modifiees[nom] = set()` ;
4. retenir `self._fonction = nom` (et remettre l'ancienne valeur dans un `finally`) ;
5. ouvrir une portée de fonction, y déclarer les paramètres, analyser le corps.

**`Affectation`** : si la cible est une `Variable`, vérifier qu'elle est déclarée et que c'est bien une variable ; **et si on est dans une fonction et que le nom est global**, l'ajouter aux globales modifiées. Si c'est un `Index`, analyser la cible et l'indice. Dans les deux cas, analyser la valeur.

<details>
<summary>▶ Solution</summary>

```python
    @instruction.register
    def _(self, noeud: Fonction) -> None:
        if self.table.profondeur > 1:
            self.erreur("une fonction se déclare au niveau global, pas dans un bloc", noeud.pos)
            return
        # déclarée AVANT le corps : la fonction peut s'appeler elle-même
        self.declarer(noeud.nom, Genre.FONCTION, noeud.pos, len(noeud.parametres))
        self.resultat.globales_modifiees[noeud.nom] = set()
        precedente = self._fonction
        self._fonction = noeud.nom
        try:
            with self.table.portee(noeud.nom, fonction=True):
                for parametre in noeud.parametres:
                    self.declarer(parametre, Genre.VARIABLE, noeud.pos)
                self.bloc(noeud.corps)
        finally:
            self._fonction = precedente

    @instruction.register
    def _(self, noeud: Affectation) -> None:
        match noeud.cible:
            case Variable(nom):
                symbole = self.table.chercher(nom)
                if symbole is None:
                    self.erreur(f"'{nom}' n'est pas déclaré", noeud.cible.pos)
                elif symbole.genre is not Genre.VARIABLE:
                    self.erreur(f"'{nom}' est une fonction, on ne peut pas lui affecter", noeud.cible.pos)
                elif self._fonction is not None and self.table.est_globale(nom):
                    self.resultat.globales_modifiees[self._fonction].add(nom)
            case Index(cible, indice):
                self.expression(cible)
                self.expression(indice)
        self.expression(noeud.valeur)
```

</details>

### 3.4 Les expressions

Même principe, avec une seconde méthode `expression` en `singledispatchmethod`. Un littéral est toujours correct ; on peut enregistrer plusieurs types d'un coup avec une union :

```python
    @singledispatchmethod
    def expression(self, noeud: Expr) -> None:
        raise NotImplementedError(f"expression non gérée : {type(noeud).__name__}")

    @expression.register
    def _(self, noeud: Entier | Decimal | Texte | Booleen | Rien) -> None:
        pass  # un littéral est toujours correct

    @expression.register
    def _(self, noeud: Variable) -> None:
        symbole = self.table.chercher(noeud.nom)
        if symbole is None:
            self.erreur(f"'{noeud.nom}' n'est pas déclaré", noeud.pos)
        elif symbole.genre is not Genre.VARIABLE:
            self.erreur(f"'{noeud.nom}' est une fonction, pas une variable", noeud.pos)
```

À toi : `Liste`, `Unaire`, `Binaire`, `Index` (analyser les enfants), et `Appel` : la fonction doit exister, ne pas être une variable, et recevoir **le bon nombre d'arguments** (message : `'f' attend 1 argument(s), en reçoit 2`). N'oublie pas d'analyser les arguments.

## 4. Les tests à écrire

Une table paramétrée `(source, fragment du message)` est la façon la plus lisible de tester toutes les règles :

```python
from functools import singledispatchmethod

import pytest

from alto.erreurs import ErreursMultiples
from alto.parser import parse
from alto.semantique import Analyseur, analyser
from alto.symboles import TableSymboles


def erreurs_de(source: str) -> list[str]:
    with pytest.raises(ErreursMultiples) as erreur:
        analyser(parse(source))
    return [e.message for e in erreur.value.erreurs]


@pytest.mark.parametrize(
    ("source", "fragment"),
    [
        ("ecris x;", "'x' n'est pas déclaré"),
        ("var x = 1; var x = 2;", "déjà déclaré"),
        ("var x = x;", "'x' n'est pas déclaré"),
        ("si vrai { var y = 1; } ecris y;", "'y' n'est pas déclaré"),
        ("rends 1;", "en dehors d'une fonction"),
        ("ecris g(1);", "fonction inconnue"),
        ("fonction f(a) { rends a; } ecris f(1, 2);", "attend 1 argument"),
        ("var taille = 3;", "prédéfinie"),
        ("var x = 1; si vrai { var x = 2; }", "déjà déclaré"),
        ("si vrai { fonction f() { } }", "niveau global"),
    ],
)
def test_regles_semantiques(source: str, fragment: str) -> None:
    assert any(fragment in message for message in erreurs_de(source))


def test_toutes_les_erreurs_sont_signalees() -> None:
    assert len(erreurs_de("ecris a;\necris b;")) == 2


def test_deux_blocs_freres_peuvent_reutiliser_un_nom() -> None:
    analyser(parse("si vrai { var x = 1; } si vrai { var x = 2; }"))


def test_une_fonction_recursive_est_acceptee() -> None:
    analyser(parse("fonction f(n) { rends f(n - 1); }"))


def test_globales_modifiees() -> None:
    analyse = analyser(parse("var a = 0; var b = 0; fonction f() { a = 1; ecris b; }"))
    assert analyse.globales_modifiees == {"f": {"a"}}  # b est lue, pas modifiée


def test_l_analyseur_utilise_singledispatchmethod() -> None:
    assert isinstance(Analyseur.__dict__["instruction"], singledispatchmethod)


def test_la_portee_est_refermee_meme_en_cas_d_exception() -> None:
    table = TableSymboles()
    with pytest.raises(ValueError):
        with table.portee():
            raise ValueError
    assert table.profondeur == 0
```

À ajouter : les 5 exemples passent l'analyse sans erreur ; la **position** (ligne, colonne) de chaque erreur ; une variable de boucle `i` inutilisable après la boucle ; appeler une variable (`var x = 1; x();`) ; utiliser une fonction comme variable (`ecris f;`).

## 5. Pièges fréquents

| Symptôme | Cause |
|---|---|
| `NotImplementedError: instruction non gérée : Si` | la variante pour `Si` manque, ou son annotation est fausse |
| la récursion est refusée | le nom de la fonction est déclaré **après** l'analyse du corps |
| `var x = x;` est accepté | la valeur est analysée **après** la déclaration |
| la portée n'est pas refermée après une erreur | il manque le `try / finally` dans `portee()` |

## 6. C'est fini quand…

- [ ] `uv run pytest -k etape_07` est vert ;
- [ ] chaque règle de la section *Sémantique* de `specification.md` a au moins un test ;
- [ ] tu as montré à Arthur ce que contient `Analyse` (il en a besoin pour `global`).
