# Alto

Alto est un petit langage de programmation aux mots-clés français, conçu dans le cadre du cours Python avancé du Geneva Institute of Technology.

Un programme Alto (`.alt`) est traduit en Python puis exécuté :

    python -m alto run programme.alt

Le transpileur est entièrement écrit à la main, sans générateur de parser :
lexer → parser → analyse sémantique → génération de Python.
