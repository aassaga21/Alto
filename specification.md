# Spécification d'Alto

> **Version 1.1** : la version 1.0, adoptée par l'équipe (Alexandra, Fatoumata, Arthur) le 3 novembre 2026, plus le **typage statique** facultatif de l'extension 12 (section *Types*). En attente de validation par l'enseignant.
> Toute modification passe par une PR qui met aussi à jour les programmes de `exemples/` et leurs fichiers `.attendu`, et doit être annoncée à toute l'équipe.

## Identité

| | |
|---|---|
| Nom | Alto |
| Extension | `.alt` |
| Idée | Un petit langage impératif aux mots-clés français, à accolades, pensé pour être lu par un débutant. Les variables se déclarent avec `var`, on affiche avec `ecris`, et les boucles `pour` incluent leurs deux bornes, comme quand on compte « de 1 jusqu'à 10 ». |
| Cible | Python 3.12, sous forme de texte. |

## Un programme pour donner le ton

```
# La factorielle, de deux façons.
fonction factorielle(n) {
    si n <= 1 {
        rends 1;
    }
    rends n * factorielle(n - 1);
}

var total = 1;
pour i de 1 jusqua 5 {
    total = total * i;
}

si total == factorielle(5) {
    ecris "5! =", total;
} sinon {
    ecris "erreur";
}
```

## Lexique

