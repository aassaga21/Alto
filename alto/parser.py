"""Le parser d'Alto : Pratt pour les expressions, descente récursive pour le reste."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from enum import IntEnum

from alto.erreurs import ErreurAlto, ErreurLexicale, ErreursMultiples, ErreurSyntaxe
from alto.flux import Flux
from alto.lexer import tokenize
from alto.noeuds import (
    Affectation,
    Appel,
    Binaire,
    Bloc,
    Booleen,
    Branche,
    Decimal,
    Declaration,
    Ecris,
    Entier,
    Expr,
    ExprInstr,
    Fonction,
    Index,
    Instr,
    Liste,
    Pour,
    Programme,
    Rends,
    Rien,
    Si,
    TantQue,
    Texte,
    Unaire,
    Variable,
)
from alto.tokens import Token
from alto.tokens import TokenKind as T


class Precedence(IntEnum):
    AUCUNE = 0
    OU = 1
    ET = 2
    NON = 3
    COMPARAISON = 4
    SOMME = 5
    PRODUIT = 6
    PREFIXE = 7
    APPEL = 8


type ReglePrefixe = Callable[[Parser, Token], Expr]
type RegleInfixe = Callable[[Parser, Expr, Token], Expr]

REGLES_PREFIXE: dict[T, ReglePrefixe] = {}
REGLES_INFIXE: dict[T, tuple[Precedence, RegleInfixe]] = {}

#: Les tokens qui commencent une instruction : on s'y arrête pour reprendre après une erreur.
DEBUTS_INSTRUCTION = frozenset({T.VAR, T.FONCTION, T.RENDS, T.SI, T.TANTQUE, T.POUR, T.ECRIS})


def prefixe(*kinds: T) -> Callable[[ReglePrefixe], ReglePrefixe]:
    """Enregistre une règle pour les tokens qui commencent une expression."""

    def enregistrer(regle: ReglePrefixe) -> ReglePrefixe:
        for kind in kinds:
            REGLES_PREFIXE[kind] = regle
        return regle

    return enregistrer


def infixe(*kinds: T, precedence: Precedence) -> Callable[[RegleInfixe], RegleInfixe]:
    """Enregistre une règle pour les tokens qui suivent une expression déjà lue."""

    def enregistrer(regle: RegleInfixe) -> RegleInfixe:
        for kind in kinds:
            REGLES_INFIXE[kind] = (precedence, regle)
        return regle

    return enregistrer


def _decrire(token: Token) -> str:
    """Comment parler d'un token dans un message d'erreur."""
    if token.kind is T.FIN:
        return "la fin du fichier"
    if token.kind is T.TEXTE:
        return texte_source(token.lexeme)
    return f"'{token.lexeme}'"


def texte_source(valeur: str) -> str:
    """Le texte tel qu'il s'écrit dans le source : le lexer a retiré guillemets et `\\`."""
    echappe = (
        valeur.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
    )
    return f'"{echappe}"'


def _longueur_source(token: Token) -> int:
    """Le nombre de caractères que le token occupe dans le source."""
    if token.kind is T.TEXTE:
        return len(texte_source(token.lexeme))
    return len(token.lexeme)


class Parser:
    def __init__(self, tokens: Iterable[Token]) -> None:
        self.flux = Flux(tokens)
        self.erreurs: list[ErreurAlto] = []
        self.dernier: Token | None = None  # le dernier token consommé

    # --- Accès aux tokens ---------------------------------------------------------

    def regarde(self, decalage: int = 0) -> Token:
        token = self.flux.regarde(decalage)
        assert token is not None, "le token FIN n'est jamais consommé"
        return token

    def avance(self) -> Token:
        token = self.regarde()
        if token.kind is not T.FIN:  # on ne consomme jamais FIN
            self.flux.avance()
            self.dernier = token
        return token

    def verifie(self, kind: T) -> bool:
        """Le token courant est-il de ce type ? (sans consommer)"""
        return self.regarde().kind is kind

    def accepte(self, kind: T) -> Token | None:
        """Consomme le token s'il est de ce type, sinon ne fait rien."""
        return self.avance() if self.verifie(kind) else None

    def attend(self, kind: T, contexte: str = "") -> Token:
        """Consomme le token s'il est de ce type, sinon lève une erreur de syntaxe."""
        token = self.regarde()
        if token.kind is kind:
            return self.avance()
        message = f"{kind} attendu{' ' + contexte if contexte else ''}, trouvé {_decrire(token)}"
        if kind is T.POINT_VIRGULE and self.dernier is not None:
            # juste après le token précédent, pas au début de la ligne suivante
            position = self.dernier.position.decalee(_longueur_source(self.dernier))
        else:
            position = token.position
        raise ErreurSyntaxe(message, position)

    # --- Expressions (Pratt) --------------------------------------------------------

    def expression(self, precedence: int = Precedence.AUCUNE) -> Expr:
        token = self.regarde()
        regle = REGLES_PREFIXE.get(token.kind)
        if regle is None:
            raise ErreurSyntaxe(f"expression attendue, trouvé {_decrire(token)}", token.position)
        self.avance()
        gauche = regle(self, token)

        while True:
            suivant = self.regarde()
            entree = REGLES_INFIXE.get(suivant.kind)
            if entree is None or entree[0] <= precedence:
                return gauche
            self.avance()
            gauche = entree[1](self, gauche, suivant)

    def arguments(self, fermant: T) -> tuple[Expr, ...]:
        """Lit `expr, expr, …` jusqu'au token fermant (la liste peut être vide)."""
        elements: list[Expr] = []
        if not self.verifie(fermant):
            elements.append(self.expression())
            while self.accepte(T.VIRGULE):
                elements.append(self.expression())  # `[1, 2,]` : expression attendue
        self.attend(fermant)
        return tuple(elements)

    # --- Instructions (descente récursive) ------------------------------------------

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

    def declaration(self) -> Declaration:
        debut = self.attend(T.VAR)
        nom = self.attend(T.IDENT, "après var").lexeme
        self.attend(T.EGAL, "après le nom de la variable")
        valeur = self.expression()
        self.attend(T.POINT_VIRGULE, "en fin de déclaration")
        return Declaration(nom, valeur, debut.position)

    def fonction(self) -> Fonction:
        debut = self.attend(T.FONCTION)
        nom = self.attend(T.IDENT, "après fonction").lexeme
        self.attend(T.PAR_G, "après le nom de la fonction")
        parametres: list[str] = []
        if not self.verifie(T.PAR_D):
            parametres.append(self.attend(T.IDENT, "comme paramètre").lexeme)
            while self.accepte(T.VIRGULE):
                parametres.append(self.attend(T.IDENT, "comme paramètre").lexeme)
        self.attend(T.PAR_D, "après les paramètres")
        return Fonction(nom, tuple(parametres), self.bloc(), debut.position)

    def rends(self) -> Rends:
        debut = self.attend(T.RENDS)
        valeur = None if self.verifie(T.POINT_VIRGULE) else self.expression()
        self.attend(T.POINT_VIRGULE, "après rends")
        return Rends(valeur, debut.position)

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

    def tantque(self) -> TantQue:
        debut = self.attend(T.TANTQUE)
        condition = self.expression()
        return TantQue(condition, self.bloc(), debut.position)

    def pour(self) -> Pour:
        debut = self.attend(T.POUR)
        variable = self.attend(T.IDENT, "après pour").lexeme
        self.attend(T.DE, "après la variable de boucle")
        borne_debut = self.expression()
        self.attend(T.JUSQUA, "entre les deux bornes")
        borne_fin = self.expression()
        return Pour(variable, borne_debut, borne_fin, self.bloc(), debut.position)

    def ecris(self) -> Ecris:
        debut = self.attend(T.ECRIS)
        valeurs = [self.expression()]  # au moins une valeur : `ecris;` est refusé
        while self.accepte(T.VIRGULE):
            valeurs.append(self.expression())
        self.attend(T.POINT_VIRGULE, "après ecris")
        return Ecris(tuple(valeurs), debut.position)

    def affectation_ou_expression(self) -> Instr:
        """`x = 1;`, `t[i] = 2;` et `f(x);` commencent tous par une expression."""
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

    # --- Reprise sur erreur ------------------------------------------------------------

    def _instruction_protegee(self) -> Instr | None:
        """Analyse une instruction ; en cas d'erreur, la note et saute à la suivante."""
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
                self.avance()  # l'instruction fautive se termine ici
                return
            if token.kind in DEBUTS_INSTRUCTION or token.kind is T.ACC_D:
                return  # on s'arrête DEVANT le début de la suivante
            self.avance()


