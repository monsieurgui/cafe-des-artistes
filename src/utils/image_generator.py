"""
Image generation utilities for creating dynamic "Now Playing" UI images.
This module provides functionality to generate custom images that mimic
the YouTube Music app layout for the bot's Now Playing display.
"""

import io
import asyncio
import aiohttp
import aiofiles
from PIL import Image, ImageDraw, ImageFont
from typing import Optional, Dict, Any
import logging

# Ensure logger is set to INFO level
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Configuration constants - Full height layout for Discord embed
MIN_CANVAS_WIDTH = 600
CANVAS_HEIGHT = 400  # Increased height for full embed display
THUMBNAIL_SIZE = 400  # Full height thumbnail
BACKGROUND_COLOR = (24, 24, 27)  # Dark background similar to YouTube Music
TEXT_COLOR_PRIMARY = (255, 255, 255)  # White for song title
TEXT_COLOR_SECONDARY = (156, 163, 175)  # Gray for artist/metadata
PROGRESS_BAR_BG_COLOR = (75, 85, 99)  # Dark gray for progress bar background
PROGRESS_BAR_FG_COLOR = (239, 68, 68)  # Red for progress bar fill
PROGRESS_BAR_HEIGHT = 8  # Slightly thicker for better visibility
PROGRESS_BAR_Y_OFFSET = 60  # Distance from bottom

# Text positioning - Adjusted for full height layout
TEXT_AREA_X = THUMBNAIL_SIZE + 30  # Start text area after thumbnail + padding
TITLE_Y = 80  # More space from top
ARTIST_Y = 140  # More vertical spacing
REQUESTER_Y = CANVAS_HEIGHT - 120  # Requested by text
ADDED_BY_Y = CANVAS_HEIGHT - 90    # Added by text

# Progress bar positioning - Lower on canvas for better layout
PROGRESS_BAR_Y_POS = CANVAS_HEIGHT - 50
TIMESTAMP_Y = PROGRESS_BAR_Y_POS - 30  # Above progress bar with more space


