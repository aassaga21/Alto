# Tokens, erreurs, flux et lexer (étapes 2 et 3)

**Responsable :** Alexandra. **Statut :** terminé, testé (77 tests), `mypy --strict` et `ruff` sans erreur.

Cette partie est le **premier maillon** de la chaîne : elle transforme le texte d'un programme Alto en une suite de tokens, et fournit les briques communes à tout le monde (positions, erreurs, flux).

```
texte source ──tokenize──▶ tokens ──Flux──▶ parser (Fatoumata) ──▶ …
```

## Les fichiers

| Fichier | Contenu | Qui s'en sert |
|---|---|---|
| [`alto/erreurs.py`](../alto/erreurs.py) | `Position`, `SANS_POSITION`, la hiérarchie d'erreurs, `formater` | **tout le monde** |
| [`alto/tokens.py`](../alto/tokens.py) | `TokenKind`, `Token`, `MOTS_CLES`, `SYMBOLES` | le lexer, le parser |
| [`alto/flux.py`](../alto/flux.py) | `Flux[T]` : un flux avec regard en avant | le parser |
| [`alto/lexer.py`](../alto/lexer.py) | `tokenize(source)` | le parser, la CLI |
| [`tests/test_etape_02_tokens.py`](../tests/test_etape_02_tokens.py) | 25 tests | |
| [`tests/test_etape_03_lexer.py`](../tests/test_etape_03_lexer.py) | 52 tests | |

## Utiliser cette partie

### Découper un programme en tokens

```python
from alto.lexer import tokenize

for token in tokenize("var x = 1.5;"):
    print(token)
```

```
Token(VAR, 'var', 1:1)
Token(IDENT, 'x', 1:5)
Token(EGAL, '=', 1:7)
Token(DECIMAL, '1.5', 1:9)
Token(POINT_VIRGULE, ';', 1:12)
Token(FIN, '', 1:13)
```

- `tokenize` est un **générateur** : il produit les tokens un par un, à la demande. Une erreur lexicale n'est levée qu'au moment où le lexer arrive sur le caractère fautif.
- Le dernier token est **toujours** `FIN`.
- Le `lexeme` d'un nombre est son texte (`"007"`, `"3.14"`) : la conversion en `int` ou `float` est à faire par le parser.
- Le `lexeme` d'un texte est **déjà décodé** : les guillemets sont retirés et `\n` est devenu un vrai saut de ligne.

### Un token

```python
from alto.erreurs import Position
from alto.tokens import Token, TokenKind

token = Token(TokenKind.IDENT, "x", Position(2, 5))
token.kind       # TokenKind.IDENT
token.lexeme     # 'x'
token.position   # Position(ligne=2, colonne=5)
```

Un `Token` est **immuable** (`frozen=True`) et **hachable**. Dans les tests, on peut en construire à la main, sans passer par le lexer.

`str(kind)` donne un texte prêt pour les messages d'erreur : `str(TokenKind.POINT_VIRGULE)` vaut `';'`, `str(TokenKind.IDENT)` vaut `<identifiant>`. Le parser peut donc écrire `f"{attendu} attendu, trouvé {trouve}"`.

### Les noms des tokens (le contrat)

Ces noms sont utilisés par le parser : **on ne les renomme pas sans prévenir toute l'équipe.**

| Catégorie | Noms |
|---|---|
| Littéraux | `ENTIER` `DECIMAL` `TEXTE` `IDENT` |
| Mots-clés | `VAR` `FONCTION` `RENDS` `SI` `SINON` `TANTQUE` `POUR` `DE` `JUSQUA` `ECRIS` `VRAI` `FAUX` `RIEN` `ET` `OU` `NON` |
| Délimiteurs | `PAR_G` `(` · `PAR_D` `)` · `ACC_G` `{` · `ACC_D` `}` · `CROCHET_G` `[` · `CROCHET_D` `]` · `VIRGULE` `,` · `POINT_VIRGULE` `;` |
| Opérateurs | `EGAL` `=` · `EGAL_EGAL` `==` · `DIFFERENT` `!=` · `INF` `<` · `INF_EGAL` `<=` · `SUP` `>` · `SUP_EGAL` `>=` · `PLUS` `+` · `MOINS` `-` · `FOIS` `*` · `DIVISE` `/` · `MODULO` `%` |
| Fin | `FIN` |

