import discord
from discord.ui import View, Button

"""
Module de gestion de l'interface utilisateur pour la file d'attente musicale.

Ce module fournit une interface interactive pour naviguer dans la file d'attente
des chansons avec des boutons de pagination.
"""

class QueueView(View):
    """
    Vue personnalisée pour l'affichage paginé de la file d'attente.
    
    Cette classe gère :
    - L'affichage des pages de la file d'attente
    - La navigation entre les pages via des boutons
    - La mise à jour dynamique de l'interface
    
    Attributes:
        pages (list): Liste des embeds représentant chaque page
        current_page (int): Index de la page actuellement affichée
        timeout (int): Délai avant désactivation automatique des boutons
    """

    def __init__(self, pages, timeout=60):
        """
        Initialise la vue avec les pages et les boutons de navigation.
        
        Args:
            pages (list): Liste des embeds Discord pour chaque page
            timeout (int, optional): Délai en secondes avant timeout. Défaut à 60
        
        Notes:
            Les boutons sont automatiquement désactivés selon la position
            dans la pagination (premier/dernier)
        """
        super().__init__(timeout=timeout)
        self.pages = pages
        self.current_page = 0
        
        # Configuration des boutons de navigation
        prev_button = Button(
            emoji="⬅️", 
            custom_id="prev", 
            disabled=True
        )
        next_button = Button(
            emoji="➡️", 
            custom_id="next", 
            disabled=len(pages) <= 1
        )
        
        # Association des callbacks aux boutons
        prev_button.callback = self.prev_callback
        next_button.callback = self.next_callback
        
        # Ajout des boutons à la vue
        self.add_item(prev_button)
        self.add_item(next_button)
    
    async def prev_callback(self, interaction: discord.Interaction):
        """
        Gère le clic sur le bouton précédent.
        
        Args:
            interaction (discord.Interaction): L'interaction déclenchée par le clic
            
        Notes:
            - Diffère la réponse pour éviter le timeout Discord
            - Met à jour l'état des boutons selon la nouvelle position
            - Met à jour l'embed affiché
        """
        await interaction.response.defer()
        self.current_page = max(0, self.current_page - 1)
        
        # Mise à jour de l'état des boutons
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = self.current_page == len(self.pages) - 1
        
        # Mise à jour de l'affichage
        await interaction.message.edit(
            embed=self.pages[self.current_page], 
            view=self
        )
    
    async def next_callback(self, interaction: discord.Interaction):
        """
        Gère le clic sur le bouton suivant.
        
        Args:
            interaction (discord.Interaction): L'interaction déclenchée par le clic
            
        Notes:
            - Diffère la réponse pour éviter le timeout Discord
            - Met à jour l'état des boutons selon la nouvelle position
            - Met à jour l'embed affiché
        """
        await interaction.response.defer()
        self.current_page = min(len(self.pages) - 1, self.current_page + 1)
        
        # Mise à jour de l'état des boutons
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = self.current_page == len(self.pages) - 1
        
        # Mise à jour de l'affichage
        await interaction.message.edit(
            embed=self.pages[self.current_page], 
            view=self
        )