# --- Les règles préfixes -------------------------------------------------------------


@prefixe(T.ENTIER)
def _entier(p: Parser, t: Token) -> Expr:
    return Entier(int(t.lexeme), t.position)


@prefixe(T.DECIMAL)
def _decimal(p: Parser, t: Token) -> Expr:
    return Decimal(float(t.lexeme), t.position)


@prefixe(T.TEXTE)
def _texte(p: Parser, t: Token) -> Expr:
    return Texte(t.lexeme, t.position)


@prefixe(T.VRAI, T.FAUX)
def _booleen(p: Parser, t: Token) -> Expr:
    return Booleen(t.kind is T.VRAI, t.position)


@prefixe(T.RIEN)
def _rien(p: Parser, t: Token) -> Expr:
    return Rien(t.position)


@prefixe(T.IDENT)
def _variable(p: Parser, t: Token) -> Expr:
    return Variable(t.lexeme, t.position)


@prefixe(T.PAR_G)
def _groupe(p: Parser, t: Token) -> Expr:
    expr = p.expression()  # on repart de zéro à l'intérieur des parenthèses
    p.attend(T.PAR_D, "pour fermer la parenthèse")
    return expr


@prefixe(T.CROCHET_G)
def _liste(p: Parser, t: Token) -> Expr:
    return Liste(p.arguments(T.CROCHET_D), t.position)


