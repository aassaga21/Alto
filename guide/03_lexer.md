# Étape 3 : le lexer

**Qui :** Alexandra. **Fichiers :** `alto/lexer.py`, `alto/flux.py`, `alto/erreurs.py` (ajout de `formater`), `tests/test_etape_03_lexer.py`. **Énoncé :** `langage/etapes/03_lexer.md`.

> **En une phrase :** lire le texte caractère par caractère et produire les tokens un par un, en signalant précisément les fautes de frappe.

## 1. Comprendre

Imagine que tu lis `var total = 12;` avec le doigt sous chaque caractère :

```
v a r   t o t a l   =   1 2 ;
▲
```

- je vois une **lettre** → je lis tant que ce sont des lettres/chiffres/`_` → `var` → c'est dans `MOTS_CLES` → token `VAR` ;
- je vois un **espace** → je l'ignore ;
- je vois une **lettre** → `total` → pas un mot-clé → token `IDENT` ;
- je vois `=` → je cherche le plus long symbole qui commence ici → `=` → token `EGAL` ;
- je vois un **chiffre** → je lis tant que ce sont des chiffres → `12` → token `ENTIER` ;
- `;` → token `POINT_VIRGULE` ;
- fin du texte → token `FIN`.

C'est exactement la structure du code : une boucle `while`, et un `if` par sorte de caractère.

## 2. Le Python à connaître

### Les générateurs (`yield`)

Une fonction qui contient `yield` ne s'exécute pas d'un coup : elle **produit ses valeurs une par une, à la demande**.

```python
def compter(n: int) -> Iterator[int]:
    i = 1
    while i <= n:
        yield i        # « voici une valeur ; je m'arrête ici jusqu'à la prochaine demande »
        i += 1

g = compter(3)    # rien ne s'exécute encore !
next(g)           # 1
next(g)           # 2
list(compter(3))  # [1, 2, 3]
```

Notre lexer sera un générateur : `tokenize(source)` rend les tokens au fur et à mesure. Conséquence : sur `1 + 2 @`, les trois premiers tokens sortent **avant** que l'erreur sur `@` soit levée. Il faut le tester.

### Lever une exception avec une position

```python
raise ErreurLexicale("texte non terminé", Position(3, 7))
```

### `for … else`

```python
for symbole, kind in SYMBOLES:
    if source.startswith(symbole, i):
        ...
        break
else:
    # exécuté seulement si la boucle n'a PAS fait `break`
    raise ErreurLexicale(...)
```

## 3. Pas à pas

### 3.1 Le squelette

```python
"""Le lexer d'Alto : texte source -> tokens."""

from collections.abc import Iterator

from alto.erreurs import ErreurLexicale, Position
from alto.tokens import MOTS_CLES, SYMBOLES, Token
from alto.tokens import TokenKind as T

ECHAPPEMENTS = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}


def _est_chiffre(c: str) -> bool:
    return "0" <= c <= "9"


def tokenize(source: str) -> Iterator[Token]:
    """Découpe `source` en tokens, le dernier étant toujours `FIN`."""
    i = 0              # l'indice du caractère courant
    ligne = 1          # la ligne courante
    debut_ligne = 0    # l'indice du premier caractère de la ligne courante
    n = len(source)

    while i < n:
        c = source[i]
        pos = Position(ligne, i - debut_ligne + 1)

        # ... une branche par sorte de caractère (voir ci-dessous)

    yield Token(T.FIN, "", Position(ligne, i - debut_ligne + 1))
```

**La colonne** vaut `i - debut_ligne + 1`. Quand on rencontre un `\n`, on augmente `ligne` et on note `debut_ligne = i + 1`.

> `TokenKind as T` : un alias court, pour écrire `T.VAR` au lieu de `TokenKind.VAR`.

### 3.2 Les blancs, sauts de ligne et commentaires

