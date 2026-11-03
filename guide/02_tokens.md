# Étape 2 : les tokens

**Qui :** Alexandra. **Fichiers :** `alto/erreurs.py`, `alto/tokens.py`, `tests/test_etape_02_tokens.py`. **Énoncé :** `langage/etapes/02_tokens.md`.

> **En une phrase :** décrire en Python la liste de tous les « mots » possibles d'Alto, et un objet `Token` qui représente un mot trouvé dans le source, avec sa position.

⚡ **Priorité équipe :** `tokens.py` et `erreurs.py` sont utilisés par tout le monde. Pousse une première version (même sans tests) **le jour 1** pour débloquer les autres.

## 1. Comprendre

Le lexer (étape 3) va lire `var x = 3;` et produire une liste d'objets :

```
Token(VAR, 'var', 1:1)
Token(IDENT, 'x', 1:5)
Token(EGAL, '=', 1:7)
Token(ENTIER, '3', 1:9)
Token(POINT_VIRGULE, ';', 1:10)
Token(FIN, '', 1:11)
```

Chaque token a trois informations :

| Champ | Exemple | Rôle |
|---|---|---|
| `kind` (le type) | `TokenKind.IDENT` | quelle sorte de mot c'est |
| `lexeme` | `'x'` | le texte exact |
| `position` | ligne 1, colonne 5 | où il est, pour les messages d'erreur |

Cette étape ne lit **pas encore** le texte : elle prépare seulement les « boîtes ».

## 2. Le Python à connaître

### `Enum` : une liste fermée de valeurs

```python
from enum import Enum

class Couleur(Enum):
    ROUGE = "rouge"
    VERT = "vert"

Couleur.ROUGE.name    # 'ROUGE'
Couleur.ROUGE.value   # 'rouge'
Couleur("vert")       # Couleur.VERT
for c in Couleur:     # on peut parcourir toutes les valeurs
    print(c)
Couleur.ROUGE is Couleur.ROUGE   # True : on compare avec `is`
```

### `@dataclass(frozen=True)` : un objet de données immuable

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Point:
    x: int
    y: int

