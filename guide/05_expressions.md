# Étape 5 : le parser des expressions (méthode de Pratt)

**Qui :** Fatoumata. **Fichiers :** `alto/parser.py`, `tests/test_etape_05_expressions.py`. **Énoncé :** `langage/etapes/05_expressions.md`.

> **En une phrase :** transformer une suite de tokens comme `1 + 2 * 3` en l'arbre `Binaire('+', 1, Binaire('*', 2, 3))`, en respectant les priorités.

**Tu as besoin de :** `tokens.py` et `flux.py` (Alexandra), `noeuds.py` (Luca). En attendant qu'ils soient prêts, lis ce guide et écris les tests : ils ne dépendent que des noms décidés en réunion 0.

## 1. Comprendre

### Le problème

`1 + 2 * 3` doit donner `1 + (2 * 3)`, et `1 - 2 - 3` doit donner `(1 - 2) - 3`. Il faut donc savoir **jusqu'où** un opérateur « attrape » ce qui est à sa droite.

### L'idée de Pratt, avec des mots simples

Chaque opérateur a une **force** (sa précédence) :

```
ou : 1    et : 2    non : 3    == < … : 4    + - : 5    * / % : 6    - unaire : 7    f(…) t[…] : 8
```

La fonction `expression(precedence)` veut dire : « lis une expression, mais **arrête-toi** dès que tu rencontres un opérateur qui n'est **pas plus fort** que `precedence` ».

1. Lire un token et appliquer sa règle **préfixe** (un nombre, une variable, `(`, un `-` unaire…) → on a l'opérande de gauche.
2. **Tant que** le token suivant est un opérateur **infixe strictement plus fort** que `precedence` : l'appliquer, avec ce qu'on a déjà à gauche.
3. Renvoyer le résultat.

### Déroulé sur `1 + 2 * 3`

```
expression(0)
  préfixe : 1                                 gauche = 1
  suivant '+' (5) > 0 ? oui → règle de '+' :
      droite = expression(5)
          préfixe : 2                         gauche = 2
          suivant '*' (6) > 5 ? oui → règle de '*' :
              droite = expression(6)
                  préfixe : 3 ; suivant FIN : pas un opérateur → rend 3
              gauche = 2 * 3
          suivant FIN → rend (2 * 3)
      gauche = 1 + (2 * 3)
  suivant FIN → rend 1 + (2 * 3)        ✓
```

### Déroulé sur `1 - 2 - 3`

```
expression(0) : préfixe 1 ; '-' (5) > 0 → droite = expression(5)
                    préfixe 2 ; le second '-' (5) > 5 ? NON → rend 2
                gauche = 1 - 2
              ; le second '-' (5) > 0 → droite = expression(5) → 3
                gauche = (1 - 2) - 3     ✓ associatif à gauche
```

C'est le « **strictement** plus fort » qui donne l'associativité à gauche.

## 2. Le Python à connaître

### Une fonction est un objet : on peut la ranger dans un dictionnaire

```python
def double(x: int) -> int:
    return 2 * x

operations = {"double": double}
operations["double"](21)   # 42
```

Nos tables : « pour tel type de token, voici la fonction qui sait l'analyser ».

### Un décorateur qui **enregistre** une fonction

```python
REGLES: dict[str, Callable[[int], int]] = {}

def regle(nom: str) -> Callable[[Callable[[int], int]], Callable[[int], int]]:
    def enregistrer(f: Callable[[int], int]) -> Callable[[int], int]:
        REGLES[nom] = f     # on range la fonction…
        return f            # …et on la rend intacte
    return enregistrer

@regle("triple")            # équivaut à : triple = regle("triple")(triple)
def triple(x: int) -> int:
    return 3 * x

REGLES["triple"](2)         # 6
```

`@regle("triple")` est un **décorateur paramétré** : `regle("triple")` est appelé d'abord, et renvoie le vrai décorateur `enregistrer`.

### `IntEnum` : des constantes qui se comparent comme des entiers

```python
class Precedence(IntEnum):
    AUCUNE = 0
    SOMME = 5
    PRODUIT = 6

Precedence.PRODUIT > Precedence.SOMME   # True
```

## 3. Pas à pas

### 3.1 Les précédences et les tables

