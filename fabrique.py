# -*- coding: utf-8 -*-
"""Atelier d'images : un petit programme à part, lancé par le bot, qui fabrique les images et animations lourdes (raid, Worlds).
Le bot lui envoie une commande, attend la réponse, et reste libre de répondre aux joueurs pendant le calcul.
Il s'arrête tout seul quand le bot s'arrête. Ne pas le lancer à la main."""
import pickle
import sys


def principal():
    entree, sortie = sys.stdin.buffer, sys.stdout.buffer
    sys.stdout = sys.stderr   # rien d'autre que les réponses ne doit passer par la sortie
    import cartes_img
    while True:
        try:
            nom, args = pickle.load(entree)
        except EOFError:
            break
        try:
            reponse = ("ok", getattr(cartes_img, nom)(*args))
        except Exception as erreur:
            reponse = ("erreur", repr(erreur))
        pickle.dump(reponse, sortie)
        sortie.flush()


if __name__ == "__main__":
    principal()
