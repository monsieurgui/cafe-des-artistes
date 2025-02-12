import discord
import asyncio
from datetime import datetime
from utils.constants import COLORS

class NowPlayingDisplay:
    def __init__(self, ctx, song_info):
        self.ctx = ctx
        self.song_info = song_info
        self.start_time = datetime.utcnow()
        self.message = None
        self.update_task = None
        
    def _format_duration(self, seconds):
        """Format duration as MM:SS or HH:MM:SS"""
        if not seconds:
            return "LIVE"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
        
    def _create_progress_bar(self, current, total, length=20):
        """Create a text-based progress bar"""
        if not total:
            return "▬" * length + " 🔴 LIVE"
            
        filled = int((current / total) * length)
        bar = "▰" * filled + "▱" * (length - filled)
        return f"{bar} 🔊"
        
    def _create_embed(self):
        """Create rich embed for now playing display"""
        embed = discord.Embed(color=COLORS['SUCCESS'])
        
        # Basic info
        embed.title = "Now Playing 🎵"
        embed.description = self.song_info.get('title', 'Unknown')
        
        # Duration and progress
        duration = self.song_info.get('duration', 0)
        current_time = (datetime.utcnow() - self.start_time).total_seconds()
        
        if duration:
            progress = (
                f"`{self._format_duration(int(current_time))} / "
                f"{self._format_duration(duration)}`\n"
                f"{self._create_progress_bar(current_time, duration)}"
            )
            embed.add_field(name="Progress", value=progress, inline=False)
            
        # Channel info
        if channel := self.song_info.get('channel'):
            embed.add_field(name="Channel", value=channel, inline=True)
            
        # Thumbnail
        if thumbnail := self.song_info.get('thumbnail'):
            embed.set_thumbnail(url=thumbnail)
            
        # URL
        if url := self.song_info.get('webpage_url'):
            embed.url = url
            
        return embed
        
    async def start(self):
        """Start displaying and updating the now playing message"""
        try:
            self.message = await self.ctx.send(embed=self._create_embed())
            self.update_task = asyncio.create_task(self._update_display())
        except Exception as e:
            print(f"Error starting now playing display: {e}")
            
    async def _update_display(self):
        """Update the now playing display every 5 seconds"""
        try:
            while True:
                await asyncio.sleep(5)
                if self.message:
                    try:
                        await self.message.edit(embed=self._create_embed())
                    except discord.errors.NotFound:
                        break
                    except Exception as e:
                        print(f"Error updating display: {e}")
                        break
        except asyncio.CancelledError:
            pass
            
    async def stop(self):
        """Stop updating and remove the display"""
        if self.update_task:
            self.update_task.cancel()
        if self.message:
            try:
                await self.message.delete()
            except:
                pass
        self.message = None 