import yaml
import os

"""
Module de gestion de la configuration du bot.

Ce module gère le chargement de la configuration depuis un fichier YAML
et fournit les paramètres nécessaires au fonctionnement du bot.
"""

def load_config() -> dict:
    """
    Charge la configuration depuis le fichier config.yaml.
    
    Returns:
        dict: Dictionnaire contenant la configuration du bot
            {
                'bot_token': str,
                'command_prefix': str,
                'ffmpeg_path': str
            }
    
    Raises:
        FileNotFoundError: Si le fichier config.yaml n'existe pas
        yaml.YAMLError: Si le fichier YAML est mal formaté
        
    Notes:
        Le chemin du fichier est relatif à l'emplacement du module
    """
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)
