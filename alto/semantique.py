"""L'analyse sémantique d'Alto."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import singledispatchmethod

from alto.erreurs import SANS_POSITION, ErreurAlto, ErreurSemantique, ErreursMultiples, Position
from alto.noeuds import (
    Affectation,
    Appel,
    Binaire,
    Bloc,
    Booleen,
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
from alto.symboles import Genre, Symbole, TableSymboles

#: Les fonctions prédéfinies et leur nombre d'arguments.
PREDEFINIES: dict[str, int] = {"taille": 1, "ajoute": 2, "texte": 1}


@dataclass
class Analyse:
    """Ce que le générateur a besoin de savoir."""

    #: Pour chaque fonction, les variables globales qu'elle affecte (il faudra un `global`).
    globales_modifiees: dict[str, set[str]] = field(default_factory=dict)


class Analyseur:
    def __init__(self) -> None:
        self.table = TableSymboles()
        self.erreurs: list[ErreurAlto] = []
        self.resultat = Analyse()
        self._fonction: str | None = None  # le nom de la fonction en cours d'analyse

    def analyser(self, programme: Programme) -> Analyse:
        with self.table.portee("globale"):
            for nom, nb in PREDEFINIES.items():
                self.table.declarer(Symbole(nom, Genre.PREDEFINIE, SANS_POSITION, nb))
            for instr in programme.instructions:
                self.instruction(instr)
        return self.resultat

    def erreur(self, message: str, pos: Position) -> None:
        self.erreurs.append(ErreurSemantique(message, pos))  # on NOTE, on ne lève pas

    def declarer(self, nom: str, genre: Genre, pos: Position, nb_parametres: int = 0) -> None:
        existant = self.table.chercher(nom)
        if existant is not None:  # règle « pas de masquage »
            if existant.genre is Genre.PREDEFINIE:
                self.erreur(f"'{nom}' est une fonction prédéfinie, ce nom est réservé", pos)
            else:
                self.erreur(f"'{nom}' est déjà déclaré ({existant.pos})", pos)
            return
        self.table.declarer(Symbole(nom, genre, pos, nb_parametres))

    def bloc(self, bloc: Bloc) -> None:
        with self.table.portee():
            for instr in bloc.instructions:
                self.instruction(instr)

    # --- Instructions -------------------------------------------------------------

    @singledispatchmethod
    def instruction(self, noeud: Instr) -> None:
        raise NotImplementedError(f"instruction non gérée : {type(noeud).__name__}")

    @instruction.register
    def _(self, noeud: Declaration) -> None:
        self.expression(noeud.valeur)  # AVANT de déclarer : `var x = x;` est faux
        self.declarer(noeud.nom, Genre.VARIABLE, noeud.pos)

    @instruction.register
    def _(self, noeud: Affectation) -> None:
        match noeud.cible:
            case Variable(nom):
                symbole = self.table.chercher(nom)
                if symbole is None:
                    self.erreur(f"'{nom}' n'est pas déclaré", noeud.cible.pos)
                elif symbole.genre is not Genre.VARIABLE:
                    self.erreur(
                        f"'{nom}' est une fonction, on ne peut pas lui affecter", noeud.cible.pos
                    )
                elif self._fonction is not None and self.table.est_globale(nom):
                    self.resultat.globales_modifiees[self._fonction].add(nom)
            case Index(cible, indice):
                self.expression(cible)
                self.expression(indice)
        self.expression(noeud.valeur)

    @instruction.register
    def _(self, noeud: Ecris) -> None:
        for valeur in noeud.valeurs:
            self.expression(valeur)

    @instruction.register
    def _(self, noeud: Si) -> None:
        for branche in noeud.branches:
            self.expression(branche.condition)
            self.bloc(branche.corps)
        if noeud.sinon is not None:
            self.bloc(noeud.sinon)

    @instruction.register
    def _(self, noeud: TantQue) -> None:
        self.expression(noeud.condition)
        self.bloc(noeud.corps)

    @instruction.register
    def _(self, noeud: Pour) -> None:
        self.expression(noeud.debut)
        self.expression(noeud.fin)
        with self.table.portee("pour"):  # la variable n'existe que dans la boucle
            self.declarer(noeud.variable, Genre.VARIABLE, noeud.pos)
            self.bloc(noeud.corps)

    @instruction.register
    def _(self, noeud: Fonction) -> None:
        if self.table.profondeur > 1:
            self.erreur("une fonction se déclare au niveau global, pas dans un bloc", noeud.pos)
            return
        # déclarée AVANT le corps : la fonction peut s'appeler elle-même
        self.declarer(noeud.nom, Genre.FONCTION, noeud.pos, len(noeud.parametres))
        self.resultat.globales_modifiees[noeud.nom] = set()
        precedente = self._fonction
        self._fonction = noeud.nom
        try:
            with self.table.portee(noeud.nom, fonction=True):
                for parametre in noeud.parametres:
                    self.declarer(parametre, Genre.VARIABLE, noeud.pos)
                self.bloc(noeud.corps)
        finally:
            self._fonction = precedente

    @instruction.register
    def _(self, noeud: Rends) -> None:
        if self._fonction is None:
            self.erreur("'rends' en dehors d'une fonction", noeud.pos)
        if noeud.valeur is not None:
            self.expression(noeud.valeur)

    @instruction.register
    def _(self, noeud: ExprInstr) -> None:
        self.expression(noeud.expr)

    # --- Expressions --------------------------------------------------------------

    @singledispatchmethod
    def expression(self, noeud: Expr) -> None:
        raise NotImplementedError(f"expression non gérée : {type(noeud).__name__}")

    @expression.register
    def _(self, noeud: Entier | Decimal | Texte | Booleen | Rien) -> None:
        pass  # un littéral est toujours correct

    @expression.register
    def _(self, noeud: Variable) -> None:
        symbole = self.table.chercher(noeud.nom)
        if symbole is None:
            self.erreur(f"'{noeud.nom}' n'est pas déclaré", noeud.pos)
        elif symbole.genre is not Genre.VARIABLE:
            self.erreur(f"'{noeud.nom}' est une fonction, pas une valeur", noeud.pos)

    @expression.register
    def _(self, noeud: Liste) -> None:
        for element in noeud.elements:
            self.expression(element)

    @expression.register
    def _(self, noeud: Unaire) -> None:
        self.expression(noeud.operande)

    @expression.register
    def _(self, noeud: Binaire) -> None:
        self.expression(noeud.gauche)
        self.expression(noeud.droite)

    @expression.register
    def _(self, noeud: Index) -> None:
        self.expression(noeud.cible)
        self.expression(noeud.indice)

    @expression.register
    def _(self, noeud: Appel) -> None:
        match noeud.fonction:
            case Variable(nom):
                symbole = self.table.chercher(nom)
                if symbole is None:
                    self.erreur(f"fonction inconnue : '{nom}'", noeud.fonction.pos)
                elif symbole.genre is Genre.VARIABLE:
                    self.erreur(f"'{nom}' est une variable, on ne peut pas l'appeler", noeud.pos)
                elif len(noeud.arguments) != symbole.nb_parametres:
                    self.erreur(
                        f"'{nom}' attend {symbole.nb_parametres} argument(s), "
                        f"en reçoit {len(noeud.arguments)}",
                        noeud.pos,
                    )
            case _:  # f(1)(2), t[0](1) : spécification 1.0
                self.erreur("seule une fonction nommée peut être appelée", noeud.pos)
                self.expression(noeud.fonction)
        for argument in noeud.arguments:
            self.expression(argument)


def analyser(programme: Programme) -> Analyse:
    """Vérifie le programme ; lève une `ErreursMultiples` avec toutes les erreurs trouvées."""
    analyseur = Analyseur()
    resultat = analyseur.analyser(programme)
    if analyseur.erreurs:
        raise ErreursMultiples(analyseur.erreurs) from analyseur.erreurs[0]
    return resultat
