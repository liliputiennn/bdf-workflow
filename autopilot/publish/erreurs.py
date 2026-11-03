"""Erreurs du publieur YouTube, classées selon ce que doit faire l'appelant."""


class ErreurPublication(Exception):
    """Base commune."""


class ErreurQuota(ErreurPublication):
    """Quota atteint ou insuffisant : reporter au lendemain (heure du Pacifique), ne rien mettre en quarantaine."""

    def __init__(self, message: str, prochain_essai: str | None = None):
        super().__init__(message)
        self.prochain_essai = prochain_essai


class ErreurAuth(ErreurPublication):
    """Jeton absent, révoqué ou refusé : s'arrêter, prévenir le propriétaire, ne rien mettre en quarantaine."""


class ErreurContenu(ErreurPublication):
    """YouTube refuse le contenu (métadonnées, fichier, miniature) : quarantaine avec raison."""


class ErreurReseau(ErreurPublication):
    """Réseau ou serveur indisponible après toutes les tentatives : réessayer à la prochaine exécution."""


class Transitoire(Exception):
    """Interne : échec passager à retenter avec attente exponentielle."""
