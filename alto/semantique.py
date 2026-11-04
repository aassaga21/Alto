"""L'analyse sémantique d'Alto."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import singledispatchmethod

from alto.erreurs import (
    SANS_POSITION,
    ErreurAlto,
    ErreurSemantique,
    ErreursMultiples,
    ErreurType,
    Position,
)
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
from alto.typage import Type, compatible, type_binaire, type_unaire

#: Les fonctions prédéfinies et leur nombre d'arguments.
PREDEFINIES: dict[str, int] = {"taille": 1, "ajoute": 2, "texte": 1}

#: Extension 12 : les types des paramètres et du retour des prédéfinies.
TYPES_PREDEFINIES: dict[str, tuple[tuple[frozenset[Type], ...], Type]] = {
    "taille": ((frozenset({Type.LISTE, Type.TEXTE}),), Type.ENTIER),
    "ajoute": ((frozenset({Type.LISTE}), frozenset(Type)), Type.RIEN),
    "texte": ((frozenset(Type),), Type.TEXTE),
}


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
        self._retour: Type | None = None  # le type de retour annoté de cette fonction

    def analyser(self, programme: Programme) -> Analyse:
        with self.table.portee("globale"):
            for nom, nb in PREDEFINIES.items():
                self.table.declarer(Symbole(nom, Genre.PREDEFINIE, SANS_POSITION, nb))
            for instr in programme.instructions:
                self.instruction(instr)
        return self.resultat

    def erreur(self, message: str, pos: Position) -> None:
        self.erreurs.append(ErreurSemantique(message, pos))  # on NOTE, on ne lève pas

    def erreur_type(self, message: str, pos: Position) -> None:
        self.erreurs.append(ErreurType(message, pos))  # collectée avec les autres

    def verifier_type(self, attendu: Type, recu: Type, quoi: str, pos: Position) -> None:
        """Signale une erreur de type si `recu` ne convient pas là où on attend `attendu`."""
        if not compatible(attendu, recu):
            self.erreur_type(f"{quoi} doit être de type {attendu}, pas {recu}", pos)

    def declarer(
        self,
        nom: str,
        genre: Genre,
        pos: Position,
        nb_parametres: int = 0,
        *,
        type_valeur: Type = Type.INCONNU,
        types_parametres: tuple[Type, ...] = (),
        type_retour: Type = Type.INCONNU,
    ) -> None:
        existant = self.table.chercher(nom)
        if existant is not None:  # règle « pas de masquage »
            if existant.genre is Genre.PREDEFINIE:
                self.erreur(f"'{nom}' est une fonction prédéfinie, ce nom est réservé", pos)
            else:
                self.erreur(f"'{nom}' est déjà déclaré ({existant.pos})", pos)
            return
        self.table.declarer(
            Symbole(nom, genre, pos, nb_parametres, type_valeur, types_parametres, type_retour)
        )

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
        recu = self.expression(noeud.valeur)  # AVANT de déclarer : `var x = x;` est faux
        if noeud.annotation is not None:
            self.verifier_type(noeud.annotation, recu, f"'{noeud.nom}'", noeud.valeur.pos)
        type_valeur = Type.INCONNU if noeud.annotation is None else noeud.annotation
        self.declarer(noeud.nom, Genre.VARIABLE, noeud.pos, type_valeur=type_valeur)

    @instruction.register
    def _(self, noeud: Affectation) -> None:
        attendu = Type.INCONNU
        match noeud.cible:
            case Variable(nom):
                symbole = self.table.chercher(nom)
                if symbole is None:
                    self.erreur(f"'{nom}' n'est pas déclaré", noeud.cible.pos)
                elif symbole.genre is not Genre.VARIABLE:
                    self.erreur(
                        f"'{nom}' est une fonction, on ne peut pas lui affecter", noeud.cible.pos
                    )
                else:
                    attendu = symbole.type_valeur
                    if self._fonction is not None and self.table.est_globale(nom):
                        self.resultat.globales_modifiees[self._fonction].add(nom)
            case Index(cible, indice):
                type_cible = self.expression(cible)
                self.verifier_type(Type.ENTIER, self.expression(indice), "un indice", indice.pos)
                if type_cible is Type.TEXTE:
                    self.erreur_type("un texte ne se modifie pas", noeud.cible.pos)
                elif not compatible(Type.LISTE, type_cible):
                    self.erreur_type(
                        f"on ne peut pas indexer une valeur de type {type_cible}", noeud.cible.pos
                    )
        recu = self.expression(noeud.valeur)
        if isinstance(noeud.cible, Variable):
            self.verifier_type(attendu, recu, f"'{noeud.cible.nom}'", noeud.valeur.pos)

    @instruction.register
    def _(self, noeud: Ecris) -> None:
        for valeur in noeud.valeurs:
            self.expression(valeur)

    @instruction.register
    def _(self, noeud: Si) -> None:
        for branche in noeud.branches:
            condition = self.expression(branche.condition)
            self.verifier_type(Type.BOOLEEN, condition, "la condition", branche.condition.pos)
            self.bloc(branche.corps)
        if noeud.sinon is not None:
            self.bloc(noeud.sinon)

    @instruction.register
    def _(self, noeud: TantQue) -> None:
        condition = self.expression(noeud.condition)
        self.verifier_type(Type.BOOLEEN, condition, "la condition", noeud.condition.pos)
        self.bloc(noeud.corps)

    @instruction.register
    def _(self, noeud: Pour) -> None:
        for borne in (noeud.debut, noeud.fin):
            self.verifier_type(Type.ENTIER, self.expression(borne), "une borne de pour", borne.pos)
        with self.table.portee("pour"):  # la variable n'existe que dans la boucle
            self.declarer(noeud.variable, Genre.VARIABLE, noeud.pos, type_valeur=Type.ENTIER)
            self.bloc(noeud.corps)

    @instruction.register
    def _(self, noeud: Fonction) -> None:
        if self.table.profondeur > 1:
            self.erreur("une fonction se déclare au niveau global, pas dans un bloc", noeud.pos)
            return
        types_parametres = tuple(
            Type.INCONNU if t is None else t
            for t in (noeud.types_parametres or (None,) * len(noeud.parametres))
        )
        type_retour = Type.INCONNU if noeud.type_retour is None else noeud.type_retour
        # déclarée AVANT le corps : la fonction peut s'appeler elle-même
        self.declarer(
            noeud.nom,
            Genre.FONCTION,
            noeud.pos,
            len(noeud.parametres),
            types_parametres=types_parametres,
            type_retour=type_retour,
        )
        self.resultat.globales_modifiees[noeud.nom] = set()
        precedente, retour_precedent = self._fonction, self._retour
        self._fonction, self._retour = noeud.nom, noeud.type_retour
        try:
            with self.table.portee(noeud.nom, fonction=True):
                for parametre, type_parametre in zip(
                    noeud.parametres, types_parametres, strict=True
                ):
                    self.declarer(parametre, Genre.VARIABLE, noeud.pos, type_valeur=type_parametre)
                self.bloc(noeud.corps)
        finally:
            self._fonction, self._retour = precedente, retour_precedent

    @instruction.register
    def _(self, noeud: Rends) -> None:
        if self._fonction is None:
            self.erreur("'rends' en dehors d'une fonction", noeud.pos)
        recu = Type.RIEN if noeud.valeur is None else self.expression(noeud.valeur)
        if self._retour is not None:
            self.verifier_type(
                self._retour, recu, f"la valeur rendue par '{self._fonction}'", noeud.pos
            )

    @instruction.register
    def _(self, noeud: ExprInstr) -> None:
        self.expression(noeud.expr)

    # --- Expressions : chacune renvoie son type (extension 12) ----------------------

    @singledispatchmethod
    def expression(self, noeud: Expr) -> Type:
        raise NotImplementedError(f"expression non gérée : {type(noeud).__name__}")

    @expression.register
    def _(self, noeud: Entier) -> Type:
        return Type.ENTIER

    @expression.register
    def _(self, noeud: Decimal) -> Type:
        return Type.DECIMAL

    @expression.register
    def _(self, noeud: Texte) -> Type:
        return Type.TEXTE

    @expression.register
    def _(self, noeud: Booleen) -> Type:
        return Type.BOOLEEN

    @expression.register
    def _(self, noeud: Rien) -> Type:
        return Type.RIEN

    @expression.register
    def _(self, noeud: Variable) -> Type:
        symbole = self.table.chercher(noeud.nom)
        if symbole is None:
            self.erreur(f"'{noeud.nom}' n'est pas déclaré", noeud.pos)
        elif symbole.genre is not Genre.VARIABLE:
            self.erreur(f"'{noeud.nom}' est une fonction, pas une valeur", noeud.pos)
        else:
            return symbole.type_valeur
        return Type.INCONNU

    @expression.register
    def _(self, noeud: Liste) -> Type:
        for element in noeud.elements:
            self.expression(element)
        return Type.LISTE

    @expression.register
    def _(self, noeud: Unaire) -> Type:
        operande = self.expression(noeud.operande)
        resultat = type_unaire(noeud.op, operande)
        if resultat is None:
            self.erreur_type(f"opération impossible : {noeud.op} {operande}", noeud.pos)
            return Type.INCONNU
        return resultat

    @expression.register
    def _(self, noeud: Binaire) -> Type:
        gauche = self.expression(noeud.gauche)
        droite = self.expression(noeud.droite)
        resultat = type_binaire(noeud.op, gauche, droite)
        if resultat is None:
            self.erreur_type(f"opération impossible : {gauche} {noeud.op} {droite}", noeud.pos)
            return Type.INCONNU
        return resultat

    @expression.register
    def _(self, noeud: Index) -> Type:
        cible = self.expression(noeud.cible)
        self.verifier_type(Type.ENTIER, self.expression(noeud.indice), "un indice", noeud.pos)
        if cible is Type.TEXTE:
            return Type.TEXTE  # "abc"[0] vaut "a"
        if not compatible(Type.LISTE, cible):
            self.erreur_type(f"on ne peut pas indexer une valeur de type {cible}", noeud.pos)
        return Type.INCONNU  # on ne connaît pas le type des éléments d'une liste

    @expression.register
    def _(self, noeud: Appel) -> Type:
        symbole: Symbole | None = None
        match noeud.fonction:
            case Variable(nom):
                symbole = self.table.chercher(nom)
                if symbole is None:
                    self.erreur(f"fonction inconnue : '{nom}'", noeud.fonction.pos)
                elif symbole.genre is Genre.VARIABLE:
                    self.erreur(f"'{nom}' est une variable, on ne peut pas l'appeler", noeud.pos)
                    symbole = None
                elif len(noeud.arguments) != symbole.nb_parametres:
                    self.erreur(
                        f"'{nom}' attend {symbole.nb_parametres} argument(s), "
                        f"en reçoit {len(noeud.arguments)}",
                        noeud.pos,
                    )
                    symbole = None
            case _:  # f(1)(2), t[0](1) : spécification 1.0
                self.erreur("seule une fonction nommée peut être appelée", noeud.pos)
                self.expression(noeud.fonction)
        types_arguments = [self.expression(argument) for argument in noeud.arguments]
        if symbole is None:
            return Type.INCONNU
        return self._verifier_arguments(symbole, noeud, types_arguments)

    def _verifier_arguments(self, symbole: Symbole, noeud: Appel, recus: list[Type]) -> Type:
        """Vérifie le type de chaque argument et renvoie le type de retour."""
        if symbole.genre is Genre.PREDEFINIE:
            permis, retour = TYPES_PREDEFINIES[symbole.nom]
            for i, (argument, recu, types) in enumerate(
                zip(noeud.arguments, recus, permis, strict=True), start=1
            ):
                if recu is not Type.INCONNU and recu not in types:
                    self.erreur_type(
                        f"l'argument {i} de '{symbole.nom}' ne peut pas être de type {recu}",
                        argument.pos,
                    )
            return retour
        for i, (argument, recu, attendu) in enumerate(
            zip(noeud.arguments, recus, symbole.types_parametres, strict=True), start=1
        ):
            self.verifier_type(attendu, recu, f"l'argument {i} de '{symbole.nom}'", argument.pos)
        return symbole.type_retour


def analyser(programme: Programme) -> Analyse:
    """Vérifie le programme ; lève une `ErreursMultiples` avec toutes les erreurs trouvées."""
    analyseur = Analyseur()
    resultat = analyseur.analyser(programme)
    if analyseur.erreurs:
        raise ErreursMultiples(analyseur.erreurs) from analyseur.erreurs[0]
    return resultat