Astuce : `from alto.tokens import TokenKind as T` permet d'écrire `T.VAR` au lieu de `TokenKind.VAR`.

### Le flux (pour le parser)

```python
from alto.flux import Flux
from alto.lexer import tokenize

flux = Flux(tokenize("si x { }"))
flux.regarde()     # Token(SI, …)    : le token courant, SANS le consommer
flux.regarde(1)    # Token(IDENT, …) : le suivant, sans rien consommer
flux.avance()      # Token(SI, …)    : consomme et renvoie le token courant
flux.consommes     # 1
```

- `regarde(decalage)` renvoie `None` au-delà de la fin.
- `avance()` lève `IndexError` si le flux est vide. Avec `tokenize`, ça n'arrive pas tant qu'on ne consomme pas le token `FIN`.
- Le flux est générique (`Flux[T]`) : il marche avec n'importe quel itérable, ce qui est pratique dans les tests (`Flux([1, 2, 3])`).

### Les erreurs

```
ErreurAlto
├── ErreurLexicale      genre = "erreur lexicale"      (lexer)
├── ErreurSyntaxe       genre = "erreur de syntaxe"    (parser)
├── ErreurSemantique    genre = "erreur sémantique"    (analyse)
├── ErreurExecution     genre = "erreur d'exécution"   (exécution)
└── ErreursMultiples    regroupe plusieurs erreurs dans .erreurs
```

Chaque erreur a un `message` et une `position` (facultative) :

```python
from alto.erreurs import ErreurSyntaxe, Position

raise ErreurSyntaxe("';' attendu", Position(3, 12))
```

Pour ajouter une nouvelle classe d'erreur (par exemple `ErreurType` pour l'extension 12), faites une petite PR dédiée sur `erreurs.py` et prévenez-moi.

`SANS_POSITION` (`Position(0, 0)`) sert de position par défaut pour les nœuds construits à la main dans les tests.

### Afficher une erreur à l'utilisateur

```python
from alto.erreurs import ErreurAlto, formater

try:
    ...
except ErreurAlto as erreur:
    print(formater(erreur, source, "programme.alt"))
```

```
programme.alt:1:9 : erreur lexicale : caractère inattendu : '@'
    var x = @;
            ^
```

- Une `ErreursMultiples` affiche toutes ses erreurs, l'une après l'autre.
- Une position avec `colonne == 0` affiche `fichier:ligne` sans `^` (prévu pour les erreurs d'exécution, étape 9).

## Ce que le lexer refuse

| Source | Message | Position signalée |
|---|---|---|
| `var x = 1 @ 2;` | `caractère inattendu : '@'` | le caractère |
| `ecris "abc` | `texte non terminé` | le `"` ouvrant |
| `ecris "a\q";` | `échappement invalide : \q` | le `\` |
| `var _x = 1;` | `un identifiant ne peut pas commencer par '_'` | le début du nom |
| `1.` ou `.5` | `caractère inattendu : '.'` | le `.` |

Les règles complètes sont dans la section **Lexique** de [`specification.md`](../specification.md).

Écart par rapport au guide : dans un identifiant, seuls les chiffres de `0` à `9` sont acceptés (le guide utilisait `isalnum()`). Sinon, un nom comme `x²` serait accepté par Alto puis refusé par Python au moment de l'exécution.

## Lancer les tests

```powershell
uv run pytest -k "etape_02 or etape_03"   # seulement cette partie
uv run mypy alto                          # typage strict
uv run ruff check alto tests              # style
uv run ruff format alto tests             # mise en forme
```

⚠️ Pour la mise en forme, utilisez `ruff format alto tests` et **pas** `ruff format .` : cette dernière reformate aussi le code Python à l'intérieur des guides Markdown.

## La suite

- [ ] **Étape 9** (CLI et REPL) : `compilateur.py`, `cli.py`, `repl.py`, `__main__.py`. À commencer quand le parser, l'analyse et le générateur marchent. Voir [`guide/09_cli_repl.md`](../guide/09_cli_repl.md).
