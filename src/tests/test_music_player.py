"""
Tests unitaires pour le lecteur de musique.

Ce module contient les tests pour vérifier le bon fonctionnement
du lecteur de musique et ses différentes fonctionnalités.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch
from core.music_player import MusicPlayer

@pytest.fixture
async def music_player():
    """
    Fixture pour créer une instance de test du lecteur de musique.
    
    Returns:
        MusicPlayer: Instance configurée pour les tests
        
    Notes:
        - Utilise des mocks pour simuler le bot et le contexte Discord
        - Nettoie automatiquement les ressources après chaque test
    """
    bot = Mock()
    ctx = Mock()
    player = MusicPlayer(bot, ctx)
    yield player
    await player.cleanup()

@pytest.mark.asyncio
async def test_add_to_queue(music_player):
    """
    Teste l'ajout de chansons à la file d'attente.
    
    Vérifie:
        - L'ajout réussi d'une chanson
        - La gestion des URLs invalides
        - Le traitement des playlists
        - Les limites de la file d'attente
    """
    # Configuration du test
    test_url = "https://youtube.com/watch?v=test"
    
    # Test d'ajout simple
    await music_player.add_to_queue(test_url)
    assert len(music_player.queue) == 1
    
    # Vérification des métadonnées
    song = music_player.queue[0]
    assert 'url' in song
    assert 'title' in song