class ImageGenerator:
    """Main class for generating Now Playing images."""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self._font_cache = {}
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    def _get_font(self, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
        """Get font with caching. Falls back to default font if custom fonts unavailable."""
        cache_key = (size, bold)
        if cache_key in self._font_cache:
            return self._font_cache[cache_key]
        
        # List of font paths to try (Linux/Docker container paths first, then Windows)
        font_paths = []
        if bold:
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux
                "/usr/share/fonts/TTF/arial.ttf",  # Some Linux distros
                "/System/Library/Fonts/Arial.ttf",  # macOS
                "C:/Windows/Fonts/ariblk.ttf",  # Windows
                "arial.ttf"  # System font name
            ]
        else:
            font_paths = [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
                "/usr/share/fonts/TTF/arial.ttf",  # Some Linux distros
                "/System/Library/Fonts/Arial.ttf",  # macOS
                "C:/Windows/Fonts/arial.ttf",  # Windows
                "arial.ttf"  # System font name
            ]
        
        font = None
        for font_path in font_paths:
            try:
                font = ImageFont.truetype(font_path, size)
                break
            except (OSError, IOError):
                continue
        
        if font is None:
            # Ultimate fallback to default font
            font = ImageFont.load_default()
            # Only log warning once per font size/bold combination
            if cache_key not in self._font_cache:
                logger.info(f"Using default font for size {size}, bold={bold}")
        
        self._font_cache[cache_key] = font
        return font
    
    async def _download_thumbnail(self, url: str) -> Optional[Image.Image]:
        """Download and process thumbnail image."""
        if not self.session or not url:
            logger.info(f"No session or URL for thumbnail download: session={bool(self.session)}, url={url}")
            return None
        
        try:
            logger.info(f"Attempting to download thumbnail from: {url}")
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as response:
                logger.info(f"Thumbnail download response: HTTP {response.status}")
                if response.status == 200:
                    image_data = await response.read()
                    logger.info(f"Downloaded {len(image_data)} bytes of thumbnail data")
                    image = Image.open(io.BytesIO(image_data))
                    # Convert to RGB if necessary
                    if image.mode != 'RGB':
                        image = image.convert('RGB')
                    logger.info(f"Successfully processed thumbnail image: {image.size}")
                    return image
                else:
                    logger.warning(f"Failed to download thumbnail: HTTP {response.status}")
                    return None
        except asyncio.TimeoutError:
            logger.error(f"Timeout downloading thumbnail from: {url}")
            return None
        except Exception as e:
            logger.error(f"Error downloading thumbnail from {url}: {e}")
            return None
    
    def _resize_thumbnail(self, image: Image.Image) -> Image.Image:
        """Resize thumbnail to fit the designated area while maintaining aspect ratio."""
        # Calculate scaling to fit within thumbnail area
        original_width, original_height = image.size
        scale_x = THUMBNAIL_SIZE / original_width
        scale_y = THUMBNAIL_SIZE / original_height
        scale = min(scale_x, scale_y)
        
        new_width = int(original_width * scale)
        new_height = int(original_height * scale)
        
        # Resize the image
        resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Create a centered crop/pad to exact thumbnail size
        thumbnail = Image.new('RGB', (THUMBNAIL_SIZE, THUMBNAIL_SIZE), BACKGROUND_COLOR)
        
        # Center the resized image
        x_offset = (THUMBNAIL_SIZE - new_width) // 2
        y_offset = (THUMBNAIL_SIZE - new_height) // 2
        thumbnail.paste(resized, (x_offset, y_offset))
        
        return thumbnail
    
    def _create_placeholder_thumbnail(self) -> Image.Image:
        """Create a placeholder thumbnail when no artwork is available."""
        thumbnail = Image.new('RGB', (THUMBNAIL_SIZE, THUMBNAIL_SIZE), (45, 45, 50))
        draw = ImageDraw.Draw(thumbnail)
        
        # Draw a simple music note icon representation
        # This is a simple geometric representation
        center_x, center_y = THUMBNAIL_SIZE // 2, THUMBNAIL_SIZE // 2
        
        # Draw circle for note head
        note_size = 40
        circle_bbox = [
            center_x - note_size//2, center_y - note_size//2,
            center_x + note_size//2, center_y + note_size//2
        ]
        draw.ellipse(circle_bbox, fill=TEXT_COLOR_SECONDARY)
        
        # Draw stem
        stem_x = center_x + note_size//2 - 5
        stem_top = center_y - note_size//2 - 60
        stem_bottom = center_y
        draw.rectangle([stem_x, stem_top, stem_x + 8, stem_bottom], fill=TEXT_COLOR_SECONDARY)
        
        return thumbnail
    
    def _truncate_text(self, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
        """Truncate text to fit within the specified width."""
        if not text:
            return ""
        
        # Check if text fits as-is
        bbox = font.getbbox(text)
        text_width = bbox[2] - bbox[0]
        
        if text_width <= max_width:
            return text
        
        # Binary search for the longest text that fits
        left, right = 0, len(text)
        result = ""
        
        while left <= right:
            mid = (left + right) // 2
            truncated = text[:mid] + "..." if mid < len(text) else text
            bbox = font.getbbox(truncated)
            truncated_width = bbox[2] - bbox[0]
            
            if truncated_width <= max_width:
                result = truncated
                left = mid + 1
            else:
                right = mid - 1
        
        return result
    
    def _format_duration(self, seconds) -> str:
        """Format duration in seconds to MM:SS or HH:MM:SS format."""
        # Convert to int to handle float values
        seconds = int(seconds) if seconds is not None else 0
        
        if seconds < 0:
            return "00:00"
        
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    
    def _draw_progress_bar(self, draw: ImageDraw.Draw, current_time: int, total_duration: int, canvas_width: int):
        """Draw the progress bar with timestamps above it."""
        progress_bar_x = TEXT_AREA_X
        progress_bar_width = canvas_width - TEXT_AREA_X - 20  # Leave right margin
        
        # Calculate progress percentage
        if total_duration > 0:
            progress = min(max(current_time / total_duration, 0), 1)
        else:
            progress = 0
        
        # Draw timestamps above progress bar (bold) - larger for full height layout
        timestamp_font = self._get_font(20, bold=True)
        current_text = self._format_duration(current_time)
        total_text = self._format_duration(total_duration)
        
        # Current time (left side)
        draw.text((progress_bar_x, TIMESTAMP_Y), current_text, 
                 fill=TEXT_COLOR_PRIMARY, font=timestamp_font)
        
        # Total duration (right side)
        total_bbox = timestamp_font.getbbox(total_text)
        total_width = total_bbox[2] - total_bbox[0]
        total_x = progress_bar_x + progress_bar_width - total_width
        draw.text((total_x, TIMESTAMP_Y), total_text, 
                 fill=TEXT_COLOR_PRIMARY, font=timestamp_font)
        
        # Draw background bar
        bar_bbox = [
            progress_bar_x, PROGRESS_BAR_Y_POS,
            progress_bar_x + progress_bar_width, PROGRESS_BAR_Y_POS + PROGRESS_BAR_HEIGHT
        ]
        draw.rectangle(bar_bbox, fill=PROGRESS_BAR_BG_COLOR)
        
        # Draw progress fill
        if progress > 0:
            fill_width = int(progress_bar_width * progress)
            fill_bbox = [
                progress_bar_x, PROGRESS_BAR_Y_POS,
                progress_bar_x + fill_width, PROGRESS_BAR_Y_POS + PROGRESS_BAR_HEIGHT
            ]
            draw.rectangle(fill_bbox, fill=PROGRESS_BAR_FG_COLOR)
    
    async def create_now_playing_image(self, song_data: Optional[Dict[str, Any]], 
                                     current_time: int = 0) -> io.BytesIO:
        """
        Create a Now Playing image with song information.
        
        Args:
            song_data: Dictionary containing song information (title, artist, thumbnail, etc.)
            current_time: Current playback position in seconds
            
        Returns:
            BytesIO buffer containing the generated PNG image
        """
        # Calculate dynamic width based on title length (using larger font)
        canvas_width = MIN_CANVAS_WIDTH
        if song_data and song_data.get('title'):
            title_font = self._get_font(36, bold=True)  # Use same font size as actual title
            title_bbox = title_font.getbbox(song_data['title'])
            title_width = title_bbox[2] - title_bbox[0]
            required_width = TEXT_AREA_X + title_width + 50  # Add more padding for larger text
            canvas_width = max(MIN_CANVAS_WIDTH, required_width)
        
        # Create the base canvas with dynamic width
        image = Image.new('RGB', (canvas_width, CANVAS_HEIGHT), BACKGROUND_COLOR)
        draw = ImageDraw.Draw(image)
        
        if song_data is None:
            # Create idle state image
            thumbnail = self._create_placeholder_thumbnail()
            image.paste(thumbnail, (0, 0))
            
            # Draw "No Song Playing" message - centered vertically in the text area
            font = self._get_font(48, bold=True)  # Even larger for full height layout
            text = "No Song Playing"
            bbox = font.getbbox(text)
            text_width = bbox[2] - bbox[0]
            text_area_width = canvas_width - TEXT_AREA_X - 20
            text_x = TEXT_AREA_X + (text_area_width - text_width) // 2
            # Center vertically in the available space
            vertical_center = CANVAS_HEIGHT // 2
            draw.text((text_x, vertical_center - 40), text, fill=TEXT_COLOR_PRIMARY, font=font)
            
            # Draw subtitle - also larger and positioned below main text
            subtitle_font = self._get_font(28)  # Larger subtitle
            subtitle = "Add a song to get started!"
            subtitle_bbox = subtitle_font.getbbox(subtitle)
            subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
            subtitle_x = TEXT_AREA_X + (text_area_width - subtitle_width) // 2
            draw.text((subtitle_x, vertical_center + 20), subtitle, fill=TEXT_COLOR_SECONDARY, font=subtitle_font)
            
        else:
            # Process thumbnail - add detailed logging
            logger.info(f"Processing song data: {song_data}")
            thumbnail_url = song_data.get('thumbnail')
            logger.info(f"Thumbnail URL from song data: {thumbnail_url}")
            
            if thumbnail_url:
                logger.info(f"Attempting to download thumbnail from: {thumbnail_url}")
                downloaded_thumbnail = await self._download_thumbnail(thumbnail_url)
                if downloaded_thumbnail:
                    logger.info(f"Successfully downloaded and processing thumbnail")
                    thumbnail = self._resize_thumbnail(downloaded_thumbnail)
                else:
                    logger.warning(f"Failed to download thumbnail, using placeholder")
                    thumbnail = self._create_placeholder_thumbnail()
            else:
                logger.warning(f"No thumbnail URL provided in song data, using placeholder")
                thumbnail = self._create_placeholder_thumbnail()
            
            # Paste thumbnail on the left
            image.paste(thumbnail, (0, 0))
            
            # Calculate text area width for this canvas
            text_area_width = canvas_width - TEXT_AREA_X - 20
            
            # Draw song title - larger for full height layout
            title = song_data.get('title', 'Unknown Title')
            title_font = self._get_font(36, bold=True)  # Larger title
            truncated_title = self._truncate_text(title, title_font, text_area_width)
            draw.text((TEXT_AREA_X, TITLE_Y), truncated_title, fill=TEXT_COLOR_PRIMARY, font=title_font)
            
            # Draw artist/uploader - larger font
            artist = song_data.get('uploader', song_data.get('channel', 'Unknown Artist'))
            artist_font = self._get_font(26)  # Larger artist text
            truncated_artist = self._truncate_text(artist, artist_font, text_area_width)
            draw.text((TEXT_AREA_X, ARTIST_Y), truncated_artist, fill=TEXT_COLOR_SECONDARY, font=artist_font)
            
            # Draw requester - larger font
            requester = song_data.get('requester_name', song_data.get('requester', 'Unknown'))
            requester_font = self._get_font(20)  # Larger requester text
            requester_text = f"Requested by {requester}"
            truncated_requester = self._truncate_text(requester_text, requester_font, text_area_width)
            draw.text((TEXT_AREA_X, REQUESTER_Y), truncated_requester, fill=TEXT_COLOR_SECONDARY, font=requester_font)
            
            # Draw "Added by" text - larger font
            added_by_font = self._get_font(18)  # Larger added by text
            added_by_text = f"Added by {requester}"
            truncated_added_by = self._truncate_text(added_by_text, added_by_font, text_area_width)
            draw.text((TEXT_AREA_X, ADDED_BY_Y), truncated_added_by, fill=TEXT_COLOR_SECONDARY, font=added_by_font)
            
            # Draw progress bar with timestamps above
            duration = song_data.get('duration', 0)
            if isinstance(duration, str):
                # Handle string durations
                try:
                    duration = int(float(duration))
                except (ValueError, TypeError):
                    duration = 0
            
            self._draw_progress_bar(draw, current_time, duration, canvas_width)
        
        # Save to BytesIO
        buffer = io.BytesIO()
        image.save(buffer, format='PNG', optimize=True)
        buffer.seek(0)
        
        return buffer


# Convenience function for easy import and usage
async def create_now_playing_image(song_data: Optional[Dict[str, Any]], 
                                 current_time: int = 0) -> io.BytesIO:
    """
    Convenience function to create a Now Playing image.
    
    Args:
        song_data: Dictionary containing song information
        current_time: Current playback position in seconds
        
    Returns:
        BytesIO buffer containing the generated PNG image
    """
    # Test logging to ensure it's working
    logger.info("=== IMAGE GENERATOR CALLED ===")
    logger.info(f"Creating Now Playing image with song_data={bool(song_data)}, current_time={current_time}")
    
    async with ImageGenerator() as generator:
        result = await generator.create_now_playing_image(song_data, current_time)
        logger.info(f"Image generation completed, buffer size: {len(result.getvalue())} bytes")
        return result