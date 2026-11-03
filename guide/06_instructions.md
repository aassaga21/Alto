# Étape 6 : le parser des instructions

**Qui :** Fatoumata. **Fichiers :** `alto/parser.py` (suite), `tests/test_etape_06_instructions.py`. **Énoncé :** `langage/etapes/06_instructions.md`.

> **En une phrase :** analyser un programme entier (déclarations, `si`, boucles, fonctions…), et **ne pas s'arrêter à la première erreur** : les signaler toutes en une fois.

## 1. Comprendre

### La descente récursive : une méthode par règle de grammaire

Pour les instructions, pas besoin de Pratt. On **recopie la grammaire** presque mot pour mot :

```ebnf
pour = "pour" IDENT "de" expression "jusqua" expression bloc ;
```

```python
def pour(self) -> Pour:
    debut = self.attend(T.POUR)                                 # "pour"
    variable = self.attend(T.IDENT, "après pour").lexeme       # IDENT
    self.attend(T.DE, "après la variable de boucle")           # "de"
    borne_debut = self.expression()                            # expression
    self.attend(T.JUSQUA, "entre les deux bornes")             # "jusqua"
    borne_fin = self.expression()                              # expression
    return Pour(variable, borne_debut, borne_fin, self.bloc(), debut.position)  # bloc
```

Les méthodes s'appellent entre elles : `bloc` appelle `instruction`, qui peut appeler `si`, qui appelle `bloc`… C'est cette récursion qui permet d'imbriquer les blocs à l'infini.

| Dans la grammaire | Dans le code |
|---|---|
| `"var"` (un mot obligatoire) | `self.attend(T.VAR)` |
| `[ "sinon" bloc ]` (facultatif) | `if self.accepte(T.SINON): …` |
| `{ "," expression }` (répété) | `while self.accepte(T.VIRGULE): …` |
| `a \| b` (un choix) | `match self.regarde().kind:` |

### La reprise sur erreur

Un programme avec 3 fautes doit afficher **3 messages**, pas un seul. L'idée :

1. on essaie d'analyser une instruction (`try`) ;
2. si une `ErreurSyntaxe` est levée, on la **note** dans `self.erreurs` ;
3. on **saute** des tokens jusqu'au début probable de l'instruction suivante (après un `;`, ou devant `var`, `si`, `}`…) ;
4. on continue.

À la fin, s'il y a des erreurs, on lève **une seule** `ErreursMultiples` qui les contient toutes.

## 2. Le Python à connaître

### Attraper, noter, continuer

```python
erreurs = []
for ligne in lignes:
    try:
        traiter(ligne)
    except ValueError as erreur:
        erreurs.append(erreur)   # on note, et la boucle continue
```

### Chaîner une exception : `raise … from …`

```python
raise ErreursMultiples(erreurs) from erreurs[0]
```

La nouvelle exception garde l'ancienne dans `__cause__` : on ne perd pas l'origine du problème. Il faut le tester.

### `match` sur une valeur d'`Enum`

```python
match token.kind:
    case T.VAR:
        ...
    case T.SI:
        ...
    case _:        # tous les autres cas
        ...
```

## 3. Pas à pas

### 3.1 Choisir l'instruction d'après le premier token

```python
    def instruction(self) -> Instr:
        match self.regarde().kind:
            case T.VAR:
                return self.declaration()
            case T.FONCTION:
                return self.fonction()
            case T.RENDS:
                return self.rends()
            case T.SI:
                return self.si()
            case T.TANTQUE:
                return self.tantque()
            case T.POUR:
                return self.pour()
            case T.ECRIS:
                return self.ecris()
            case _:
                return self.affectation_ou_expression()
```

### 3.2 Les instructions simples

```python
    def declaration(self) -> Declaration:
        debut = self.attend(T.VAR)
        nom = self.attend(T.IDENT, "après var").lexeme
        self.attend(T.EGAL, "après le nom de la variable")
        valeur = self.expression()
        self.attend(T.POINT_VIRGULE, "en fin de déclaration")
        return Declaration(nom, valeur, debut.position)
```

À toi, sur le même modèle : `rends` (la valeur est facultative : `None` si le token suivant est `;`), `ecris` (au moins une expression, puis `{ "," expression }`), `tantque`, `pour` (donné plus haut), `fonction` (paramètres `IDENT { "," IDENT }`, éventuellement aucun).

### 3.3 `bloc` et `si`