```python
        if c == "\n":
            i += 1
            ligne += 1
            debut_ligne = i
            continue

        if c in " \t\r":
            i += 1
            continue

        if c == "#":
            while i < n and source[i] != "\n":
                i += 1
            continue
```

### 3.3 Les nombres

```python
        if _est_chiffre(c):
            debut = i
            while i < n and _est_chiffre(source[i]):
                i += 1
            # un point SUIVI d'un chiffre : c'est un décimal
            if i + 1 < n and source[i] == "." and _est_chiffre(source[i + 1]):
                i += 1
                while i < n and _est_chiffre(source[i]):
                    i += 1
                yield Token(T.DECIMAL, source[debut:i], pos)
            else:
                yield Token(T.ENTIER, source[debut:i], pos)
            continue
```

> **Pourquoi `_est_chiffre` et pas `c.isdigit()` ?** Parce que `"²".isdigit()` vaut `True` ! `int("²")` planterait ensuite.

### 3.4 Les identifiants et mots-clés

```python
        if c.isalpha() or c == "_":
            debut = i
            while i < n and (source[i].isalnum() or source[i] == "_"):
                i += 1
            mot = source[debut:i]
            if mot.startswith("_"):
                raise ErreurLexicale("un identifiant ne peut pas commencer par '_'", pos)
            yield Token(MOTS_CLES.get(mot, T.IDENT), mot, pos)
            continue
```

On lit **le mot entier d'abord**, puis on regarde si c'est un mot-clé. Ainsi `sinon_si` est un identifiant, pas `sinon` suivi de `_si`. On interdit `_` au début : ces noms seront réservés au code Python généré (étape 8).

### 3.5 Les textes (à toi de jouer)

Un texte commence par `"`. Il faut :

1. avancer après le `"` ouvrant ;
2. accumuler les caractères dans une liste jusqu'au `"` fermant ;
3. sur un `\`, regarder le caractère suivant : s'il est dans `ECHAPPEMENTS`, ajouter la valeur décodée (le `\n` écrit dans le source devient un **vrai** saut de ligne) ; sinon, erreur « échappement invalide » **à la position du `\`** ;
4. si on arrive à la fin du source ou à un saut de ligne sans `"` fermant : erreur « texte non terminé » **à la position du `"` ouvrant** ;
5. produire `Token(T.TEXTE, texte_decode, pos)`.

<details>
<summary>▶ Solution</summary>

```python
        if c == '"':
            i += 1
            morceaux: list[str] = []
            while True:
                if i >= n or source[i] == "\n":
                    raise ErreurLexicale("texte non terminé", pos)
                ch = source[i]
                if ch == '"':
                    i += 1
                    break
                if ch == "\\":
                    suivant = source[i + 1] if i + 1 < n else ""
                    if suivant not in ECHAPPEMENTS:
                        raise ErreurLexicale(
                            f"échappement invalide : \\{suivant}",
                            Position(ligne, i - debut_ligne + 1),
                        )
                    morceaux.append(ECHAPPEMENTS[suivant])
                    i += 2
                    continue
                morceaux.append(ch)
                i += 1
            yield Token(T.TEXTE, "".join(morceaux), pos)
            continue
```

</details>

### 3.6 Les symboles, et le caractère inconnu

```python
        for symbole, kind in SYMBOLES:
            if source.startswith(symbole, i):
                yield Token(kind, symbole, pos)
                i += len(symbole)
                break
        else:
            raise ErreurLexicale(f"caractère inattendu : {c!r}", pos)
```

C'est la dernière branche de la boucle : si rien d'autre n'a marché, on essaie les symboles, du plus long au plus court.

**Teste maintenant :**

```bash
uv run python -c "from alto.lexer import tokenize; print(*tokenize('var x = 1.5;'), sep='\n')"
```

```
Token(VAR, 'var', 1:1)
Token(IDENT, 'x', 1:5)
Token(EGAL, '=', 1:7)
Token(DECIMAL, '1.5', 1:9)
Token(POINT_VIRGULE, ';', 1:12)
Token(FIN, '', 1:13)
```

### 3.7 Le flux avec regard en avant (`alto/flux.py`)

Le parser aura besoin de **regarder le token suivant sans le consommer** (« est-ce qu'il y a un `sinon` après ce bloc ? »). Un générateur ne sait pas faire ça : on l'enveloppe dans un objet avec un **tampon**.

```
source (générateur) ──next()──▶ tampon [tok1, tok2] ──avance()──▶ tok1
                                         ▲
                                   regarde(1) = tok2 (sans rien retirer)
