# Alto

Alto est un petit langage de programmation **aux mots-clés français**, conçu dans le cadre du cours Python avancé du Geneva Institute of Technology. Un programme Alto (fichier `.alt`) est traduit en Python, puis exécuté :

```bash
python -m alto run programme.alt
```

Le compilateur est **entièrement écrit à la main**, sans bibliothèque ni générateur de parser (ni `lark`, ni `ply`).

```
fonction fizzbuzz(n) {
    si n % 15 == 0 {
        rends "FizzBuzz";
    } sinon si n % 3 == 0 {
        rends "Fizz";
    } sinon {
        rends texte(n);
    }
}

pour i de 1 jusqua 15 {
    ecris fizzbuzz(i);
}
```

## Sommaire

- [Installation](#installation)
- [Utilisation](#utilisation)
- [Le langage en bref](#le-langage-en-bref)
- [Comment ça marche](#comment-ça-marche)
- [Tests et qualité](#tests-et-qualité)
- [Organisation du dépôt](#organisation-du-dépôt)
- [Équipe](#équipe)

## Installation

Il faut **Python 3.12 ou plus** et [uv](https://docs.astral.sh/uv/), qui installe la bonne version de Python et les outils du projet.

```bash
git clone https://github.com/aassaga21/Alto.git
cd Alto
uv run pytest          # la première fois, uv crée l'environnement ; tout doit être vert
```

Le pas à pas pour débutants (y compris le dépannage sous Windows) est dans [`guide/00_installation.md`](guide/00_installation.md).

## Utilisation

| Commande | Ce qu'elle fait |
|---|---|
| `uv run python -m alto run p.alt` | exécute le programme |
| `uv run python -m alto check p.alt` | vérifie le programme sans l'exécuter (n'affiche rien s'il est correct) |
| `uv run python -m alto transpile p.alt` | affiche le Python généré (`-o p.py` pour l'écrire dans un fichier) |
| `uv run python -m alto fmt p.alt` | réécrit le programme proprement (`--ecrire` pour modifier le fichier) |
| `uv run python -m alto repl` | ouvre une session interactive |

`run` et `transpile` acceptent `--backend python` (par défaut, génération de texte) ou `--backend ast` (génération avec le module `ast` de Python).

**Codes de retour** : `0` tout va bien, `1` erreur de compilation ou fichier introuvable, `2` mauvaise option, `3` erreur d'exécution.

### Les messages d'erreur

Les erreurs montrent le fichier, la ligne, la colonne et la ligne fautive. Le compilateur signale **toutes** les erreurs d'un coup :

```
p.alt:2:7 : erreur sémantique : 'y' n'est pas déclaré
    ecris y;
          ^
p.alt:3:17 : erreur de type : 'x' doit être de type entier, pas texte
    var x: entier = "a";
                    ^
```

Une erreur d'exécution désigne la **ligne Alto**, sans traceback Python :

```
p.alt:2 : erreur d'exécution : indice hors limites
        rends l[5];
```

### Le REPL

```
$ uv run python -m alto repl
Alto — Ctrl-D (ou Ctrl-Z puis Entrée sous Windows) pour quitter.
alto> var x = 20;
alto> x * 2 + 2
42
alto> si x > 1 {
....> ecris "oui";
....> }
oui
```

Le REPL se souvient des saisies précédentes, affiche une expression tapée seule, attend la fin d'un bloc ouvert et survit aux erreurs.

## Le langage en bref

La définition complète est dans [`specification.md`](specification.md) (lexique, grammaire EBNF, priorités, sémantique, cas limites).

| Construction | Alto |
|---|---|
| Variable | `var x = 3;` puis `x = x + 1;` |
| Affichage | `ecris "total :", x;` |
| Condition | `si x > 0 { … } sinon si x < 0 { … } sinon { … }` |
| Boucle bornée | `pour i de 1 jusqua 10 { … }` (**les deux bornes sont incluses**) |
| Boucle conditionnelle | `tantque x < 10 { … }` |
| Fonction | `fonction f(a, b) { rends a + b; }` |
| Valeurs | entiers, décimaux, textes `"…"`, `vrai` / `faux`, `rien`, listes `[1, 2, 3]` |
| Logique | `et`, `ou`, `non` |
| Prédéfinies | `taille(x)`, `ajoute(liste, x)`, `texte(x)` |
| Commentaire | `# jusqu'à la fin de la ligne` |
| Types (facultatifs) | `var n: entier = 3;`, `fonction f(x: decimal) -> texte { … }` |

Quelques règles à connaître :

- chaque bloc `{ }` ouvre une portée, et **on ne peut pas redéclarer un nom déjà visible** (Python n'a pas de portée de bloc : sans cette règle, le code généré changerait de sens) ;
- `/` donne toujours un décimal (`7 / 2` vaut `3.5`) ;
- `a < b < c` se lit `(a < b) < c`, contrairement à Python ;
- le **typage est graduel** : sans annotation, une valeur a le type inconnu et est acceptée partout ; avec une annotation, les erreurs de type sont signalées à la compilation.

Le dossier [`exemples/`](exemples/) contient 6 programmes et leur sortie exacte (fichiers `.attendu`).

## Comment ça marche

```
texte .alt ──lexer──▶ tokens ──parser──▶ arbre ──analyse──▶ arbre vérifié ──générateur──▶ Python ──exec──▶ résultat
```

Par exemple, la fonction `fizzbuzz` ci-dessus devient (les noms sont renommés pour éviter toute collision avec Python) :

```python
def _v_66697a7a62757a7a_1(_v_6e_2):
    if ((_v_6e_2 % 15) == 0):
        return 'FizzBuzz'
    elif ((_v_6e_2 % 3) == 0):
        return 'Fizz'
    ...
```

| Étape | Module(s) | Rôle | Notions Python |
|---|---|---|---|
| 2 Tokens | `tokens.py`, `erreurs.py` | les types de token, `Token`, `Position`, les erreurs | `Enum`, `@dataclass(frozen=True)` |
| 3 Lexer | `lexer.py`, `flux.py` | texte → tokens, avec ligne et colonne | générateurs (`yield`), générique `Flux[T]` |
| 4 AST | `noeuds.py` | les nœuds de l'arbre | dataclasses, unions de types |
| 5-6 Parser | `parser.py` | tokens → arbre (Pratt pour les expressions), reprise sur erreur | fonctions de 1ʳᵉ classe, décorateurs paramétrés |
| 7 Sémantique | `symboles.py`, `semantique.py` | portées, déclarations, appels, globales | `singledispatchmethod`, `@contextmanager` |
| 8 Génération | `emetteur.py`, `generateur.py` | arbre → texte Python + prélude | `match` / `case`, `assert_never` |
| 9 CLI + REPL | `compilateur.py`, `cli.py`, `repl.py`, `__main__.py` | la ligne de commande, la session interactive | `argparse`, générateur avec `send` |
| 10 Qualité | `backend.py`, `backends.py`, `formateur.py` | plusieurs sorties branchées sur la même chaîne | `Protocol`, `mypy --strict` |
| Ext. 11 | `generateur_ast.py` | génération avec le module `ast` | `ast`, `ast.unparse` |
| Ext. 12 | `typage.py` | typage statique graduel | `Enum`, typage graduel |

La CLI et le REPL ne passent que par la façade `alto/compilateur.py` (`compiler`, `transpiler`, `executer`). Ajouter un backend dans `alto/backends.py` le rend disponible dans `--backend` **sans modifier la CLI**.

## Tests et qualité

```bash
uv run pytest                  # tous les tests (565)
uv run pytest -k etape_03      # les tests d'une étape
uv run mypy alto               # typage strict, sans erreur
uv run ruff check alto tests   # style
```

- un fichier de tests par étape (`tests/test_etape_XX_*.py`) ;
- **le test central** (`tests/test_etape_08_generation.py`) exécute chaque programme de `exemples/` avec les deux backends et compare sa sortie au fichier `.attendu` ;
- une GitHub Action ([`.github/workflows/qualite.yml`](.github/workflows/qualite.yml)) lance `pytest`, `ruff` et `mypy` à chaque push et à chaque PR.

Pour mettre le code en forme, utilisez `uv run ruff format alto tests` et **pas** `ruff format .`, qui reformaterait aussi le code Python contenu dans les guides Markdown.

## Organisation du dépôt

```
Alto/
├── specification.md     # la définition du langage (version 1.1)
├── ORGANISATION.md      # qui fait quoi, et comment on travaille avec Git
├── guide/               # le guide pas à pas, une page par étape
├── exemples/            # les programmes .alt et leur sortie .attendu
├── alto/                # le compilateur (paquet Python)
├── tests/               # un fichier de tests par étape
└── docs/                # la documentation de chaque partie
```

Documentation détaillée par partie :

- [`docs/lexer.md`](docs/lexer.md) : tokens, erreurs, flux et lexer (étapes 2 et 3) ;
- [`README_ARTHUR.md`](README_ARTHUR.md) : génération de Python et extension `ast` (étape 8 et extension 11).

## Équipe

Le projet a été réalisé à trois :

| Membre | Parties |
|---|---|
| Alexandra | tokens et lexer (étapes 2-3), CLI et REPL (étape 9), typage statique (extension 12) |
| Fatoumata | arbre syntaxique (étape 4), parser (étapes 5-6), analyse sémantique (étape 7), backends et formateur (étape 10) |
| Arthur | génération de Python (étape 8), extension `ast` (extension 11), GitHub Action |

La spécification (étape 1) a été écrite ensemble.