@prefixe(T.MOINS)
def _moins(p: Parser, t: Token) -> Expr:
    return Unaire("-", p.expression(Precedence.PREFIXE), t.position)


@prefixe(T.NON)
def _non(p: Parser, t: Token) -> Expr:
    # précédence NON (3) < COMPARAISON (4) : `non a == b` donne `non (a == b)`
    return Unaire("non", p.expression(Precedence.NON), t.position)


# --- Les règles infixes ----------------------------------------------------------------


def _binaire(precedence: Precedence, *kinds: T) -> None:
    @infixe(*kinds, precedence=precedence)
    def regle(p: Parser, gauche: Expr, t: Token) -> Expr:
        # l'opérande droit ne contient que des opérateurs plus forts : associatif à gauche
        return Binaire(t.lexeme, gauche, p.expression(precedence), t.position)


_binaire(Precedence.OU, T.OU)
_binaire(Precedence.ET, T.ET)
_binaire(Precedence.COMPARAISON, T.EGAL_EGAL, T.DIFFERENT, T.INF, T.INF_EGAL, T.SUP, T.SUP_EGAL)
_binaire(Precedence.SOMME, T.PLUS, T.MOINS)
_binaire(Precedence.PRODUIT, T.FOIS, T.DIVISE, T.MODULO)


@infixe(T.PAR_G, precedence=Precedence.APPEL)
def _appel(p: Parser, gauche: Expr, t: Token) -> Expr:
    # `f(1)(2)` est accepté ici : c'est l'analyse sémantique qui le refuse (spécification 1.0)
    return Appel(gauche, p.arguments(T.PAR_D), gauche.pos)


@infixe(T.CROCHET_G, precedence=Precedence.APPEL)
def _index(p: Parser, gauche: Expr, t: Token) -> Expr:
    indice = p.expression()
    p.attend(T.CROCHET_D, "pour fermer l'indice")
    return Index(gauche, indice, t.position)


# --- Points d'entrée -----------------------------------------------------------------------


def parse_expression(source: str) -> Expr:
    parser = Parser(tokenize(source))
    expr = parser.expression()
    parser.attend(T.FIN, "après l'expression")  # il ne doit rien rester derrière
    return expr


def parse(source: str) -> Programme:
    """Le programme entier ; lève une `ErreursMultiples` avec toutes les erreurs de syntaxe."""
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