```

`class Flux[T]` veut dire « un flux de n'importe quel type `T` » (des tokens, des entiers…). C'est la syntaxe des génériques de Python 3.12.

```python
"""Un flux avec regard en avant, générique."""

from collections import deque
from collections.abc import Iterable, Iterator


class Flux[T]:
    def __init__(self, source: Iterable[T]) -> None:
        self._source: Iterator[T] = iter(source)
        self._tampon: deque[T] = deque()
        self.consommes = 0  # nombre d'éléments consommés (servira à l'étape 6)

    def regarde(self, decalage: int = 0) -> T | None:
        """L'élément situé `decalage` crans plus loin, sans le consommer."""
        while len(self._tampon) <= decalage:
            try:
                self._tampon.append(next(self._source))
            except StopIteration:
                return None
        return self._tampon[decalage]

    def avance(self) -> T:
        """Consomme et renvoie l'élément courant."""
        if self.regarde() is None:
            raise IndexError("le flux est vide")
        self.consommes += 1
        return self._tampon.popleft()
```

Le flux ne tire de la source **que ce qui est nécessaire** : `regarde(1)` tire au plus deux éléments.

### 3.8 `formater` : un message d'erreur lisible (`alto/erreurs.py`)

On veut afficher :

```
p.alt:1:9 : erreur lexicale : caractère inattendu : '@'
    var x = @;
            ^
```

```python
def formater(erreur: ErreurAlto, source: str, fichier: str = "<source>") -> str:
    if isinstance(erreur, ErreursMultiples):
        return "\n".join(formater(e, source, fichier) for e in erreur.erreurs)
    if erreur.position is None:
        return f"{fichier} : {erreur.genre} : {erreur.message}"
    pos = erreur.position
    lignes = source.splitlines()
    texte = lignes[pos.ligne - 1] if 0 < pos.ligne <= len(lignes) else ""
    if pos.colonne == 0:  # colonne inconnue (erreur d'exécution, étape 9) : pas de ^
        return f"{fichier}:{pos.ligne} : {erreur.genre} : {erreur.message}\n    {texte}"
    return (
        f"{fichier}:{pos.ligne}:{pos.colonne} : {erreur.genre} : {erreur.message}\n"
        f"    {texte}\n"
        f"    {' ' * (pos.colonne - 1)}^"
    )
```

Le `^` est précédé de `colonne - 1` espaces (plus les 4 de l'indentation, comme la ligne au-dessus).

## 4. Les tests à écrire

`tests/test_etape_03_lexer.py` :

```python
from collections.abc import Iterator

import pytest

from alto.erreurs import ErreurLexicale, Position, formater
from alto.flux import Flux
from alto.lexer import tokenize
from alto.tokens import TokenKind as T


def kinds(source: str) -> list[T]:
    """Petit utilitaire : juste les types des tokens."""
    return [token.kind for token in tokenize(source)]


def test_une_declaration_donne_les_bons_tokens() -> None:
    assert kinds("var x = 3;") == [T.VAR, T.IDENT, T.EGAL, T.ENTIER, T.POINT_VIRGULE, T.FIN]


def test_positions_apres_un_saut_de_ligne() -> None:
    tokens = list(tokenize("var x = 1;\n  ecris x;"))
    assert tokens[5].position == Position(2, 3)  # ecris
    assert tokens[6].position == Position(2, 9)  # x