```python
    def bloc(self) -> Bloc:
        debut = self.attend(T.ACC_G, "pour ouvrir le bloc")
        instructions: list[Instr] = []
        while not self.verifie(T.ACC_D):
            if self.verifie(T.FIN):
                raise ErreurSyntaxe("bloc jamais fermé : '}' attendu", debut.position)
            instr = self._instruction_protegee()
            if instr is not None:
                instructions.append(instr)
        self.avance()  # le '}'
        return Bloc(tuple(instructions), debut.position)
```

Pour `si` : après le premier bloc, **tant qu'**on accepte un `sinon` : si le token suivant est `si`, c'est une nouvelle branche ; sinon, c'est le bloc final et on s'arrête.

<details>
<summary>▶ Solution</summary>

```python
    def si(self) -> Si:
        debut = self.attend(T.SI)
        condition = self.expression()
        branches = [Branche(condition, self.bloc(), condition.pos)]
        sinon: Bloc | None = None
        while self.accepte(T.SINON):
            if self.accepte(T.SI):
                condition = self.expression()
                branches.append(Branche(condition, self.bloc(), condition.pos))
            else:
                sinon = self.bloc()
                break
        return Si(tuple(branches), sinon, debut.position)
```

</details>

### 3.4 L'affectation : on ne sait qu'après coup

`x = 1;` et `t[i] = 2;` commencent comme des expressions. On lit donc **d'abord une expression**, puis on regarde s'il y a un `=` :

```python
    def affectation_ou_expression(self) -> Instr:
        expr = self.expression()
        if self.accepte(T.EGAL):
            if not isinstance(expr, (Variable, Index)):
                raise ErreurSyntaxe(
                    "on ne peut affecter qu'à une variable ou à un élément de liste", expr.pos
                )
            valeur = self.expression()
            self.attend(T.POINT_VIRGULE, "en fin d'affectation")
            return Affectation(expr, valeur, expr.pos)
        self.attend(T.POINT_VIRGULE, "en fin d'instruction")
        return ExprInstr(expr, expr.pos)
```

`1 = 2;` et `f(x) = 3;` sont refusés.

### 3.5 Le `;` oublié, signalé au bon endroit

```
var x = 1        ← le ; manque ICI (ligne 1, juste après le 1)
ecris x;         ← et non pas ici, sur le « ecris »
```

Dans `attend`, quand le token attendu est `;`, on calcule la position à partir du **dernier token consommé** (`self.dernier`) : sa colonne plus la longueur de son lexème. Remplace la fin de `attend` :

```python
        message = f"{kind} attendu{' ' + contexte if contexte else ''}, trouvé {_decrire(token)}"
        if kind is T.POINT_VIRGULE and self.dernier is not None:
            # juste après le token précédent, pas au début de la ligne suivante
            position = self.dernier.position.decalee(len(self.dernier.lexeme))
        else:
            position = token.position
        raise ErreurSyntaxe(message, position)
```

### 3.6 Protéger chaque instruction, et se resynchroniser

```python
#: Les tokens qui commencent une instruction (en haut du fichier, près des tables).
DEBUTS_INSTRUCTION = frozenset({T.VAR, T.FONCTION, T.RENDS, T.SI, T.TANTQUE, T.POUR, T.ECRIS})
```

```python
    def _instruction_protegee(self) -> Instr | None:
        avant = self.flux.consommes
        try:
            return self.instruction()
        except ErreurSyntaxe as erreur:
            self.erreurs.append(erreur)
            self._synchroniser(avant)
            return None

    def _synchroniser(self, avant: int) -> None:
        if self.flux.consommes == avant:
            self.avance()  # au moins un token, sinon on boucle à l'infini
        while not self.verifie(T.FIN):
            token = self.regarde()
            if token.kind is T.POINT_VIRGULE:
                self.avance()   # l'instruction fautive se termine ici
                return
            if token.kind in DEBUTS_INSTRUCTION or token.kind is T.ACC_D:
                return          # on s'arrête DEVANT le début de la suivante
            self.avance()
```

> **La boucle infinie :** si l'erreur a lieu sur le tout premier token (par exemple `* 2;`) et que rien n'a été consommé, on recommencerait au même endroit pour toujours. D'où le test `consommes == avant`.

### 3.7 Le programme et le point d'entrée `parse`

```python
    def programme(self) -> Programme:
        instructions: list[Instr] = []
        while not self.verifie(T.FIN):
            if self.verifie(T.ACC_D):  # un '}' orphelin
                token = self.avance()
                self.erreurs.append(ErreurSyntaxe("'}' sans '{' correspondante", token.position))
                continue
            instr = self._instruction_protegee()
            if instr is not None:
                instructions.append(instr)
        return Programme(tuple(instructions))
```