p = Point(1, 2)        # __init__ est écrit automatiquement
p == Point(1, 2)       # True : __eq__ est écrit automatiquement
p.x = 5                # ERREUR : dataclasses.FrozenInstanceError
{p}                    # possible : un objet gelé est « hachable »
```

`slots=True` rend l'objet plus léger en mémoire (on va créer des milliers de tokens).

### `__repr__` et `__str__`

- `__repr__` : ce que tu vois dans la console et dans pytest quand un test échoue. On le veut **court**.
- `__str__` : ce qu'affiche `print(x)` ou `f"{x}"`. On s'en sert dans les messages d'erreur.

## 3. Pas à pas

### 3.1 `Position` (dans `alto/erreurs.py`)

```python
"""Positions dans le source et hiérarchie des erreurs d'Alto."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Position:
    ligne: int
    colonne: int

    def __str__(self) -> str:
        return f"ligne {self.ligne}, colonne {self.colonne}"

    def decalee(self, n: int) -> Position:
        """La même position, n colonnes plus loin (servira à l'étape 6)."""
        return Position(self.ligne, self.colonne + n)


#: Position par défaut des nœuds construits à la main dans les tests (étape 4).
SANS_POSITION = Position(0, 0)
```

Les lignes et colonnes commencent à **1**, comme dans un éditeur.

> **`from __future__ import annotations`** permet d'écrire `-> Position` à l'intérieur de la classe `Position` elle-même. Mets-le en tête de chaque module.

Ajoute tout de suite, dans le même fichier, la hiérarchie des erreurs (les autres en ont besoin dès le jour 1, même si elle ne sert vraiment qu'à l'étape 3) :

```python
class ErreurAlto(Exception):
    """La racine de toutes nos erreurs."""

    genre = "erreur"

    def __init__(self, message: str, position: Position | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.position = position

    def __str__(self) -> str:
        if self.position is None:
            return f"{self.genre} : {self.message}"
        return f"{self.position} : {self.genre} : {self.message}"


class ErreurLexicale(ErreurAlto):
    genre = "erreur lexicale"


class ErreurSyntaxe(ErreurAlto):
    genre = "erreur de syntaxe"


class ErreurSemantique(ErreurAlto):
    genre = "erreur sémantique"


class ErreurExecution(ErreurAlto):
    genre = "erreur d'exécution"


class ErreursMultiples(ErreurAlto):
    """Regroupe plusieurs erreurs (parser et analyse sémantique)."""

    def __init__(self, erreurs: list[ErreurAlto]) -> None:
        super().__init__(f"{len(erreurs)} erreur(s)")
        self.erreurs = erreurs
```

Chaque sous-classe ne change que son `genre`, qui apparaîtra dans les messages : `p.alt:3:7 : erreur lexicale : texte non terminé`.

### 3.2 `TokenKind` (dans `alto/tokens.py`)

**L'astuce :** la valeur de chaque membre est le **lexème lui-même** pour les mots-clés et les symboles (`VAR = "var"`, `PLUS = "+"`), et une description **entre chevrons** pour les autres (`IDENT = "<identifiant>"`). On pourra ainsi construire les tables du lexer automatiquement.

Voici la liste complète pour Alto (à valider en réunion 0) :

```python
"""Les types de token d'Alto et la classe Token."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from alto.erreurs import Position


class TokenKind(Enum):
    # Littéraux et identifiants : valeur entre chevrons
    ENTIER = "<entier>"
    DECIMAL = "<décimal>"
    TEXTE = "<texte>"
    IDENT = "<identifiant>"
    # Mots-clés
    VAR = "var"
    FONCTION = "fonction"
    RENDS = "rends"
    SI = "si"
    SINON = "sinon"
    TANTQUE = "tantque"
    POUR = "pour"
    DE = "de"
    JUSQUA = "jusqua"
    ECRIS = "ecris"
    VRAI = "vrai"
    FAUX = "faux"
    RIEN = "rien"
    ET = "et"
    OU = "ou"
    NON = "non"
    # Symboles
    PAR_G = "("
    PAR_D = ")"
    ACC_G = "{"
    ACC_D = "}"
    CROCHET_G = "["
    CROCHET_D = "]"
    VIRGULE = ","
    POINT_VIRGULE = ";"
    EGAL = "="
    EGAL_EGAL = "=="
    DIFFERENT = "!="
    INF = "<"
    INF_EGAL = "<="
    SUP = ">"
    SUP_EGAL = ">="
    PLUS = "+"
    MOINS = "-"
    FOIS = "*"
    DIVISE = "/"
    MODULO = "%"
    # Fin du source
    FIN = "<fin>"
```

### 3.3 Distinguer les tokens « fixes » des autres

Un token est **fixe** si son lexème est toujours le même (mot-clé ou symbole). Ajoute dans la classe :

```python
    @property
    def est_fixe(self) -> bool:
        """Vrai pour un mot-clé ou un symbole."""
        v = self.value
        return not (len(v) > 2 and v.startswith("<") and v.endswith(">"))

    def __str__(self) -> str:
        return f"'{self.value}'" if self.est_fixe else self.value
```

Résultat : `str(TokenKind.POINT_VIRGULE)` donne `';'`, et `str(TokenKind.IDENT)` donne `<identifiant>`. Le parser écrira ainsi `';' attendu, trouvé '}'`.

> ⚠️ **Piège :** on ne peut pas tester seulement `v.startswith("<")`, car le symbole `<` (et `<=`) commence aussi par `<` ! C'est pour ça qu'on vérifie aussi la longueur et le `>` final.

### 3.4 Les deux tables pour le lexer

Après la classe (pas dedans !), on construit les tables **à partir de l'`Enum`** :

```python
#: Les mots réservés, indexés par leur orthographe : {"var": TokenKind.VAR, ...}
MOTS_CLES: dict[str, TokenKind] = {
    k.value: k for k in TokenKind if k.est_fixe and k.value.isalpha()
}

#: Les symboles, du plus long au plus court : [("==", EGAL_EGAL), ..., ("=", EGAL), ...]
SYMBOLES: list[tuple[str, TokenKind]] = sorted(
    ((k.value, k) for k in TokenKind if k.est_fixe and not k.value.isalpha()),
    key=lambda paire: -len(paire[0]),
)
```

**Pourquoi trier du plus long au plus court ?** Le lexer essaiera les symboles dans cet ordre. Sur `x == 1`, s'il essayait `=` en premier, il verrait deux `=` au lieu d'un `==`.

### 3.5 La classe `Token`

```python
@dataclass(frozen=True, slots=True)
class Token:
    kind: TokenKind
    lexeme: str
    position: Position

    def __repr__(self) -> str:
        p = self.position
        return f"Token({self.kind.name}, {self.lexeme!r}, {p.ligne}:{p.colonne})"
```

Essaie dans un terminal :

```bash
uv run python -c "from alto.tokens import *; from alto.erreurs import Position; print(repr(Token(TokenKind.VAR, 'var', Position(1, 1))))"
```

Tu dois voir `Token(VAR, 'var', 1:1)`.

## 4. Les tests à écrire

Crée `tests/test_etape_02_tokens.py`. Voici une base qui couvre la section *Validation* de l'énoncé ; complète-la.

```python
import dataclasses

import pytest

from alto.erreurs import Position
from alto.tokens import MOTS_CLES, SYMBOLES, Token, TokenKind


def test_un_token_est_immuable() -> None:
    token = Token(TokenKind.VAR, "var", Position(1, 1))
    with pytest.raises(dataclasses.FrozenInstanceError):
        token.lexeme = "autre"  # type: ignore[misc]


def test_un_token_est_hachable() -> None:
    token = Token(TokenKind.VAR, "var", Position(1, 1))
    assert token in {token}


def test_deux_tokens_identiques_sont_egaux() -> None:
    assert Token(TokenKind.IDENT, "x", Position(2, 5)) == Token(TokenKind.IDENT, "x", Position(2, 5))


def test_repr_tient_sur_une_ligne() -> None:
    assert repr(Token(TokenKind.VAR, "var", Position(1, 1))) == "Token(VAR, 'var', 1:1)"


def test_mots_cles_ne_contient_que_des_mots() -> None:
    assert MOTS_CLES["var"] is TokenKind.VAR
    assert MOTS_CLES["jusqua"] is TokenKind.JUSQUA
    assert all(mot.isalpha() for mot in MOTS_CLES)


@pytest.mark.parametrize(("court", "long"), [("=", "=="), ("<", "<="), (">", ">=")])
def test_un_symbole_long_passe_avant_son_prefixe(court: str, long: str) -> None:
    ordre = [symbole for symbole, _ in SYMBOLES]
    assert ordre.index(long) < ordre.index(court)


@pytest.mark.parametrize(
    ("kind", "texte"),
    [(TokenKind.POINT_VIRGULE, "';'"), (TokenKind.IDENT, "<identifiant>"), (TokenKind.INF, "'<'")],
)
def test_str_d_un_type_de_token(kind: TokenKind, texte: str) -> None:
    assert str(kind) == texte
```

À ajouter toi-même : `SYMBOLES` ne contient aucun mot-clé, `MOTS_CLES` contient **tous** les mots-clés de la spec (compte-les), `Position.__str__`, `Position.decalee`.

```bash
uv run pytest -k etape_02
```

## 5. Pièges fréquents

| Symptôme | Cause |
|---|---|
| `NameError: name 'TokenKind' is not defined` dans `MOTS_CLES` | tu as mis la table **dans** la classe ; elle doit être **après** (bonus de l'énoncé : explique pourquoi) |
| `<` est considéré comme « non fixe » | voir le piège du 3.3 |
| le `repr` affiche `TokenKind.VAR` au lieu de `VAR` | utilise `self.kind.name` |

## 6. C'est fini quand…

- [ ] `uv run pytest -k etape_02` est vert ;
- [ ] tous les mots-clés et symboles de `specification.md` sont dans `TokenKind` ;
- [ ] la PR est relue et fusionnée → **préviens Fatoumata et Luca** qu'ils peuvent importer `Token` et `Position`.
