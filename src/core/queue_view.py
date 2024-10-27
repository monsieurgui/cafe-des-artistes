import discord
from discord.ui import View, Button

class QueueView(View):
    """Reference from original code"""
    def __init__(self, pages, timeout=60):
        super().__init__(timeout=timeout)
        self.pages = pages  # Pre-generated pages
        self.current_page = 0
        
        # Add buttons with emojis
        prev_button = Button(emoji="⬅️", custom_id="prev", disabled=True)
        next_button = Button(emoji="➡️", custom_id="next", disabled=len(pages) <= 1)
        
        prev_button.callback = self.prev_callback
        next_button.callback = self.next_callback
        
        self.add_item(prev_button)
        self.add_item(next_button)
    
    async def prev_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()  # Acknowledge the interaction first
        self.current_page = max(0, self.current_page - 1)
        
        # Update button states
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = self.current_page == len(self.pages) - 1
        
        await interaction.message.edit(
            embed=self.pages[self.current_page], 
            view=self
        )
    
    async def next_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()  # Acknowledge the interaction first
        self.current_page = min(len(self.pages) - 1, self.current_page + 1)
        
        # Update button states
        self.children[0].disabled = self.current_page == 0
        self.children[1].disabled = self.current_page == len(self.pages) - 1
        
        await interaction.message.edit(
            embed=self.pages[self.current_page], 
            view=self
        )
