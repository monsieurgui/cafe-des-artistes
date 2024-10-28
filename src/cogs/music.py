import discord
from discord.ext import commands
from core.music_player import MusicPlayer
from utils.constants import MESSAGES, COLORS

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    def get_music_player(self, ctx):
        """Récupère ou crée un lecteur de musique pour le serveur"""
        if ctx.guild.id not in self.bot.music_players:
            self.bot.music_players[ctx.guild.id] = MusicPlayer(self.bot, ctx)
        return self.bot.music_players[ctx.guild.id]

    @commands.command(name='p', aliases=['play'])
    async def play(self, ctx, *, query):
        """Joue une chanson ou une playlist depuis YouTube"""
        player = self.get_music_player(ctx)
        await player.add_to_queue(query)

    @commands.command(name='s', aliases=['skip'])
    async def skip(self, ctx):
        """Passe à la chanson suivante"""
        player = self.get_music_player(ctx)
        await player.skip()

    @commands.command(name='purge')
    async def purge(self, ctx):
        """Vide la file d'attente de musique"""
        player = self.get_music_player(ctx)
        await player.purge()

    @commands.command(name='queue', aliases=['q'])
    async def queue(self, ctx, show_all: str = None):
        """Affiche la file d'attente actuelle"""
        player = self.get_music_player(ctx)
        embed, view = await player.get_detailed_queue(show_all == "all")
        await ctx.send(embed=embed, view=view)

    @commands.command(name='support')
    async def support(self, ctx, *, message):
        """Envoie un message de support au propriétaire du bot"""
        try:
            # Remplacez ceci par votre ID utilisateur Discord
            owner_id = 503411896041340949  # Mettez votre ID utilisateur Discord ici
            owner = await self.bot.fetch_user(owner_id)
            
            embed = discord.Embed(
                title=MESSAGES['SUPPORT_TITLE'],
                description=message,
                color=COLORS['ERROR']
            )
            embed.add_field(name="De", value=f"{ctx.author} (ID: {ctx.author.id})")
            embed.add_field(name="Serveur", value=f"{ctx.guild.name} (ID: {ctx.guild.id})")
            embed.add_field(name="Canal", value=f"{ctx.channel.name} (ID: {ctx.channel.id})")
            
            await owner.send(embed=embed)
            await ctx.author.send(embed=discord.Embed(
                description=MESSAGES['SUPPORT_SENT'],
                color=COLORS['SUCCESS']
            ))
            await ctx.message.delete()
            
        except discord.Forbidden:
            await ctx.send(embed=discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=MESSAGES['DM_ERROR'],
                color=COLORS['ERROR']
            ), delete_after=10)
        except Exception as e:
            print(f"Erreur de commande support: {str(e)}")  # Ajout de journalisation pour le débogage
            await ctx.send(embed=discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=MESSAGES['SUPPORT_ERROR'],
                color=COLORS['ERROR']
            ), delete_after=10)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Gère les erreurs de commandes"""
        if isinstance(error, commands.CommandInvokeError):
            error = error.original
        
        if isinstance(error, ValueError):
            embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=str(error),
                color=COLORS['ERROR']
            )
            await ctx.send(embed=embed, delete_after=10)

    @commands.command(name='quit', help='Quitte le canal vocal et vide la file d\'attente')
    async def quit(self, ctx):
        """Quitte le canal vocal et vide la file d'attente"""
        player = self.get_music_player(ctx)
        
        # Vide la file d'attente
        player.queue.clear()
        
        # Arrête la lecture en cours s'il y en a une
        if player.voice_client and player.voice_client.is_playing():
            player.voice_client.stop()
        
        # Annule tout minuteur de déconnexion en attente
        if player.disconnect_task:
            player.disconnect_task.cancel()
            player.disconnect_task = None
        
        # Nettoie et déconnecte immédiatement
        await player.cleanup()
        
        # Envoie un message de confirmation
        embed = discord.Embed(
            description=MESSAGES['GOODBYE'],
            color=COLORS['WARNING']
        )
        await ctx.send(embed=embed)

    @commands.command(name='help', aliases=['h'])
    async def help(self, ctx):
        """Affiche toutes les commandes disponibles"""
        embed = discord.Embed(
            title="🎵 Café des Artistes - Commandes",
            description="Voici la liste des commandes disponibles:",
            color=COLORS['INFO']
        )
        
        commands_list = {
            "!p ou !play": "Jouer une chanson ou une liste de lecture YouTube",
            "!s ou !skip": "Passer à la chanson suivante",
            "!q ou !queue": "Afficher la file d'attente actuelle",
            "!queue all": "Afficher la file complète avec pagination",
            "!purge": "Vider la file d'attente",
            "!l ou !loop": "Activer/désactiver la lecture en boucle",
            "!quit": "Quitter le canal vocal et vider la file d'attente",
            "!h ou !help": "Afficher cette liste de commandes",
            "!support": "Envoyer un message au propriétaire du bot"
        }
        
        for command, description in commands_list.items():
            embed.add_field(
                name=command,
                value=description,
                inline=False
            )
            
        await ctx.send(embed=embed)

    @commands.command(name='l', aliases=['loop'])
    async def loop(self, ctx, *, query=None):
        """Active/désactive le mode boucle pour la chanson actuelle ou démarre la boucle d'une nouvelle chanson"""
        player = self.get_music_player(ctx)
        await player.toggle_loop(ctx, query)

async def setup(bot):
    """Configure le cog de musique"""
    await bot.add_cog(Music(bot))
