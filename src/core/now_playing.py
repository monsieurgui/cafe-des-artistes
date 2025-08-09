import discord
import asyncio
from datetime import datetime
from utils.constants import COLORS

class NowPlayingDisplay:
    def __init__(self, ctx, song_info, voice_client=None):
        self.ctx = ctx
        self.song_info = song_info
        self.start_time = discord.utils.utcnow()  # Fixed timezone issue
        self.message = None
        self.update_task = None
        self.voice_client = voice_client
        
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
            
        # Clamp to [0, length] to avoid overflow when elapsed > duration
        ratio = 0 if total <= 0 else current / total
        filled = max(0, min(length, int(ratio * length)))
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
        current_time = (discord.utils.utcnow() - self.start_time).total_seconds()
        
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
        """Update the now playing display with state validation"""
        try:
            while self.should_continue():
                if not self.is_playing():
                    await self.stop()
                    break
                    
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
            
    def should_continue(self):
        """Check if display should continue updating"""
        # Validate voice client exists and is playing
        if not self.voice_client or not self.voice_client.is_connected():
            return False
        # Check if message still exists    
        if not self.message:
            return False
        return True
        
    def is_playing(self):
        """Check if voice client is actually playing audio"""
        return (self.voice_client and 
                self.voice_client.is_connected() and 
                self.voice_client.is_playing())
            
    async def stop(self):
        """Stop updating and remove the display"""
        try:
            if self.update_task:
                self.update_task.cancel()
                self.update_task = None
            if self.message:
                try:
                    await self.message.delete()
                except discord.errors.NotFound:
                    pass  # Message already deleted
                except Exception as e:
                    print(f"Error deleting now playing message: {e}")
                finally:
                    self.message = None
        except Exception as e:
            print(f"Error stopping now playing display: {e}")
            # Ensure cleanup even if error occurs
            self.update_task = None
            self.message = None 