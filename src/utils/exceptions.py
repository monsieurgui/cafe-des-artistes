"""
Exceptions personnalisées pour le bot musical.

Définit les exceptions spécifiques utilisées dans l'application
pour une meilleure gestion des erreurs.
"""

class MusicBotException(Exception):
    """
    Exception de base pour toutes les erreurs du bot musical.
    
    Attributes:
        message (str): Message d'erreur détaillé
        code (int): Code d'erreur optionnel
    """
    def __init__(self, message: str, code: int = None):
        self.message = message
        self.code = code
        super().__init__(self.message)

class QueueError(MusicBotException):
    """
    Exception levée pour les erreurs liées à la file d'attente.
    
    Examples:
        >>> raise QueueError("La file d'attente est pleine")
        >>> raise QueueError("URL invalide", code=4001)
    """
    pass

class VoiceError(MusicBotException):
    """
    Exception levée pour les erreurs de connexion vocale.
    
    Examples:
        >>> raise VoiceError("Impossible de rejoindre le canal vocal")
        >>> raise VoiceError("Connexion perdue", code=5001)
    """
    pass