@pytest.mark.parametrize(
    ("source", "attendu"),
    [("==", T.EGAL_EGAL), ("=", T.EGAL), ("<=", T.INF_EGAL), ("<", T.INF), ("!=", T.DIFFERENT)],
)
def test_symboles(source: str, attendu: T) -> None:
    assert kinds(source) == [attendu, T.FIN]


def test_un_decimal_et_un_entier() -> None:
    assert kinds("1.5 2") == [T.DECIMAL, T.ENTIER, T.FIN]


def test_un_texte_est_decode() -> None:
    token = next(tokenize(r'"a\nb\"c"'))
    assert token.kind is T.TEXTE
    assert token.lexeme == 'a\nb"c'


def test_les_commentaires_sont_ignores() -> None:
    assert kinds("# rien à voir\nvar") == [T.VAR, T.FIN]


def test_un_mot_cle_n_est_pas_un_prefixe_d_identifiant() -> None:
    assert kinds("sinon_si variable") == [T.IDENT, T.IDENT, T.FIN]


@pytest.mark.parametrize(
    ("source", "message", "position"),
    [
        ("var x = 1 @ 2;", "caractère inattendu", Position(1, 11)),
        ('ecris "abc', "texte non terminé", Position(1, 7)),
        (r'ecris "a\q";', "échappement invalide", Position(1, 9)),
        ("var _x = 1;", "ne peut pas commencer par '_'", Position(1, 5)),
    ],
)
def test_erreurs_lexicales(source: str, message: str, position: Position) -> None:
    with pytest.raises(ErreurLexicale) as erreur:
        list(tokenize(source))
    assert message in erreur.value.message
    assert erreur.value.position == position


def test_tokenize_est_paresseux() -> None:
    tokens = tokenize("1 + 2 @")
    assert [next(tokens).kind for _ in range(3)] == [T.ENTIER, T.PLUS, T.ENTIER]
    with pytest.raises(ErreurLexicale):
        next(tokens)


def test_flux_regarde_ne_consomme_pas() -> None:
    flux = Flux([1, 2, 3])
    assert flux.regarde() == 1
    assert flux.regarde(1) == 2
    assert flux.avance() == 1
    assert flux.regarde() == 2


def test_flux_ne_tire_que_le_necessaire() -> None:
    demandes: list[int] = []

    def source() -> Iterator[int]:
        for i in range(10):
            demandes.append(i)
            yield i

    flux = Flux(source())
    flux.regarde(1)
    assert demandes == [0, 1]


def test_formater_place_le_chapeau_sous_la_colonne() -> None:
    erreur = ErreurLexicale("caractère inattendu : '@'", Position(1, 9))
    assert formater(erreur, "var x = @;", "p.alt") == (
        "p.alt:1:9 : erreur lexicale : caractère inattendu : '@'\n"
        "    var x = @;\n"
        "            ^"
    )
```

> Le `r` devant `r'"a\nb"'` fait que Python garde `\n` comme **deux caractères** (`\` et `n`), exactement comme dans un fichier `.alt`.

À ajouter : `1..2` ou `1.` (que se passe-t-il ?), un identifiant accentué (`déjà`) qui ne décale pas les colonnes, un texte vide `""`, et un test qui tokenise chacun des fichiers de `exemples/` sans erreur.

## 5. Pièges fréquents

| Symptôme | Cause |
|---|---|
| boucle infinie | une branche oublie d'avancer `i` avant `continue` |
| colonnes fausses à la ligne 2 | `debut_ligne` mal mis à jour après `\n` |
| `==` lu comme deux `=` | `SYMBOLES` pas trié du plus long au plus court |
| le dernier token n'est pas `FIN` | le `yield` de `FIN` doit être **après** la boucle `while` |

## 6. C'est fini quand…

- [ ] `uv run pytest -k etape_03` est vert ;
- [ ] les 5 exemples se découpent en tokens sans erreur ;
- [ ] `Flux` est fusionné sur `main` → **préviens Fatoumata** (le parser en a besoin).
