import os

# Les tests ne lancent jamais Remotion (calcul lourd) : rendu Pillow léger ; BDF_RENDU=remotion pour l'exiger.
os.environ.setdefault("BDF_RENDU", "pillow")
