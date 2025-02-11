import yt_dlp
import logging
from typing import Optional, Dict, Any, List
import asyncio
from functools import partial

logger = logging.getLogger(__name__)

class YouTubeError(Exception):
    """Custom exception for YouTube-related errors."""
    pass

class YouTubeUtils:
    """Utility class for YouTube operations."""
    
    def __init__(self):
        """Initialize the YouTube utility with default options."""
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'youtube_include_dash_manifest': True,  # Enable DASH manifest
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'opus',
                'preferredquality': '192',
            }],
            # Enhanced options for better compatibility
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],  # Try multiple clients
                    'player_skip': ['configs']  # Only skip configs
                }
            },
            'socket_timeout': 15,
            'retries': 5,  # Increase retries
            'geo_bypass': True,  # Try to bypass geo-restrictions
            'nocheckcertificate': True,  # Skip HTTPS certificate validation
        }
        
        # Search-specific options
        self.search_opts = {
            **self.ydl_opts,
            'default_search': 'ytsearch',
            'extract_flat': True,
        }
    
    async def extract_info(self, url: str) -> Dict[str, Any]:
        """
        Extract information about a YouTube video asynchronously.
        
        Args:
            url: The URL of the YouTube video
            
        Returns:
            Dict containing video information
            
        Raises:
            YouTubeError: If extraction fails
        """
        try:
            logger.info(f"Extracting info for URL: {url}")
            # Run yt-dlp in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            # Try with initial options
            try:
                with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                    extract_func = partial(ydl.extract_info, url, download=False)
                    info = await loop.run_in_executor(None, extract_func)
            except Exception as first_error:
                logger.warning(f"Failed first extraction attempt: {str(first_error)}")
                # Try with fallback options
                fallback_opts = {
                    **self.ydl_opts,
                    'format': 'bestaudio',  # Simplified format selection
                    'youtube_include_dash_manifest': False,
                    'extractor_args': {
                        'youtube': {
                            'player_client': ['android'],  # Only use android client
                            'player_skip': []  # Don't skip anything
                        }
                    }
                }
                
                with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                    extract_func = partial(ydl.extract_info, url, download=False)
                    info = await loop.run_in_executor(None, extract_func)
            
            if info is None:
                raise YouTubeError(f"Could not extract info for URL: {url}")
            
            # Try to get the best audio format
            formats = info.get('formats', [])
            audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
            
            # Get the best audio format or fallback to the default URL
            stream_url = None
            if audio_formats:
                best_audio = max(audio_formats, key=lambda f: f.get('abr', 0) or 0)
                stream_url = best_audio.get('url')
            
            result = {
                'title': info.get('title'),
                'duration': info.get('duration'),
                'stream_url': stream_url or info.get('url'),  # Fallback to default URL if needed
                'thumbnail': info.get('thumbnail'),
                'webpage_url': info.get('webpage_url'),
            }
            
            logger.info(f"Successfully extracted info for: {result['title']}")
            logger.info(f"Stream URL found: {bool(result['stream_url'])}")
            return result
        
        except Exception as e:
            logger.error(f"Error extracting YouTube info: {str(e)}", exc_info=True)
            raise YouTubeError(f"Failed to extract video info: {str(e)}")
    
    async def get_stream_url(self, url: str) -> Optional[str]:
        """
        Get just the stream URL for a YouTube video.
        
        Args:
            url: The URL of the YouTube video
            
        Returns:
            The direct stream URL or None if extraction fails
        """
        try:
            logger.info(f"Getting stream URL for: {url}")
            info = await self.extract_info(url)
            stream_url = info.get('stream_url')
            logger.info(f"Stream URL found: {bool(stream_url)}")
            return stream_url
        except Exception as e:
            logger.error(f"Error getting stream URL: {str(e)}", exc_info=True)
            return None
    
    async def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for YouTube videos.
        
        Args:
            query: Search query
            limit: Maximum number of results (default: 5)
            
        Returns:
            List of video information dictionaries
            
        Raises:
            YouTubeError: If search fails
        """
        try:
            # Prepare search query
            search_query = f"ytsearch{limit}:{query}"
            
            # Run search in thread pool
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(self.search_opts) as ydl:
                extract_func = partial(ydl.extract_info, search_query, download=False)
                results = await loop.run_in_executor(None, extract_func)
                
                if not results or 'entries' not in results:
                    raise YouTubeError(f"No results found for query: {query}")
                
                # Process search results
                videos = []
                for entry in results['entries']:
                    if entry:
                        videos.append({
                            'title': entry.get('title'),
                            'url': entry.get('url'),
                            'duration': entry.get('duration'),
                            'thumbnail': entry.get('thumbnail'),
                            'webpage_url': entry.get('webpage_url'),
                            'channel': entry.get('channel', entry.get('uploader')),
                        })
                
                return videos
                
        except Exception as e:
            logger.error(f"Error searching YouTube: {str(e)}")
            raise YouTubeError(f"Failed to search YouTube: {str(e)}")
    
    async def get_playlist_videos(self, playlist_url: str) -> List[Dict[str, Any]]:
        """
        Get videos from a YouTube playlist.
        
        Args:
            playlist_url: URL of the playlist
            
        Returns:
            List of video information dictionaries
            
        Raises:
            YouTubeError: If playlist extraction fails
        """
        try:
            # Configure options for playlist extraction
            playlist_opts = {
                **self.ydl_opts,
                'extract_flat': True,
            }
            
            # Extract playlist info
            loop = asyncio.get_event_loop()
            with yt_dlp.YoutubeDL(playlist_opts) as ydl:
                extract_func = partial(ydl.extract_info, playlist_url, download=False)
                results = await loop.run_in_executor(None, extract_func)
                
                if not results or 'entries' not in results:
                    raise YouTubeError(f"No videos found in playlist: {playlist_url}")
                
                # Process playlist entries
                videos = []
                for entry in results['entries']:
                    if entry:
                        videos.append({
                            'title': entry.get('title'),
                            'url': entry.get('url'),
                            'duration': entry.get('duration'),
                            'webpage_url': entry.get('webpage_url'),
                        })
                
                return videos
                
        except Exception as e:
            logger.error(f"Error extracting playlist: {str(e)}")
            raise YouTubeError(f"Failed to extract playlist: {str(e)}") 