Début de `alto/parser.py` :

```python
"""Le parser d'Alto : Pratt pour les expressions, descente récursive pour le reste."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from enum import IntEnum

from alto.erreurs import ErreurAlto, ErreurLexicale, ErreursMultiples, ErreurSyntaxe
from alto.flux import Flux
from alto.lexer import tokenize
from alto.noeuds import (
    Appel, Binaire, Booleen, Decimal, Entier, Expr, Index, Liste, Rien, Texte, Unaire, Variable,
    # l'étape 6 ajoutera ici : Affectation, Bloc, Branche, Declaration, Ecris, ...
)
from alto.tokens import Token
from alto.tokens import TokenKind as T


class Precedence(IntEnum):
    AUCUNE = 0
    OU = 1
    ET = 2
    NON = 3
    COMPARAISON = 4
    SOMME = 5
    PRODUIT = 6
    PREFIXE = 7
    APPEL = 8


type ReglePrefixe = Callable[[Parser, Token], Expr]
type RegleInfixe = Callable[[Parser, Expr, Token], Expr]

REGLES_PREFIXE: dict[T, ReglePrefixe] = {}
REGLES_INFIXE: dict[T, tuple[Precedence, RegleInfixe]] = {}
```

- Une règle **préfixe** reçoit le parser et le token qui commence l'expression.
- Une règle **infixe** reçoit en plus l'expression **déjà lue à gauche**.

### 3.2 Les décorateurs qui remplissent les tables

```python
def prefixe(*kinds: T) -> Callable[[ReglePrefixe], ReglePrefixe]:
    def enregistrer(regle: ReglePrefixe) -> ReglePrefixe:
        for kind in kinds:
            REGLES_PREFIXE[kind] = regle
        return regle

    return enregistrer
```

À toi : écris `infixe(*kinds, precedence)`, qui range le couple `(precedence, regle)` dans `REGLES_INFIXE`.

### 3.3 La classe `Parser` et ses méthodes d'accès

```python
def _decrire(token: Token) -> str:
    """Comment parler d'un token dans un message d'erreur."""
    if token.kind is T.FIN:
        return "la fin du fichier"
    return f"'{token.lexeme}'"


class Parser:
    def __init__(self, tokens: Iterable[Token]) -> None:
        self.flux = Flux(tokens)
        self.erreurs: list[ErreurAlto] = []   # servira à l'étape 6
        self.dernier: Token | None = None     # le dernier token consommé

    def regarde(self, decalage: int = 0) -> Token:
        token = self.flux.regarde(decalage)
        assert token is not None, "le token FIN n'est jamais consommé"
        return token

    def avance(self) -> Token:
        token = self.regarde()
        if token.kind is not T.FIN:  # on ne consomme jamais FIN
            self.flux.avance()
            self.dernier = token
        return token

    def verifie(self, kind: T) -> bool:
        """Le token courant est-il de ce type ? (sans consommer)"""
        return self.regarde().kind is kind

    def accepte(self, kind: T) -> Token | None:
        """Consomme le token s'il est de ce type, sinon ne fait rien."""
        return self.avance() if self.verifie(kind) else None

    def attend(self, kind: T, contexte: str = "") -> Token:
        """Consomme le token s'il est de ce type, sinon lève une erreur de syntaxe."""
        token = self.regarde()
        if token.kind is kind:
            return self.avance()
        message = f"{kind} attendu{' ' + contexte if contexte else ''}, trouvé {_decrire(token)}"
        raise ErreurSyntaxe(message, token.position)
```

> **Pourquoi ne jamais consommer `FIN` ?** Ainsi `regarde()` rend toujours un token (au pire `FIN`), et on n'a jamais à gérer « plus rien du tout ».

### 3.4 Le cœur : `expression(precedence)`

```python
    def expression(self, precedence: int = Precedence.AUCUNE) -> Expr:
        token = self.regarde()
        regle = REGLES_PREFIXE.get(token.kind)
        if regle is None:
            raise ErreurSyntaxe(f"expression attendue, trouvé {_decrire(token)}", token.position)
        self.avance()
        gauche = regle(self, token)

        while True:
            suivant = self.regarde()
            entree = REGLES_INFIXE.get(suivant.kind)
            if entree is None or entree[0] <= precedence:
                return gauche
            self.avance()
            gauche = entree[1](self, gauche, suivant)
```

