# Spécification d'Alto

> **BROUILLON à relire ensemble (réunion 0), puis à faire valider par l'enseignant.**
> Tout peut changer : les mots-clés, les règles, les fonctions prédéfinies. Si vous changez quelque chose ici, mettez aussi à jour les programmes de `exemples/` et leurs fichiers `.attendu`.

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

- **Blancs et sauts de ligne** : ignorés. La mise en forme est libre ; une instruction simple se termine par `;`.
- **Commentaires** : de `#` jusqu'à la fin de la ligne.
- **Entiers** : chiffres ASCII, `0`, `42`. Pas de signe : `-3` est le `-` unaire appliqué à `3`.
- **Décimaux** : `3.14`. Il faut au moins un chiffre de chaque côté du point : `1.` et `.5` sont refusés (`1.` donne l'entier `1` suivi d'un caractère inattendu `.`).
- **Textes** : entre guillemets `"..."`, sur une seule ligne. Échappements permis : `\n` (saut de ligne), `\t` (tabulation), `\"` (guillemet), `\\` (barre oblique). Tout autre échappement est une erreur.
- **Identifiants** : une lettre (accents permis), puis des lettres, chiffres ou `_`. Un identifiant **ne commence pas par `_`** : ce préfixe est réservé au code Python généré.
- **Mots-clés** (réservés, ne peuvent pas servir de nom) : `var fonction rends si sinon tantque pour de jusqua ecris vrai faux rien et ou non`.
- **Symboles** : `( ) { } [ ] , ; = == != < <= > >= + - * / %`.

Les jetons qui se ressemblent : `=` (affectation) et `==` (égalité), `<` et `<=`, `>` et `>=`. Le lexer essaie toujours le symbole le plus long d'abord.

## Grammaire (EBNF)

`{ x }` répète zéro fois ou plus, `[ x ]` est facultatif, `|` sépare les choix.

```ebnf
programme     = { instruction } FIN ;
instruction   = declaration | fonction | si | tantque | pour | rends | ecris
              | affectation | expression ";" ;

declaration   = "var" IDENT "=" expression ";" ;
affectation   = cible "=" expression ";" ;
cible         = IDENT | postfixe "[" expression "]" ;
fonction      = "fonction" IDENT "(" [ IDENT { "," IDENT } ] ")" bloc ;
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

- **Pas de comparaison chaînée** : `a < b < c` se lit `(a < b) < c`, et non comme en Python.
- `-a * b` se lit `(-a) * b`, mais `non a == b` se lit `non (a == b)`.
- Seule une fonction **nommée** peut être appelée : `f(1)` est valide, `f(1)(2)` ne l'est pas.

## Sémantique

- **Variables.** On les déclare avec `var` avant de les utiliser. `var x = x;` est refusé (le `x` de droite n'existe pas encore).
- **Blocs et portées.** Chaque bloc `{ }` ouvre une portée : une variable déclarée dans un bloc n'existe plus après lui. Deux blocs voisins peuvent déclarer chacun une variable du même nom.
- **Pas de masquage.** On ne peut pas déclarer un nom déjà visible (variable, paramètre, fonction ou fonction prédéfinie), même dans un bloc intérieur. *Raison : Python n'a pas de portée de bloc ; sans cette règle, le code généré changerait de sens.*
- **Fonctions.** Elles se déclarent **au niveau global** (pas dans un bloc), avant leur premier appel. Une fonction peut s'appeler elle-même (récursion). Elle voit les variables globales déclarées **avant** elle, peut les lire et les modifier. Le nombre d'arguments est vérifié à la compilation. Une fonction sans `rends` (ou avec `rends;`) renvoie `rien`.
- **`rends`** n'est permis qu'à l'intérieur d'une fonction.
- **`pour i de a jusqua b`** parcourt `a, a+1, …, b` : **les deux bornes sont incluses**. Si `a > b`, la boucle ne fait aucun tour. La variable `i` n'existe que dans la boucle.
- **`tantque c { ... }`** répète le bloc tant que `c` est vrai.
- **Affichage.** `ecris` affiche ses valeurs séparées par une espace, puis passe à la ligne. Les booléens s'affichent `vrai` / `faux`, l'absence de valeur `rien`, les listes `[1, 2, 3]` (leurs éléments suivent les mêmes règles), les textes sans guillemets.
- **Arithmétique.** `/` donne toujours un décimal (`7 / 2` vaut `3.5`, `4 / 2` vaut `2.0`). `%` est le reste (convention de Python). `+` additionne des nombres, ou colle deux textes, ou deux listes.
- **Logique.** `et`, `ou`, `non` s'appliquent à des booléens.
- **Listes.** `[1, 2, 3]`, indices à partir de 0 : `l[0]`. On peut affecter un élément : `l[0] = 5;`. Les textes s'indexent aussi : `"abc"[0]` vaut `"a"`.
- **Fonctions prédéfinies** (leurs noms sont réservés) :

| Fonction | Rôle |
|---|---|
| `taille(x)` | le nombre d'éléments d'une liste ou de caractères d'un texte |
| `ajoute(liste, x)` | ajoute `x` à la fin de la liste |
| `texte(x)` | convertit une valeur en texte (`texte(vrai)` vaut `"vrai"`) |

- **Erreurs d'exécution** (division par zéro, indice hors limites, opération impossible comme `1 + "a"`) : le programme s'arrête et affiche un message qui désigne **la ligne Alto** fautive, sans traceback Python.

## Programmes d'exemple

| Fichier | Ce qu'il montre |
|---|---|
| `01_bonjour.alt` | variables, textes et échappements, booléens, `rien`, arithmétique, priorités |
| `02_factorielle.alt` | fonctions, récursion, `pour` (dont une boucle de 0 tour) |
| `03_fizzbuzz.alt` | `si` / `sinon si` / `sinon`, `%`, comparaisons, `et` / `ou` / `non` |
| `04_listes.alt` | listes, indices, affectation d'un élément, prédéfinies, globale modifiée par une fonction |
| `05_premiers.alt` | `tantque` imbriqués, `rends` au milieu d'une boucle, fonction sans paramètre |

## Limites assumées

- Pas de types déclarés (peut-être en extension 12).
- Pas de fonctions imbriquées ; les fonctions ne sont pas des valeurs.
- Pas de dictionnaires, pas de `pour chaque` sur une liste, pas de lecture au clavier.
- Les opérandes de `et` / `ou` / `non` ne sont pas vérifiés : `1 ou 2` n'est pas une erreur de compilation.
- Le formateur (étape 10) perd les commentaires, car ils ne sont pas dans l'arbre.