- **Encodage** : le source est lu en UTF-8.
- **Blancs et sauts de ligne** : ignorés. La mise en forme est libre ; une instruction simple se termine par `;`.
- **Commentaires** : de `#` jusqu'à la fin de la ligne.
- **Entiers** : chiffres ASCII, `0`, `42`. Pas de signe : `-3` est le `-` unaire appliqué à `3`. Les zéros en tête sont permis (`007` vaut `7`). Pas de limite de taille.
- **Décimaux** : `3.14`. Il faut au moins un chiffre de chaque côté du point : `1.` et `.5` sont refusés (`1.` donne l'entier `1` suivi d'un caractère inattendu `.`). Pas de notation scientifique (`1e5`).
- **Textes** : entre guillemets `"..."`, sur une seule ligne. Échappements permis : `\n` (saut de ligne), `\t` (tabulation), `\"` (guillemet), `\\` (barre oblique). Tout autre échappement est une erreur. Un texte qui atteint la fin de la ligne ou du fichier sans guillemet fermant est une erreur (« texte non terminé »). Le texte vide `""` est permis.
- **Identifiants** : une lettre (au sens d'Unicode, accents permis), puis des lettres, chiffres ou `_`. Un identifiant **ne commence pas par `_`** : ce préfixe est réservé au code Python généré.
- **Casse** : Alto distingue majuscules et minuscules. `Si` ou `VAR` sont des identifiants, pas des mots-clés.
- **Mots-clés** (réservés, ne peuvent pas servir de nom) : `var fonction rends si sinon tantque pour de jusqua ecris vrai faux rien et ou non`.
- **Symboles** : `( ) { } [ ] , ; : -> = == != < <= > >= + - * / %`. Les symboles `:` et `->` servent aux annotations de type (section *Types*).
- **Noms de types** : `entier decimal texte booleen liste rien`. Ce ne sont **pas** des mots-clés (sauf `rien`, qui l'était déjà) : `texte` reste aussi le nom d'une fonction prédéfinie. Le parser les reconnaît seulement après `:` ou `->`.

Les jetons qui se ressemblent : `=` (affectation) et `==` (égalité), `<` et `<=`, `>` et `>=`. Le lexer essaie toujours le symbole le plus long d'abord. Un `!` seul est un caractère inattendu.

Tout autre caractère hors d'un texte ou d'un commentaire (`@`, `$`, `'`, `.`…) est une erreur lexicale.

## Grammaire (EBNF)

`{ x }` répète zéro fois ou plus, `[ x ]` est facultatif, `|` sépare les choix.

```ebnf
programme     = { instruction } FIN ;
instruction   = declaration | fonction | si | tantque | pour | rends | ecris
              | affectation | expression ";" ;

declaration   = "var" IDENT [ ":" type ] "=" expression ";" ;
affectation   = cible "=" expression ";" ;
cible         = IDENT | postfixe "[" expression "]" ;
fonction      = "fonction" IDENT "(" [ parametre { "," parametre } ] ")" [ "->" type ] bloc ;
parametre     = IDENT [ ":" type ] ;
type          = "entier" | "decimal" | "texte" | "booleen" | "liste" | "rien" ;
si            = "si" expression bloc { "sinon" "si" expression bloc } [ "sinon" bloc ] ;
tantque       = "tantque" expression bloc ;
pour          = "pour" IDENT "de" expression "jusqua" expression bloc ;
rends         = "rends" [ expression ] ";" ;
ecris         = "ecris" expression { "," expression } ";" ;
bloc          = "{" { instruction } "}" ;

expression    = ou ;
ou            = et { "ou" et } ;
et            = negation { "et" negation } ;
negation      = "non" negation | comparaison ;
comparaison   = somme { ( "==" | "!=" | "<" | "<=" | ">" | ">=" ) somme } ;
somme         = produit { ( "+" | "-" ) produit } ;
produit       = unaire { ( "*" | "/" | "%" ) unaire } ;
unaire        = "-" unaire | postfixe ;
postfixe      = primaire { "(" [ arguments ] ")" | "[" expression "]" } ;
arguments     = expression { "," expression } ;
primaire      = ENTIER | DECIMAL | TEXTE | "vrai" | "faux" | "rien" | IDENT
              | "(" expression ")" | "[" [ arguments ] "]" ;
```

Précisions :

- Le parser distingue `affectation` et `expression ";"` en lisant d'abord une expression : si elle est suivie de `=`, c'est une affectation, et l'expression lue doit être une **cible valide** (un identifiant ou un indice). Sinon, `1 = 2;` ou `f() = 3;` sont des erreurs de syntaxe.
- Pas de virgule finale : `[1, 2,]` et `f(a,)` sont refusés.
- Un programme vide (ou ne contenant que des commentaires) est valide et n'affiche rien.

## Priorité et associativité des opérateurs

Du moins prioritaire au plus prioritaire :

| Niveau | Opérateurs | Associativité |
|---|---|---|
| 1 | `ou` | gauche |
| 2 | `et` | gauche |
| 3 | `non` (unaire) | — |
| 4 | `==` `!=` `<` `<=` `>` `>=` | gauche |
| 5 | `+` `-` | gauche |
| 6 | `*` `/` `%` | gauche |
| 7 | `-` (unaire) | — |
| 8 | appel `f(...)`, indice `t[...]` | gauche |

Points particuliers :

- **Pas de comparaison chaînée** : `a < b < c` se lit `(a < b) < c`, et non comme en Python. Le générateur ajoute les parenthèses.
- `-a * b` se lit `(-a) * b`, mais `non a == b` se lit `non (a == b)`.
- `- - 3` est permis et vaut `3` ; `non non vrai` vaut `vrai`.
- Seule une fonction **nommée** peut être appelée : `f(1)` est valide, `f(1)(2)` ou `t[0](1)` ne le sont pas (erreur sémantique).

## Sémantique

### Valeurs

Alto manipule six sortes de valeurs : les **entiers** (sans limite de taille), les **décimaux**, les **textes**, les **booléens** (`vrai`, `faux`), les **listes** et l'absence de valeur **`rien`**. Les types ne sont pas déclarés ; ils sont vérifiés à l'exécution.

### Variables et portées

- **Déclaration.** On déclare une variable avec `var` avant de l'utiliser, et elle reçoit toujours une valeur initiale. `var x = x;` est refusé (le `x` de droite n'existe pas encore).
- **Affectation.** `x = 3;` n'est permis que si `x` est une variable ou un paramètre visible. On ne peut pas affecter une fonction ni une fonction prédéfinie.
- **Blocs et portées.** Chaque bloc `{ }` ouvre une portée : une variable déclarée dans un bloc n'existe plus après lui. Deux blocs voisins peuvent déclarer chacun une variable du même nom.
- **Pas de masquage.** On ne peut pas déclarer un nom déjà visible (variable, paramètre, fonction ou fonction prédéfinie), même dans un bloc intérieur. Deux paramètres d'une même fonction ne peuvent pas avoir le même nom. *Raison : Python n'a pas de portée de bloc ; sans cette règle, le code généré changerait de sens.*
- **Noms Python.** Un nom Alto peut coïncider avec un mot réservé ou une fonction de Python (`print`, `list`, `class`, `None`…) : c'est permis, le générateur le renomme.

### Fonctions

- Elles se déclarent **au niveau global** (pas dans un bloc, même pas dans un `si`), **avant leur premier appel**. Deux fonctions ne peuvent pas porter le même nom.
- Une fonction peut s'appeler elle-même (récursion). Comme une fonction doit être déclarée avant d'être appelée, deux fonctions ne peuvent pas s'appeler mutuellement.
- Elle voit les variables globales déclarées **avant** elle, peut les lire et les modifier. Elle ne voit pas celles déclarées après.
- Une fonction peut ne pas avoir de paramètre : `fonction f() { }`.
- Le nombre d'arguments est vérifié à la compilation.
- Les arguments sont évalués de gauche à droite, avant l'appel. Une liste passée en argument est **partagée** : si la fonction la modifie (`ajoute`, `l[0] = …`), l'appelant voit la modification.
- Une fonction sans `rends` (ou avec `rends;`) renvoie `rien`.
- **`rends`** n'est permis qu'à l'intérieur d'une fonction ; il termine immédiatement la fonction, même au milieu d'une boucle.
- Une variable ne peut pas être appelée (`var x = 1; x();`), et une fonction ne peut pas être utilisée comme une valeur (`ecris f;`, `var g = f;`).

### Structures de contrôle

- **`si … sinon si … sinon`** : les conditions sont évaluées dans l'ordre ; seul le bloc de la première condition vraie s'exécute. Sans condition vraie, c'est le bloc `sinon` s'il existe.
- **`tantque c { ... }`** : répète le bloc tant que `c` est vrai. Si `c` est faux dès le départ, le bloc ne s'exécute pas.
- **`pour i de a jusqua b`** parcourt `a, a+1, …, b` : **les deux bornes sont incluses**. Si `a > b`, la boucle ne fait aucun tour.
  - `a` et `b` sont évalués **une seule fois**, avant le premier tour, et doivent être des entiers (sinon, erreur d'exécution).
  - La variable `i` est déclarée par la boucle : elle n'existe que dans la boucle et ne doit pas déjà être visible (pas de masquage). Deux boucles `pour i` l'une après l'autre sont permises.
  - Modifier `i` dans le corps est permis, mais ne change pas le tour suivant : `i` reprend la valeur prévue au début de chaque tour.
- **Conditions.** Les conditions de `si` et `tantque` sont prévues pour être des booléens. Depuis la version 1.1, une condition dont le type est **connu** et n'est pas `booleen` est une erreur de type (`si 1 { }`). Si le type est inconnu (variable sans annotation), la valeur suit à l'exécution la règle de Python : `0`, `0.0`, `""`, `[]` et `rien` comptent comme faux, tout le reste comme vrai.
- **Blocs vides.** Un bloc vide `{ }` est permis partout (`si vrai { }`, `fonction f() { }`).

### Affichage

`ecris` affiche ses valeurs séparées par une espace, puis passe à la ligne. Chaque valeur s'affiche ainsi :

| Valeur | Affichage |
|---|---|
| entier | `42`, `-9`, `2432902008176640000` |
| décimal | comme Python : `3.5`, `1.0`, `12.9` |
| texte | sans guillemets : `Bonjour` |
| booléen | `vrai` / `faux` |
| `rien` | `rien` |
| liste | `[1, 2, 3]` : les éléments suivent les mêmes règles (`[vrai, rien, a, [1.5]]`) |

Les valeurs d'un `ecris` sont évaluées de gauche à droite, puis affichées toutes ensemble.

### Opérations

- **Arithmétique.** `+ - * %` sur deux entiers donnent un entier ; si l'un des deux est décimal, le résultat est décimal. `/` donne toujours un décimal (`7 / 2` vaut `3.5`, `4 / 2` vaut `2.0`). `%` est le reste (convention de Python : `-7 % 3` vaut `2`). Pas de division entière.
- **Textes et listes.** `+` colle deux textes, ou deux listes (le résultat est une nouvelle liste). Coller un texte et un nombre est une erreur : on écrit `"n = " + texte(n)`.
- **Comparaisons.** `==` et `!=` comparent deux valeurs de n'importe quel type (`1 == "1"` vaut `faux`, `1 == 1.0` vaut `vrai`). `< <= > >=` comparent deux nombres, ou deux textes (ordre alphabétique de Python).
- **Logique.** `et`, `ou`, `non` s'appliquent à des booléens. `et` et `ou` sont **court-circuités** : dans `a et b`, `b` n'est pas évalué si `a` est faux ; dans `a ou b`, `b` n'est pas évalué si `a` est vrai.
- **Listes.** `[1, 2, 3]`, `[]`. Les indices commencent à 0 : `l[0]`. Un indice négatif compte depuis la fin, comme en Python : `l[-1]` est le dernier élément. On peut affecter un élément existant : `l[0] = 5;`. Les textes s'indexent aussi (`"abc"[0]` vaut `"a"`) mais ne se modifient pas.

### Fonctions prédéfinies

Leurs noms sont réservés : on ne peut ni les redéclarer, ni les affecter.

| Fonction | Rôle |
|---|---|
| `taille(x)` | le nombre d'éléments d'une liste ou de caractères d'un texte |
| `ajoute(liste, x)` | ajoute `x` à la fin de la liste, et renvoie `rien` |
| `texte(x)` | convertit une valeur en texte, selon les règles d'affichage (`texte(vrai)` vaut `"vrai"`, `texte([1, 2])` vaut `"[1, 2]"`) |

### Erreurs

Le compilateur s'arrête à la première erreur lexicale. Le parser et l'analyse sémantique, eux, **signalent toutes leurs erreurs** avant de s'arrêter. Chaque erreur s'affiche ainsi, suivie de la ligne fautive et d'un `^` sous la colonne :

```
fichier.alt:ligne:colonne : genre : message
```

| Genre | Exemples |
|---|---|
| `erreur lexicale` | caractère inattendu `@`, texte non terminé, échappement invalide `\q` |
| `erreur de syntaxe` | `;` oublié (signalé juste après le token précédent), `}` manquant, cible d'affectation invalide |
| `erreur sémantique` | variable non déclarée, double déclaration, masquage, `rends` hors fonction, mauvais nombre d'arguments, fonction déclarée dans un bloc |
| `erreur de type` | valeur qui ne respecte pas une annotation, opération impossible entre types connus (`1 + "a"`), condition non booléenne (section *Types*) |
| `erreur d'exécution` | division (ou `%`) par zéro, indice hors limites, opération impossible comme `1 + "a"`, bornes de `pour` non entières |

Une erreur d'exécution arrête le programme et affiche un message qui désigne **la ligne Alto** fautive, sans traceback Python. Ce qui a été affiché avant l'erreur reste affiché.

## Types (extension 12)

Les annotations de type sont **facultatives**. Un programme sans annotation (comme ceux de la version 1.0) reste valide.

### Les types

| Type | Valeurs |
|---|---|
| `entier` | `0`, `42`, `-3` |
| `decimal` | `3.14`, `2.0` |
| `texte` | `"abc"` |
| `booleen` | `vrai`, `faux` |
| `liste` | `[1, 2]` (le type des éléments n'est pas suivi) |
| `rien` | `rien` |

### Les annotations

```
var age: entier = 20;
fonction moyenne(a: decimal, b: decimal) -> decimal {
    rends (a + b) / 2;
}
```

- `var x: T = valeur;` : la valeur, puis toutes les affectations de `x`, doivent être de type `T`.
- `fonction f(p: T, q) -> R` : chaque paramètre peut être annoté ou non ; chaque argument d'un appel et chaque `rends` sont vérifiés. Une fonction `-> rien` peut faire `rends;`.
- La variable d'une boucle `pour` est toujours un `entier`.

### Typage graduel

Une variable ou un paramètre **sans annotation** a le type inconnu `?`, compatible avec tout. Le compilateur ne signale une erreur que lorsqu'il **sait** que les types ne collent pas :

- `var x = "a"; var n: entier = x;` est accepté (le type de `x` est inconnu), l'erreur éventuelle arrive à l'exécution ;
- `var n: entier = "a";` est refusé à la compilation.

### Compatibilité

Une valeur de type `R` est acceptée là où on attend `T` si `T` et `R` sont le même type, si l'un des deux est `?`, ou si **un `entier` est donné là où on attend un `decimal`** (`var x: decimal = 1;` est permis, l'inverse non).

### Le type de chaque expression

| Expression | Type |
|---|---|
| un littéral | son type (`3` : `entier`, `"a"` : `texte`, `[…]` : `liste`…) |
| une variable | son annotation, ou `?` |
| `entier + - * % entier` | `entier` |
| `+ - * %` avec au moins un `decimal` (et l'autre nombre) | `decimal` |
| `nombre / nombre` | `decimal` |
| `texte + texte`, `liste + liste` | `texte`, `liste` |
| `- nombre` | le même type |
| `==`, `!=` (n'importe quels types) | `booleen` |
| `< <= > >=` entre deux nombres (ou booléens), deux textes, ou deux listes | `booleen` |
| `non x` | `booleen` |
| `a et b`, `a ou b` | `booleen` si `a` et `b` sont booléens, sinon `?` |
| `texte[entier]` | `texte` |
| `liste[entier]` | `?` |
| `f(…)` | le type de retour annoté de `f`, ou `?` |
| `taille(x)`, `ajoute(l, x)`, `texte(x)` | `entier`, `rien`, `texte` |

Avec un opérande de type `?`, le résultat est `?`, sauf pour les opérations dont le type ne dépend pas des opérandes (`/`, comparaisons, `non`, `taille`…).

### Ce qui est refusé (erreur de type)

- une valeur qui ne respecte pas une annotation (déclaration, affectation, argument, `rends`) ;
- une opération **impossible** entre types connus : `1 + "a"`, `"a" * 2`, `- "a"`, `"a" < 1`, `rien < 1` ;
- indexer autre chose qu'une liste ou un texte (`3[0]`), un indice qui n'est pas un entier (`l["a"]`), modifier un texte (`t[0] = "x";`) ;
- un argument de mauvais type pour une prédéfinie : `taille(3)`, `ajoute("a", 1)` ;
- une borne de `pour` qui n'est pas un `entier` ;
- une **condition** de `si` ou de `tantque` dont le type est connu et n'est pas `booleen` : `si 1 { }`. C'est le seul cas où un programme 1.0 qui s'exécutait devient refusé (la version 1.0 suivait la règle de Python pour les conditions).

Les erreurs de type sont collectées avec les autres erreurs sémantiques et affichées avec le genre `erreur de type`.

## Cas limites décidés

| Question | Décision |
|---|---|
| Bloc vide `si vrai { }` | permis |
| `pour i de 5 jusqua 1 { … }` | 0 tour |
| `pour i de 1 jusqua 1 { … }` | 1 tour |
| Fonction sans paramètre `fonction f() { }` | permise (voir `05_premiers.alt`) |
| Texte vide `""` | permis |
| Variable nommée `sinon_si`, `variable`, `Si` | permise (ce ne sont pas des mots-clés) |
| Variable nommée `print`, `list`, `class` | permise, renommée par le générateur |
| Identifiant commençant par `_` | refusé (erreur lexicale) |
| `var x = x;` | refusé (erreur sémantique) |
| `ecris;` sans valeur | refusé (erreur de syntaxe) ; pour une ligne vide, `ecris "";` |
| Instruction qui n'est qu'une expression, comme `1 + 2;` | permise, sans effet |
| `rends` au niveau global | refusé (erreur sémantique) |
| Appel d'une fonction avant sa déclaration | refusé (erreur sémantique) |
| `a < b < c` | `(a < b) < c` |
| `7 / 2`, `4 / 2` | `3.5`, `2.0` |
| `1 / 0`, `1 % 0` | erreur d'exécution |
| `l[taille(l)]` | erreur d'exécution (indice hors limites) |
| `l[-1]` | le dernier élément (comme en Python) |

## Programmes d'exemple

Chaque programme a un fichier `.attendu` qui contient sa sortie exacte. Ils ont été vérifiés à la main par l'équipe et servent de test central (étape 8).

| Fichier | Ce qu'il montre |
|---|---|
| `01_bonjour.alt` | variables, textes et échappements, booléens, `rien`, arithmétique, priorités |
| `02_factorielle.alt` | fonctions, récursion, `pour` (dont une boucle de 0 tour), grands entiers |
| `03_fizzbuzz.alt` | `si` / `sinon si` / `sinon`, `%`, comparaisons, `et` / `ou` / `non` |
| `04_listes.alt` | listes, indices, affectation d'un élément, prédéfinies, globale modifiée par une fonction |
| `05_premiers.alt` | `tantque` imbriqués, `rends` au milieu d'une boucle, fonction sans paramètre |
| `06_types.alt` | annotations de type (extension 12), mélange de variables annotées et non annotées |

## Limites assumées

- Le typage (section *Types*) ne connaît pas le type des éléments d'une liste, et ne vérifie pas qu'une fonction annotée rend une valeur sur tous les chemins.
- Pas de fonctions imbriquées ; les fonctions ne sont pas des valeurs ; pas de récursion mutuelle.
- Pas de dictionnaires, pas de `pour chaque` sur une liste, pas de `pour` avec un pas, pas de lecture au clavier.
- Pas de `arrete` / `continue` dans les boucles : on sort d'une boucle avec une condition, ou avec `rends` dans une fonction.
- Les opérandes de `et` / `ou` / `non` ne sont pas vérifiés : `1 ou 2` n'est pas une erreur de compilation.
- Le formateur (étape 10) perd les commentaires, car ils ne sont pas dans l'arbre.
