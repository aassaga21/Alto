# Organisation du projet — équipe Alexandra, Luca, Fatoumata, Arthur

Ce fichier explique **le projet en entier** (l'idée, la chaîne de compilation, ce qu'on rend), puis **qui fait quoi** pour avancer vite et en parallèle sur GitHub sans se marcher dessus.

---

## 1. L'idée générale du projet

On invente **notre propre langage de programmation**, puis on écrit **à la main** (sans `lark`, `ply` ni générateur de parser) le compilateur qui le **traduit en Python**.

À la fin, cette commande doit marcher :

```bash
python -m monlangage run programme.xyz
```

(`monlangage` = le nom de notre paquet Python, `.xyz` = l'extension de nos fichiers. **À choisir ensemble à la réunion 0.**)

Le langage de démonstration fourni s'appelle **Brindille** (dossier [`demo/`](demo/)). C'est un exemple pour comprendre, **pas un modèle à recopier**.

### La chaîne de compilation (imposée)

```
texte source ──lexer──▶ tokens ──parser──▶ arbre (AST) ──analyse sémantique──▶ arbre vérifié ──génération──▶ code Python ──exec──▶ résultat
```

| Maillon | Ce qu'il fait | Exemple |
|---|---|---|
| **Lexer** | découpe le texte en mots (*tokens*) | `soit x = 3;` → `SOIT`, `IDENT(x)`, `EGAL`, `ENTIER(3)`, `POINT_VIRGULE` |
| **Parser** | assemble les tokens en arbre selon la grammaire | `1 + 2 * 3` → `Binaire(+, 1, Binaire(*, 2, 3))` |
| **Analyse sémantique** | vérifie le sens : variable déclarée ? double déclaration ? `retourne` hors fonction ? | `affiche y;` sans `soit y` → erreur ligne/colonne |
| **Génération** | transforme l'arbre en texte Python | `si x > 1 { ... }` → `if x > 1:` |
| **CLI / REPL** | la ligne de commande `run`, `transpile`, `check`, `repl` | |

### Ce que notre langage doit avoir au minimum

- des expressions avec **au moins deux niveaux de priorité** (`+` et `*`) ;
- des **variables** et des **blocs** qui délimitent leur portée ;
- au moins **une structure de contrôle** (si / boucle) ;
- un moyen d'**afficher** quelque chose.
- Très conseillé : des **fonctions**. Le reste (listes, textes, types…) est en bonus.

👉 **Règle d'or : un petit langage qui marche de bout en bout vaut mieux qu'un gros à moitié fini.** On commence petit, on enrichit après.

### Comment on est évalués

- richesse et cohérence de la spécification ;
- jusqu'où va la chaîne, et si elle marche **de bout en bout** ;
- la qualité et la couverture de **nos propres tests** (il n'y a pas de tests fournis) ;
- les notions Python utilisées à chaque étape ;
- `mypy --strict` sans erreur ;
- les extensions (étapes 11, 12, 13).

### Les 13 étapes du sujet

| Étape | Fichier(s) | Notions Python |
|---|---|---|
| 1 Spécification | `specification.md`, `exemples/` | grammaire EBNF |
| 2 Tokens | `tokens.py`, `erreurs.py` (Position) | `Enum`, `@dataclass(frozen=True)`, `__repr__` |
| 3 Lexer | `lexer.py`, `flux.py`, `erreurs.py` | générateurs, exceptions avec position |
| 4 AST | `noeuds.py` | dataclasses, unions de types (`type Expr = ...`) |
| 5 Expressions (Pratt) | `parser.py` | fonctions de 1ʳᵉ classe, décorateurs paramétrés |
| 6 Instructions | `parser.py` | collecte et chaînage d'exceptions (`ErreursMultiples`) |
| 7 Sémantique | `symboles.py`, `semantique.py` | `singledispatchmethod`, `@contextmanager` |
| 8 Génération | `emetteur.py`, `generateur.py` | context manager, `match`, `assert_never` |
| 9 CLI + REPL | `compilateur.py`, `cli.py`, `repl.py`, `__main__.py` | `argparse`, générateur avec `send` |
| 10 Qualité | `backend.py`, `formateur.py` | `Protocol`, ouvert/fermé, `mypy --strict` |
| 11 *(extension)* module `ast` | `generateur_ast.py` | `ast`, `ast.unparse` |
| 12 *(extension)* typage statique | `typage.py` | `Enum`, typage graduel |
| 13 *(extension)* source maps | `sourcemap.py` | `TypedDict`, `Literal` |

---

## 2. Arborescence du dépôt

On suit l'arborescence conseillée ([`gabarits/arborescence.md`](gabarits/arborescence.md)) : **un module par étape, un fichier de test par étape**. C'est ce qui permet de travailler à 4 sans conflits Git : chacun a *ses* fichiers.

```
projet/
├── specification.md
├── exemples/                    # 5+ programmes .xyz + leur sortie .attendu
├── monlangage/
│   ├── __init__.py
│   ├── __main__.py              # Alexandra
│   ├── erreurs.py               # Alexandra (les autres ajoutent leur classe d'erreur)
│   ├── tokens.py                # Alexandra
│   ├── flux.py                  # Alexandra
│   ├── lexer.py                 # Alexandra
│   ├── noeuds.py                # Luca
│   ├── parser.py                # Fatoumata
│   ├── symboles.py              # Luca
│   ├── semantique.py            # Luca
│   ├── emetteur.py              # Arthur
│   ├── generateur.py            # Arthur
│   ├── compilateur.py           # Alexandra
│   ├── cli.py                   # Alexandra
│   ├── repl.py                  # Alexandra
│   ├── backend.py               # Fatoumata
│   └── formateur.py             # Fatoumata
└── tests/
    ├── conftest.py              # copie de gabarits/conftest_modele.py
    ├── test_etape_02_tokens.py
    ├── test_etape_03_lexer.py
    └── ...
```

> ⚠️ Ne jamais appeler un fichier `ast.py`, `token.py`, `types.py` ou `tokenize.py` : ça masque le module standard de Python.

---

## 3. Le secret pour aller vite : se mettre d'accord sur les « contrats » dès le jour 1

Normalement chaque étape dépend de la précédente (le parser a besoin des tokens, le générateur a besoin de l'arbre…). Pour **travailler tous en même temps**, on fixe dès la réunion 0 les **interfaces** entre les maillons. Ensuite chacun code son morceau en parallèle.

| Contrat | Défini par | Utilisé par | Contenu à fixer le jour 1 |
|---|---|---|---|
| **Liste des tokens** (`TokenKind`) | Alexandra | Fatoumata | le nom de chaque mot-clé et symbole (`SI`, `SINON`, `PLUS`, `ACCOLADE_G`…) |
| **`Token` et `Position`** | Alexandra | tout le monde | `Token(kind, lexeme, position)`, `Position(ligne, colonne)` |
| **Liste des nœuds de l'AST** (`noeuds.py`) | Luca | Fatoumata, Luca, Arthur | un nœud par construction : `Entier`, `Variable`, `Binaire`, `Si`, `Fonction`… avec leurs champs |
| **Hiérarchie d'erreurs** | Alexandra | tout le monde | `ErreurMonlangage` → `ErreurLexicale`, `ErreurSyntaxe`, `ErreurSemantique`, `ErreursMultiples`, `ErreurExecution` |
| **Points d'entrée** | — | Alexandra (CLI) | `tokenize(source)`, `parse(source)`, `analyser(programme)`, `generer(programme, analyse)` |

👉 **Premier PR à faire (jour 1)** : Alexandra pousse `tokens.py` + `erreurs.py` en version « squelette » et Luca pousse `noeuds.py` en squelette (juste les dataclasses, sans `afficher_arbre`). **Dès que ces deux PR sont fusionnées, tout le monde peut coder.**

En attendant le vrai lexer/parser, chacun peut **construire ses tokens ou ses nœuds à la main** dans ses tests (c'est prévu : le champ `pos` a une valeur par défaut).

---

## 4. Répartition des tâches

### Réunion 0 — TOUS ENSEMBLE (étape 1)

C'est la seule étape qu'on fait à quatre, car **tout le reste en dépend** et l'enseignant doit la valider avant qu'on code.

- [ ] Choisir **le nom** du langage, **l'extension** des fichiers, l'**idée directrice** (mots-clés en français ? accolades ou indentation ?).
- [ ] Écrire les **5 programmes d'exemple** d'abord (comme si le langage existait), puis en déduire la grammaire. Un chacun + un ensemble :
  - Alexandra : `01_bonjour` (affichage, textes)
  - Luca : `02_factorielle` (fonctions, récursion)
  - Fatoumata : `03_fizzbuzz` (conditions, boucles, opérateurs)
  - Arthur : `04_listes` (listes / indices, si on en a)
  - Ensemble : `05_...` (un programme qui mélange tout)
  - Pour chacun, écrire **à la main** le fichier `.attendu` (la sortie exacte).
- [ ] Remplir `projet/specification.md` à partir du gabarit [`gabarits/specification.md`](gabarits/specification.md) : lexique, grammaire EBNF, table des priorités, sémantique (portées, fonctions), cas limites (bloc vide, boucle de 0 tour…).
- [ ] Fixer les **contrats** de la section 3 (liste des tokens, liste des nœuds).
- [ ] **Faire valider la spécification par l'enseignant.**

### Phase 1 — le cœur de la chaîne (en parallèle)

#### 🟣 Alexandra — Tokens, Lexer, Erreurs (étapes 2 et 3)

- [ ] **Jour 1** : squelette de `erreurs.py` (`Position`, `ErreurMonlangage` et toutes les sous-classes vides) et `tokens.py` (`TokenKind` complet, `Token`) → **PR en priorité**, les autres en ont besoin.
- [ ] `tokens.py` : dictionnaire des mots-clés et liste des symboles **construits à partir de l'Enum**, triés du plus long au plus court ; `__str__` de `TokenKind` (`';'`, `<identifiant>`).
- [ ] `lexer.py` : générateur `tokenize(source) -> Iterator[Token]` (blancs, commentaires, nombres, textes avec échappements, identifiants, mots-clés, symboles, ligne/colonne, token `FIN` à la fin).
- [ ] `ErreurLexicale` sur caractère inconnu, texte non terminé, échappement invalide.
- [ ] `flux.py` : classe générique `Flux[T]` avec `regarde(decalage=0)` et `avance()` (Fatoumata en a besoin pour le parser → à livrer tôt).
- [ ] `formater(erreur, source, fichier)` : `fichier:ligne:colonne : genre : message` + la ligne + un `^`.
- [ ] Tests : `test_etape_02_tokens.py`, `test_etape_03_lexer.py`.

#### 🔵 Luca — AST puis Analyse sémantique (étapes 4 et 7)

- [ ] **Jour 1** : squelette de `noeuds.py` (une dataclass gelée par construction, champ `pos` exclu de la comparaison avec valeur par défaut, unions `Expr` et `Instr`, nœud `Programme`) → **PR en priorité**.
- [ ] `afficher_arbre(noeud) -> str` générique (sans une ligne par type de nœud — utiliser `dataclasses.fields`).
- [ ] Tests : `test_etape_04_ast.py`.
- [ ] `symboles.py` : pile de portées, `portee()` en `@contextmanager`, `declarer()`, `chercher()`.
- [ ] `semantique.py` : visiteur `Analyseur` avec `singledispatchmethod` (une méthode par nœud). Vérifier : variable déclarée avant usage, pas de double déclaration, règles des fonctions (nb d'arguments, `retourne` hors fonction), fonctions prédéfinies protégées.
- [ ] Collecter **toutes** les erreurs → une seule `ErreursMultiples` ; renvoyer un objet `Analyse` utile au générateur (se mettre d'accord avec Arthur sur son contenu, ex. globales modifiées par fonction).
- [ ] Tests : `test_etape_07_semantique.py` (on peut construire les arbres à la main sans attendre le parser).

#### 🟢 Fatoumata — Parser (étapes 5 et 6)

- [ ] **Jour 1** : préparer `test_etape_05_expressions.py` avec la table des cas (`"1 + 2 * 3"` → arbre attendu) en `pytest.mark.parametrize`, à partir de la table des priorités de la spec.
- [ ] `parser.py` : classe `Parser` (enveloppe un `Flux`) avec `regarde()`, `avance()`, `verifie()`, `accepte()`, `attend()`.
- [ ] Décorateurs paramétrés `prefixe(*kinds)` et `infixe(*kinds, precedence)` qui remplissent `REGLES_PREFIXE` / `REGLES_INFIXE`.
- [ ] `expression(precedence)` : algorithme de Pratt ; toutes les expressions (littéraux, variables, parenthèses, unaires, binaires, appels, indices).
- [ ] `parse_expression(source)`.
- [ ] Étape 6 : une méthode par instruction, `bloc()`, `programme()`, affectations (vérifier que la cible est valide), **récupération d'erreurs** (on note l'erreur et on saute jusqu'à l'instruction suivante), `parse(source) -> Programme` qui lève une `ErreursMultiples` chaînée avec `from`.
- [ ] Point-virgule oublié signalé **juste après le token précédent**.
- [ ] Tests : `test_etape_05_expressions.py`, `test_etape_06_instructions.py`.

> Le parser est le plus gros morceau. Si Fatoumata est en avance ou en retard, Arthur ou Alexandra peuvent prendre l'étape 6 (instructions) pendant qu'elle finit l'étape 5.

#### 🟠 Arthur — Génération de Python + le test central (étape 8)

- [ ] `emetteur.py` : classe `Emetteur` avec `ligne(texte)`, `bloc()` en context manager (indente, ajoute `pass` si vide), `texte()`.
- [ ] `generateur.py` : traduction de chaque nœud avec `match` / `case` et `assert_never`. On peut commencer **avant le parser** en construisant les arbres à la main.
- [ ] Faire la liste des « pièges » de traduction propres à **notre** langage (portée de bloc vs Python, noms qui sont des mots-clés Python comme `list` ou `class`, division entière, comparaisons chaînées, `global`…) et les régler.
- [ ] `transpiler(source) -> str` + exécution via `exec(compile(code, "<monlangage>", "exec"), {"__name__": "__main__"})`.
- [ ] **Le test central** `test_etape_08_generation.py` : pour chaque fichier de `exemples/`, transpiler, exécuter, capturer la sortie, comparer au `.attendu`. C'est **le test le plus important du projet**.
- [ ] Mettre en place l'outillage pour tout le monde : `pyproject.toml` (pytest, mypy strict, ruff) et, si possible, une **GitHub Action** qui lance `pytest` + `ruff` sur chaque PR.

### Phase 2 — finitions (quand la chaîne marche de bout en bout)

| Qui | Tâche |
|---|---|
| 🟣 **Alexandra** | **Étape 9** : `compilateur.py` (façade `compiler` / `transpiler` / `executer`), `ErreurExecution` ramenée à la ligne source, `cli.py` (`run`, `transpile [-o]`, `check`, `repl`), codes de retour, fichier introuvable propre, `__main__.py`, `repl.py` (générateur avec `send`, garde l'état, survit aux erreurs, attend la suite si bloc non fermé). Tests `test_etape_09_cli_repl.py`. |
| 🟢 **Fatoumata** | **Étape 10** : `backend.py` (`Protocol Backend`, dataclass `Sortie`, dict `BACKENDS`), option `--backend`, `formateur.py` (réécrit notre langage proprement, parenthèses minimales), sous-commande `fmt`. Tests `test_etape_10_qualite.py`. |
| 🟠 **Arthur** | **`mypy --strict`** sur tout le paquet (chacun corrige ses fichiers, Arthur coordonne) puis **extension 11** (`generateur_ast.py` avec le module `ast`). |
| 🔵 **Luca** | **Extension 12** : typage statique (`typage.py`, `ErreurType`, annotations dans la spec, le lexer et le parser). |
| Le premier libre | **Extension 13** : source maps (`sourcemap.py`). |

---

## 5. Résumé : qui dépend de qui

```
Réunion 0 (tous) : spec + exemples + contrats
        │
        ├── Alexandra : tokens/erreurs (jour 1) ──▶ lexer, flux ──────────────┐
        ├── Luca      : noeuds (jour 1) ──▶ afficher_arbre ──▶ sémantique ────┤
        ├── Fatoumata : parser (tests avec tokens faits à la main au début) ──┤──▶ chaîne complète
        └── Arthur    : émetteur, générateur (arbres faits à la main) ────────┘    │
                                                                                   ▼
                                     Alexandra CLI/REPL · Fatoumata backend/formateur
                                     Arthur mypy + ext. 11 · Luca ext. 12 · ext. 13
```

**Objectif intermédiaire :** faire marcher `01_bonjour` de bout en bout le plus vite possible (même avec un langage minuscule), puis ajouter les constructions une par une.

---

## 6. Travailler ensemble sur GitHub

### Mise en place (une seule personne, ex. Fatoumata)

1. Créer le dépôt sur GitHub et ajouter Alexandra, Luca et Arthur comme collaborateurs (*Settings → Collaborators*).
2. Pousser le contenu actuel :

```bash
cd /Users/mac/Desktop/langage
git init
git add .
git commit -m "Sujet du projet et organisation de l'équipe"
git branch -M main
git remote add origin https://github.com/<compte>/<depot>.git
git push -u origin main
```

3. Protéger `main` (*Settings → Branches → Add rule*) : PR obligatoire, 1 relecture minimum.
4. Créer un **ticket (Issue) par case à cocher** de la section 4, assigné à la bonne personne, et un tableau **Projects** (À faire / En cours / En relecture / Fini).

### Les autres membres

```bash
git clone https://github.com/<compte>/<depot>.git
cd <depot>
```

### Le cycle de travail (pour chaque tâche)

```bash
git switch main
git pull                                   # récupérer le travail des autres
git switch -c alexandra/lexer              # une branche par tâche : prenom/sujet
# ... coder + écrire les tests ...
uv run pytest projet                       # les tests passent ?
uv run ruff check projet                   # le style est bon ?
git add projet/monlangage/lexer.py projet/tests/test_etape_03_lexer.py
git commit -m "Lexer : nombres, identifiants et mots-clés"
git push -u origin alexandra/lexer
```

Puis sur GitHub : **ouvrir une Pull Request**, demander une relecture à un autre membre, fusionner quand c'est validé, et supprimer la branche.

### Règles d'équipe

- **On ne pousse jamais directement sur `main`.** Toujours une branche + une PR.
- **Petites PR, souvent** (une fonctionnalité + ses tests). Une PR de 2000 lignes, personne ne la relit.
- **Chacun ses fichiers** (voir l'arborescence). Si on doit toucher le fichier d'un autre (ex. ajouter une erreur dans `erreurs.py`), on le prévient et on fait une petite PR dédiée.
- **Changer un contrat** (renommer un token, un champ de nœud) = prévenir tout le monde **avant**, car ça casse le code des autres.
- **`git pull` sur `main` chaque matin**, puis `git merge main` dans sa branche pour éviter les gros conflits.
- **Pas de PR sans tests.** Les tests sont notés autant que le code. Un test = un comportement, nommé comme une phrase : `test_point_virgule_oublie_signale_en_fin_de_ligne`. Tester les **erreurs** (avec ligne et colonne) autant que les succès.
- **Le test central (étape 8) doit rester vert** sur `main`.
- Messages de commit en français, clairs : `Parser : priorité des opérateurs de comparaison`.

### Point quotidien (5 minutes)

Chacun répond à : *qu'est-ce que j'ai fini ? qu'est-ce que je fais aujourd'hui ? est-ce que je suis bloqué(e) par quelqu'un ?* Le rendu est quotidien (voir `docs/rendu.md`), donc on fusionne ce qui marche chaque soir.

---

## 7. Commandes utiles

```bash
uv run pytest projet                 # tous les tests
uv run pytest projet -k etape_05     # les tests d'une étape
uv run mypy projet/monlangage        # typage strict
uv run ruff check projet             # style
uv run ruff format projet            # mise en forme automatique
cd projet && uv run python -m monlangage run exemples/01_bonjour.xyz
cd projet && uv run python -m monlangage transpile exemples/01_bonjour.xyz
```
