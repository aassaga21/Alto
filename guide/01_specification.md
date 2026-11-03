# Étape 1 : la spécification

**Qui :** tout le monde, ensemble. **Énoncé du cours :** `langage/etapes/01_specification.md`.

> **En une phrase :** écrire noir sur blanc à quoi ressemble Alto et ce que fait chaque construction, **avant** d'écrire la moindre ligne de Python.

## 1. Comprendre

Une spécification, c'est le **mode d'emploi** du langage. Elle répond à trois questions, une par grand morceau du compilateur :

| Question                                                           | Partie de la spec    | Qui s'en sert                                  |
| ------------------------------------------------------------------ | -------------------- | ---------------------------------------------- |
| Quels sont les « mots » ? (`var`, `42`, `"bonjour"`, `==`)         | **Lexique**          | le lexer (étapes 2-3)                          |
| Comment les mots s'assemblent-ils en phrases ?                     | **Grammaire** (EBNF) | le parser (étapes 4-6)                         |
| Que veut dire une phrase correcte, et lesquelles sont interdites ? | **Sémantique**       | l'analyse (étape 7) et le générateur (étape 8) |

Chaque flou dans la spécification devient plus tard une décision prise au hasard au milieu du code. Exemple : « `pour i de 1 jusqua 3` fait-il 2 ou 3 tours ? ». Si la spec ne le dit pas, Arthur (générateur) et Luca (sémantique) risquent de ne pas faire le même choix.

## 2. Lire l'EBNF

L'EBNF est une façon compacte d'écrire une grammaire :

| Notation          | Sens                             | Exemple                      |
| ----------------- | -------------------------------- | ---------------------------- |
| `"var"`           | le mot exact                     | `"var"`                      |
| `IDENT`, `ENTIER` | un token d'une catégorie         | `x`, `42`                    |
| `a b`             | `a` puis `b`                     | `"var" IDENT`                |
| `a \| b`          | `a` **ou** `b`                   | `"vrai" \| "faux"`           |
| `[ a ]`           | `a` est **facultatif**           | `"rends" [ expression ] ";"` |
| `{ a }`           | `a` répété **zéro fois ou plus** | `{ instruction }`            |

Lis par exemple la règle du `si` :

```ebnf
si = "si" expression bloc { "sinon" "si" expression bloc } [ "sinon" bloc ] ;
```

« le mot `si`, une expression, un bloc, puis zéro ou plusieurs `sinon si …`, puis éventuellement un `sinon` final ». Ces trois programmes sont donc corrects :

```
si x > 0 { ecris "positif"; }

si x > 0 { ecris "positif"; } sinon { ecris "négatif ou nul"; }

si x > 0 { ecris "+"; } sinon si x < 0 { ecris "-"; } sinon { ecris "0"; }
```

### Pourquoi la grammaire des expressions a autant de règles ?

```ebnf
somme   = produit { ( "+" | "-" ) produit } ;
produit = unaire  { ( "*" | "/" | "%" ) unaire } ;
```

Une `somme` est faite de `produit`s : donc dans `1 + 2 * 3`, le `2 * 3` est « collé » ensemble avant l'addition. **Plus une règle est basse, plus l'opérateur est prioritaire.** C'est le tableau des priorités, écrit sous forme de règles.

## 3. Ce qui est déjà prêt

Un brouillon complet est dans [`../specification.md`](../specification.md), avec 5 programmes dans [`../exemples/`](../exemples/). Les fichiers `.attendu` contiennent **la sortie exacte**, caractère par caractère, que chaque programme doit produire. Ils deviendront le test central de l'étape 8.

Les choix principaux du brouillon :

| Choix                       | Dans Alto                           | Remarque                                                 |
| --------------------------- | ----------------------------------- | -------------------------------------------------------- |
| Déclarer une variable       | `var x = 3;`                        |                                                          |
| Afficher                    | `ecris a, b;`                       | valeurs séparées par une espace                          |
| Fonction                    | `fonction f(a, b) { rends a + b; }` | pas de types                                             |
| Boucle bornée               | `pour i de 1 jusqua 10 { }`         | **les deux bornes sont incluses** (différent de `range`) |
| Boucle conditionnelle       | `tantque c { }`                     |                                                          |
| Condition                   | `si … { } sinon si … { } sinon { }` |                                                          |
| Booléens, absence de valeur | `vrai`, `faux`, `rien`              |                                                          |
| Logique                     | `et`, `ou`, `non`                   |                                                          |
| Fin d'instruction           | `;`                                 | blocs entre accolades                                    |
| Commentaire                 | `# …`                               |                                                          |
| Prédéfinies                 | `taille`, `ajoute`, `texte`         |                                                          |

## 4. Pas à pas (réunion 0)

...

1. **Lisez les 5 exemples à voix haute**, chacun le sien. Est-ce qu'Alto vous plaît ? Voulez-vous changer un mot-clé (`ecris` → `affiche`, `var` → `soit`…) ? **C'est maintenant ou jamais** : après, ça coûte cher.
2. **Lisez la spec section par section** et posez-vous les questions « au bord » :
   - un bloc vide `si vrai { }` est-il permis ? (oui)
   - une boucle `pour i de 5 jusqua 1` ? (0 tour)
   - une fonction sans paramètre `fonction f() { }` ? (oui, voir `05_premiers.alt`)
   - un texte vide `""` ? (oui)
   - une variable nommée `sinon_si` ? (oui : ce n'est pas un mot-clé)
   - une variable nommée `print` ou `list` ? (oui : le générateur la renommera)
3. **Vérifiez chaque `.attendu` à la main** : exécutez le programme dans votre tête (ou sur papier) et comparez. Une erreur dans un `.attendu`, c'est un test faux pour toute la suite du projet.
4. **Décidez les « contrats »** de la section 3 de `ORGANISATION.md` : la liste des noms de tokens (étape 2) et la liste des nœuds (étape 4). Les guides `02_tokens.md` et `04_ast.md` en proposent une : validez-la ensemble.
5. Si vous changez quelque chose : modifiez `specification.md`, les exemples **et** les `.attendu`, puis faites une PR.
6. **Présentez la spécification à l'enseignant.** On ne commence le code qu'après sa validation.

## 5. Préparer la présentation à l'enseignant

Soyez prêts à expliquer en deux minutes :

- l'idée d'Alto (un langage lisible par un débutant, en français) ;
- le tableau des priorités et un exemple (`non a == b` se lit `non (a == b)`) ;
- la règle « pas de masquage » et **pourquoi** (Python n'a pas de portée de bloc) ;
- pourquoi `pour` inclut ses deux bornes (plus naturel en français ; le générateur ajoutera `+ 1`).

## 6. C'est fini quand…

- [ ] tout le monde a lu et accepte la spécification ;
- [ ] les 5 exemples et leurs `.attendu` ont été vérifiés à la main ;
- [ ] la liste des tokens et la liste des nœuds sont décidées ;
- [ ] **l'enseignant a validé.**