En bas du fichier :

```python
def parse(source: str) -> Programme:
    parser = Parser(tokenize(source))
    programme = Programme(())
    try:
        programme = parser.programme()
    except ErreurLexicale as erreur:
        # le lexer ne peut pas reprendre : on arrête tout, mais on garde les erreurs déjà vues
        parser.erreurs.append(erreur)
    if parser.erreurs:
        raise ErreursMultiples(parser.erreurs) from parser.erreurs[0]
    return programme
```

Teste sur un vrai fichier :

```bash
uv run python -c "
from alto.parser import parse
from alto.noeuds import afficher_arbre
print(afficher_arbre(parse(open('exemples/02_factorielle.alt').read())))"
```

## 4. Les tests à écrire

```python
import pytest

from alto.erreurs import ErreurLexicale, ErreursMultiples, Position
from alto.noeuds import (
    Affectation, Binaire, Bloc, Branche, Declaration, Ecris, Entier, Pour, Programme, Si, Variable,
)
from alto.parser import parse


def test_declaration() -> None:
    assert parse("var x = 1;") == Programme((Declaration("x", Entier(1)),))


def test_si_sinon() -> None:
    attendu = Si(
        (Branche(Variable("a"), Bloc((Ecris((Entier(1),)),))),),
        Bloc((Ecris((Entier(2),)),)),
    )
    assert parse("si a { ecris 1; } sinon { ecris 2; }").instructions[0] == attendu


def test_pour() -> None:
    attendu = Pour(
        "i", Entier(1), Entier(3),
        Bloc((Affectation(Variable("s"), Binaire("+", Variable("s"), Variable("i"))),)),
    )
    assert parse("pour i de 1 jusqua 3 { s = s + i; }").instructions[0] == attendu


@pytest.mark.parametrize("source", ["1 = 2;", "f(x) = 3;"])
def test_affectation_a_une_cible_invalide(source: str) -> None:
    with pytest.raises(ErreursMultiples) as erreur:
        parse(source)
    assert "on ne peut affecter" in erreur.value.erreurs[0].message


def test_point_virgule_oublie_signale_en_fin_de_ligne() -> None:
    with pytest.raises(ErreursMultiples) as erreur:
        parse("var x = 1\necris x;")
    assert erreur.value.erreurs[0].position == Position(1, 10)


def test_plusieurs_erreurs_signalees_ensemble() -> None:
    with pytest.raises(ErreursMultiples) as erreur:
        parse("var = 1;\necris 2;\nvar y 3;")
    positions = [e.position for e in erreur.value.erreurs]
    assert positions == [Position(1, 5), Position(3, 7)]


def test_une_erreur_lexicale_est_chainee() -> None:
    with pytest.raises(ErreursMultiples) as erreur:
        parse("var x = @;")
    assert isinstance(erreur.value.__cause__, ErreurLexicale)


def test_bloc_jamais_ferme() -> None:
    with pytest.raises(ErreursMultiples) as erreur:
        parse("si vrai {\necris 1;")
    assert "jamais fermé" in erreur.value.erreurs[0].message
```

À ajouter : chaque instruction **avec et sans** ses parties facultatives (`rends;`, `si` sans `sinon`, plusieurs `sinon si`, fonction sans paramètre), une boucle dans un `si` dans une fonction, une erreur **dans** un bloc qui n'empêche pas d'analyser la suite du bloc, un `}` orphelin, et : chacun des fichiers de `exemples/` s'analyse sans erreur.

## 5. Pièges fréquents

| Symptôme | Cause |
|---|---|
| le programme ne termine jamais | resynchronisation qui ne consomme rien (voir 3.6) |
| le `;` oublié est signalé sur la ligne suivante | `self.dernier` pas mis à jour dans `avance`, ou cas spécial du 3.5 oublié |
| une seule erreur au lieu de plusieurs | `bloc()` n'utilise pas `_instruction_protegee` |
| `UnboundLocalError: programme` dans `parse` | initialise `programme = Programme(())` avant le `try` |

## 6. C'est fini quand…

- [ ] `uv run pytest -k etape_06` est vert ;
- [ ] les 5 exemples donnent un arbre sans erreur ;
- [ ] un fichier avec 3 fautes donne 3 messages ;
- [ ] **préviens Arthur et Luca** : ils peuvent maintenant écrire leurs tests à partir de vrai code Alto au lieu d'arbres écrits à la main.
