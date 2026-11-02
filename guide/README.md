# Guide pas à pas : construire Alto quand on débute

Ce guide accompagne les énoncés du cours (dossier `langage/etapes/` du dépôt du cours). Les énoncés disent **quoi** faire ; ce guide explique **comment**, avec des mots simples, des schémas, du code Alto déjà réfléchi et les tests à écrire.

> **Comment s'en servir.** Pour ton étape : lis d'abord la partie « Comprendre », puis fais la section « Pas à pas » dans l'ordre, en lançant les tests à chaque fois. Quand une solution est cachée dans un bloc ▶ **Solution**, essaie d'abord tout seul ou toute seule (10 à 15 minutes), puis ouvre-la. Recopier sans comprendre ne t'aidera pas à l'oral.

## Le projet en une image

On écrit un programme Python (le **compilateur**) qui lit un programme Alto et le transforme en programme Python, puis l'exécute.

```
  fichier.alt                                                              ce qui s'affiche
 ┌──────────────┐   ┌───────┐  tokens  ┌────────┐  arbre  ┌───────────┐  arbre  ┌────────────┐  code    ┌──────┐
 │ var x = 3;   │──▶│ LEXER │────────▶│ PARSER │────────▶│ SÉMANTIQUE│────────▶│ GÉNÉRATEUR │─Python──▶│ exec │──▶ 3
 │ ecris x;     │   └───────┘         └────────┘         └───────────┘ vérifié └────────────┘          └──────┘
 └──────────────┘   étapes 2-3          étapes 4-6          étape 7                étape 8
```

Chaque boîte est un module Python, et **chaque boîte se teste toute seule**. C'est ce qui permet de travailler à quatre en même temps.

### La même instruction, à chaque étage

Prenons `ecris 1 + 2 * x;` :

| Étage | Ce qu'on obtient |
|---|---|
| **Texte source** | `ecris 1 + 2 * x;` |
| **Tokens** (lexer) | `ECRIS` `ENTIER(1)` `PLUS` `ENTIER(2)` `FOIS` `IDENT(x)` `POINT_VIRGULE` `FIN` |
| **Arbre** (parser) | `Ecris(valeurs=(Binaire('+', Entier(1), Binaire('*', Entier(2), Variable('x'))),))` |
| **Vérification** (sémantique) | « `x` est-il déclaré ? » Sinon : `erreur sémantique : 'x' n'est pas déclaré` |
| **Python** (générateur) | `_ecris(1 + (2 * x))` |

## Sommaire

| Fichier | Étape | Qui | Durée indicative |
|---|---|---|---|
| [00_installation.md](00_installation.md) | installer les outils, cloner, lancer les tests | **tout le monde** | 30 min |
| [01_specification.md](01_specification.md) | relire la spécification et les exemples, les faire valider | **tout le monde** | ½ journée |
| [02_tokens.md](02_tokens.md) | les types de token, `Token`, `Position` | Alexandra | 1-2 h |
| [03_lexer.md](03_lexer.md) | le lexer, le flux, les erreurs, `formater` | Alexandra | ½ journée |
| [04_ast.md](04_ast.md) | les nœuds de l'arbre, `afficher_arbre` | Luca | 2-3 h |
| [05_expressions.md](05_expressions.md) | le parser des expressions (Pratt) | Fatoumata | ½ journée |
| [06_instructions.md](06_instructions.md) | le parser des instructions, la reprise sur erreur | Fatoumata | ½ journée |
| [07_semantique.md](07_semantique.md) | l'analyse sémantique, les portées | Luca | ½ journée |
| [08_generation.md](08_generation.md) | la génération de Python, **le test central** | Arthur | ½ journée |
| [09_cli_repl.md](09_cli_repl.md) | `python -m alto run`, le REPL | Alexandra | ½ journée |
| [10_qualite.md](10_qualite.md) | `Backend`, le formateur, `mypy --strict` | Fatoumata + Arthur | ½ journée |
| [11_extensions.md](11_extensions.md) | les extensions 11, 12, 13 | qui est libre | — |

La répartition et la façon de travailler avec Git sont dans [`../ORGANISATION.md`](../ORGANISATION.md).

## Ce qui est déjà prêt dans le dépôt

| Fichier | Contenu |
|---|---|
| `specification.md` | un **brouillon** complet de la spécification d'Alto (à relire et faire valider) |
| `exemples/*.alt` + `*.attendu` | 5 programmes Alto et leur sortie exacte |
| `pyproject.toml` | la configuration de pytest, mypy (strict) et ruff |
| `alto/__init__.py` | le paquet Python, vide pour l'instant |
| `tests/conftest.py` | rend `alto` importable dans les tests |
| `tests/test_etape_00_installation.py` | un premier test : s'il passe, ton installation marche |

## Le vocabulaire

| Mot | Ce que ça veut dire |
|---|---|
| **source** | le texte du programme Alto |
| **token** (ou jeton) | un « mot » du programme : `var`, `x`, `=`, `3`, `;` |
| **lexème** | le texte exact d'un token : `"var"`, `"x"`, `"3"` |
| **lexer** | le module qui découpe le source en tokens |
| **parser** | le module qui assemble les tokens en arbre |
| **AST** (arbre syntaxique) | la structure du programme sous forme d'objets Python imbriqués |
| **nœud** | un élément de l'arbre : `Binaire`, `Si`, `Variable`… |
| **expression** | ce qui a une valeur : `1 + 2`, `x`, `f(3)` |
| **instruction** | ce qui s'exécute : `var x = 1;`, `si … { }`, `ecris x;` |
| **portée** | la zone du programme où un nom existe |
| **transpiler** | traduire un langage en un autre langage (ici Alto → Python) |
| **prélude** | quelques fonctions Python ajoutées au début du code généré (`_ecris`…) |
| **REPL** | la session interactive : on tape une ligne, on voit le résultat |

## Les règles d'or

1. **Lance les tests tout le temps** : `uv run pytest -k etape_03` après chaque petite modification.
2. **Commence par le cas le plus simple** (un entier, `var x = 1;`), fais-le marcher de bout en bout, puis ajoute le reste.
3. **Un test qui échoue n'est pas un échec** : c'est lui qui te dit quoi faire ensuite.
4. **Lis les messages d'erreur jusqu'en bas** : la dernière ligne d'un traceback Python dit presque toujours où est le problème.
5. **Bloqué ou bloquée depuis plus de 30 minutes ?** Demande aux autres. C'est plus rapide pour tout le monde.