C'est **tout** l'algorithme. Le reste, ce sont des petites règles.

> On regarde la règle **avant** de consommer le token (`regarde` puis `avance`) : si c'est une erreur, le token fautif reste là, ce qui aidera la reprise sur erreur à l'étape 6.

### 3.5 Les règles préfixes

Elles se placent **après** la classe `Parser` (en bas du fichier) :

```python
@prefixe(T.ENTIER)
def _entier(p: Parser, t: Token) -> Expr:
    return Entier(int(t.lexeme), t.position)


@prefixe(T.IDENT)
def _variable(p: Parser, t: Token) -> Expr:
    return Variable(t.lexeme, t.position)


@prefixe(T.PAR_G)
def _groupe(p: Parser, t: Token) -> Expr:
    expr = p.expression()          # on repart de zéro à l'intérieur des parenthèses
    p.attend(T.PAR_D, "pour fermer la parenthèse")
    return expr


@prefixe(T.MOINS)
def _moins(p: Parser, t: Token) -> Expr:
    return Unaire("-", p.expression(Precedence.PREFIXE), t.position)
```

À toi : `DECIMAL` (avec `float`), `TEXTE`, `VRAI` et `FAUX` (une seule règle pour les deux : `t.kind is T.VRAI`), `RIEN`, `NON` (avec `Precedence.NON` : c'est ce qui fait que `non a == b` donne `non (a == b)`), et `CROCHET_G` pour une liste `[1, 2, 3]`.

Pour la liste, et plus tard pour les appels, écris d'abord une méthode du parser qui lit `expr, expr, …` jusqu'au token fermant :

```python
    def arguments(self, fermant: T) -> tuple[Expr, ...]:
        elements: list[Expr] = []
        if not self.verifie(fermant):          # la liste peut être vide : []
            elements.append(self.expression())
            while self.accepte(T.VIRGULE):
                elements.append(self.expression())
        self.attend(fermant)
        return tuple(elements)
```

### 3.6 Les opérateurs binaires : une seule fonction pour tous

Les règles de `+`, `-`, `*`… ne diffèrent que par leur précédence. On écrit une fonction qui **fabrique** la règle :

```python
def _binaire(precedence: Precedence, *kinds: T) -> None:
    @infixe(*kinds, precedence=precedence)
    def regle(p: Parser, gauche: Expr, t: Token) -> Expr:
        return Binaire(t.lexeme, gauche, p.expression(precedence), t.position)


_binaire(Precedence.OU, T.OU)
_binaire(Precedence.ET, T.ET)
_binaire(Precedence.COMPARAISON, T.EGAL_EGAL, T.DIFFERENT, T.INF, T.INF_EGAL, T.SUP, T.SUP_EGAL)
_binaire(Precedence.SOMME, T.PLUS, T.MOINS)
_binaire(Precedence.PRODUIT, T.FOIS, T.DIVISE, T.MODULO)
```

`regle` est une **closure** : elle se souvient de `precedence`. L'opérande droit est lu avec `expression(precedence)` : il ne peut contenir que des opérateurs **plus forts** → associativité à gauche.

> `T.MOINS` a donc **deux** règles : préfixe (`-x`) et infixe (`a - b`). C'est normal : la position décide.

### 3.7 Appel et indice : des opérateurs infixes très forts

Dans `f(1)`, la `(` **suit** une expression (`f`) : c'est une règle infixe de `(`, de précédence `APPEL`. Même chose pour `t[i]` avec `[`.

<details>
<summary>▶ Solution</summary>

```python
@infixe(T.PAR_G, precedence=Precedence.APPEL)
def _appel(p: Parser, gauche: Expr, t: Token) -> Expr:
    if not isinstance(gauche, Variable):
        raise ErreurSyntaxe("seule une fonction nommée peut être appelée", t.position)
    return Appel(gauche.nom, p.arguments(T.PAR_D), gauche.pos)


@infixe(T.CROCHET_G, precedence=Precedence.APPEL)
def _index(p: Parser, gauche: Expr, t: Token) -> Expr:
    indice = p.expression()
    p.attend(T.CROCHET_D, "pour fermer l'indice")
    return Index(gauche, indice, t.position)
```

</details>

### 3.8 Le point d'entrée `parse_expression`

```python
def parse_expression(source: str) -> Expr:
    parser = Parser(tokenize(source))
    expr = parser.expression()
    parser.attend(T.FIN, "après l'expression")   # il ne doit rien rester derrière
    return expr
```

Essaie :

```bash
uv run python -c "from alto.parser import parse_expression; print(parse_expression('1 + 2 * 3'))"
```

## 4. Les tests à écrire

`tests/test_etape_05_expressions.py` : compare le résultat à des arbres écrits à la main (c'est là que `compare=False` sur `pos` sert).

```python
import pytest

from alto.erreurs import ErreurSyntaxe, Position
from alto.noeuds import Appel, Binaire, Entier, Expr, Index, Texte, Unaire, Variable
from alto.parser import REGLES_INFIXE, REGLES_PREFIXE, parse_expression
from alto.tokens import TokenKind as T


@pytest.mark.parametrize(
    ("source", "arbre"),
    [
        ("42", Entier(42)),
        ('"salut"', Texte("salut")),
        ("1 + 2 * 3", Binaire("+", Entier(1), Binaire("*", Entier(2), Entier(3)))),
        ("1 - 2 - 3", Binaire("-", Binaire("-", Entier(1), Entier(2)), Entier(3))),
        ("(1 + 2) * 3", Binaire("*", Binaire("+", Entier(1), Entier(2)), Entier(3))),
        ("-a * b", Binaire("*", Unaire("-", Variable("a")), Variable("b"))),
        ("non a == b", Unaire("non", Binaire("==", Variable("a"), Variable("b")))),
        ("f(x)[0]", Index(Appel("f", (Variable("x"),)), Entier(0))),
        ("t[i + 1]", Index(Variable("t"), Binaire("+", Variable("i"), Entier(1)))),
    ],
)
def test_arbre_des_expressions(source: str, arbre: Expr) -> None:
    assert parse_expression(source) == arbre


def test_les_decorateurs_ont_rempli_les_tables() -> None:
    assert T.ENTIER in REGLES_PREFIXE
    assert T.PLUS in REGLES_INFIXE


def test_un_noeud_porte_la_position_de_son_token() -> None:
    expr = parse_expression("1 +\n  2")
    assert isinstance(expr, Binaire)
    assert expr.droite.pos == Position(2, 3)


@pytest.mark.parametrize(
    ("source", "position"),
    [("1 +", Position(1, 4)), ("(1 + 2", Position(1, 7)), ("* 2", Position(1, 1))],
)
def test_erreurs_de_syntaxe(source: str, position: Position) -> None:
    with pytest.raises(ErreurSyntaxe) as erreur:
        parse_expression(source)
    assert erreur.value.position == position
```

À ajouter : chaque littéral (`1.5`, `vrai`, `faux`, `rien`, `[]`, `[1, 2]`), `a ou b et c` (→ `a ou (b et c)`), `non a et b` (→ `(non a) et b`), `- - x`, `f()` sans argument, `f(1)(2)` refusé, `1 2` refusé (« `<fin>` attendu »).

> **Astuce pour comprendre un test qui échoue :** `print(afficher_arbre(parse_expression("…")))` dans un terminal.

## 5. Pièges fréquents

| Symptôme | Cause |
|---|---|
| `1 - 2 - 3` donne `1 - (2 - 3)` | tu as écrit `<` au lieu de `<=` dans `entree[0] <= precedence` |
| `-a * b` donne `-(a * b)` | le `-` unaire lit son opérande avec une précédence trop faible : il faut `PREFIXE` |
| `NameError: Parser` dans `type ReglePrefixe` | `from __future__ import annotations` manquant |
| une règle n'est jamais appelée | la fonction n'a pas le décorateur, ou le fichier n'a pas été importé |

## 6. C'est fini quand…

- [ ] `uv run pytest -k etape_05` est vert ;
- [ ] toutes les lignes du tableau des priorités de `specification.md` sont testées ;
- [ ] tu sais expliquer à l'oral le déroulé de `1 + 2 * 3`.
