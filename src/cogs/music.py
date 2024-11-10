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
        else:
            # Update context for existing player
            self.bot.music_players[ctx.guild.id].ctx = ctx
        return self.bot.music_players[ctx.guild.id]

    @commands.command(name='p', aliases=['play'])
    async def play(self, ctx, *, query):
        """Joue une chanson ou une playlist depuis YouTube"""
        player = self.get_music_player(ctx)
        await player.stop_live()  # Stop live if running
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

    @commands.command(name='h', aliases=['help'], help='Affiche ce message d\'aide')
    async def help(self, ctx):
        """Affiche la liste des commandes disponibles"""
        embed = discord.Embed(
            title="🎵 Commandes du Bot Musical",
            color=COLORS['INFO']
        )
        
        commands_info = {
            "Lecture": {
                "!p <lien/recherche>": "Joue une chanson ou ajoute à la queue",
                "!skip": "Passe à la chanson suivante",
                "!loop": "Active/désactive la lecture en boucle",
                "!quit": "Arrête la musique et déconnecte le bot"
            },
            "Diffusion en Direct": {
                "!live <lien>": "Démarre une diffusion en direct",
                "!stop": "Arrête la diffusion en direct"
            },
            "File d'attente": {
                "!queue": "Affiche les 10 prochaines chansons",
                "!queue all": "Affiche toute la file d'attente",
                "!purge": "Vide la file d'attente"
            },
            "Administration": {
                "!cleanup": "Force le nettoyage des ressources (Admin)",
                "!support <message>": "Envoie un message au support"
            }
        }
        
        for category, commands in commands_info.items():
            command_text = "\n".join(f"`{cmd}`: {desc}" for cmd, desc in commands.items())
            # Using different emojis for each category
            category_emojis = {
                "Lecture": "📀",
                "Diffusion en Direct": "🔴",
                "File d'attente": "📋",
                "Administration": "⚙️"
            }
            emoji = category_emojis.get(category, "📑")
            embed.add_field(name=f"{emoji} {category}", value=command_text, inline=False)
        
        embed.set_footer(text="Bot développé avec ❤️ pour le Café des Artistes")
        await ctx.send(embed=embed)

    @commands.command(name='l', aliases=['loop'])
    async def loop(self, ctx, *, query=None):
        """Active/désactive le mode boucle pour la chanson actuelle ou démarre la boucle d'une nouvelle chanson"""
        player = self.get_music_player(ctx)
        await player.stop_live()  # Stop live if running
        await player.toggle_loop(ctx, query)

    @commands.command(name='p5')
    async def play_five(self, ctx, *, query):
        """Joue une chanson ou une playlist 5 fois"""
        player = self.get_music_player(ctx)
        await player.add_multiple_to_queue(query, 5)

    @commands.command(name='p10')
    async def play_ten(self, ctx, *, query):
        """Joue une chanson ou une playlist 10 fois"""
        player = self.get_music_player(ctx)
        await player.add_multiple_to_queue(query, 10)

    @commands.command(name='cleanup', aliases=['clean'], help='Force le nettoyage des ressources')
    async def cleanup(self, ctx):
        """Force le nettoyage des ressources du bot"""
        try:
            player = self.get_music_player(ctx)
            
            # Send initial message
            status_msg = await ctx.send(MESSAGES['CLEANUP_START'])
            
            # Clear queue and stop playback
            player.queue.clear()
            if player.voice_client and player.voice_client.is_playing():
                player.voice_client.stop()
            
            # Cancel any pending tasks
            if player.disconnect_task:
                player.disconnect_task.cancel()
                player.disconnect_task = None
                
            if player.loop_task:
                player.loop_task.cancel()
                player.loop_task = None
                
            # Force cleanup
            await player.cleanup()
            
            # Update status message
            embed = discord.Embed(
                description=MESSAGES['CLEANUP_COMPLETE'],
                color=COLORS['SUCCESS']
            )
            await status_msg.edit(content=None, embed=embed)
            
        except Exception as e:
            # Send error message if cleanup fails
            embed = discord.Embed(
                title=MESSAGES['ERROR_TITLE'],
                description=MESSAGES['CLEANUP_ERROR'].format(str(e)),
                color=COLORS['ERROR']
            )
            await ctx.send(embed=embed)

    @commands.command(name='live')
    async def live(self, ctx, *, url):
        """Démarre une diffusion en direct"""
        player = self.get_music_player(ctx)
        await player.start_live(url)
        
    @commands.command(name='stop')
    async def stop(self, ctx):
        """Arrête la lecture en cours"""
        player = self.get_music_player(ctx)
        await player.stop()
        await ctx.send(embed=discord.Embed(
            description=MESSAGES['PLAYBACK_STOPPED'],
            color=COLORS['WARNING']
        ))

async def setup(bot):
    """Configure le cog de musique"""
    await bot.add_cog(Music(bot))
