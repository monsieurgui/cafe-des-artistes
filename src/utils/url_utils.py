import re
from typing import Optional
from urllib.parse import urlparse, parse_qs

class URLUtils:
    """Utility class for handling URLs."""
    
    # YouTube URL patterns
    YOUTUBE_PATTERNS = [
        r'^https?://(?:www\.)?youtube\.com/watch\?(?=.*v=\w+)(?:\S+)?$',  # Standard YouTube URLs
        r'^https?://(?:www\.)?youtube\.com/playlist\?(?=.*list=\w+)(?:\S+)?$',  # Playlist URLs
        r'^https?://youtu\.be/[\w-]+(?:\?.*)?$',  # Short YouTube URLs
        r'^https?://(?:www\.)?youtube\.com/shorts/[\w-]+(?:\?.*)?$',  # YouTube Shorts URLs
        r'^https?://(?:www\.)?youtube\.com/v/[\w-]+(?:\?.*)?$'  # Alternative YouTube URLs
    ]
    
    @classmethod
    def is_youtube_url(cls, url: str) -> bool:
        """
        Check if a URL is a valid YouTube URL.
        
        Args:
            url: The URL to check
            
        Returns:
            bool: True if the URL is a valid YouTube URL, False otherwise
        """
        # Log the URL being checked
        print(f"Checking URL: {url}")  # Temporary debug print
        result = any(re.match(pattern, url) for pattern in cls.YOUTUBE_PATTERNS)
        print(f"URL validation result: {result}")  # Temporary debug print
        return result
    
    @classmethod
    def extract_video_id(cls, url: str) -> Optional[str]:
        """
        Extract the video ID from a YouTube URL.
        
        Args:
            url: The YouTube URL
            
        Returns:
            str: The video ID if found, None otherwise
        """
        if not cls.is_youtube_url(url):
            return None
            
        parsed_url = urlparse(url)
        
        if parsed_url.hostname in ('youtu.be', 'youtube.com'):
            if parsed_url.hostname == 'youtu.be':
                return parsed_url.path[1:]
            elif 'shorts' in parsed_url.path:
                return parsed_url.path.split('/')[-1].split('?')[0]
            else:
                query = parse_qs(parsed_url.query)
                return query.get('v', [None])[0]
        
        return None
    
    @classmethod
    def is_playlist(cls, url: str) -> bool:
        """
        Check if a URL is a YouTube playlist.
        
        Args:
            url: The URL to check
            
        Returns:
            bool: True if the URL is a playlist, False otherwise
        """
        if not cls.is_youtube_url(url):
            return False
            
        parsed_url = urlparse(url)
        query = parse_qs(parsed_url.query)
        return 'list' in query
    
    @classmethod
    def extract_playlist_id(cls, url: str) -> Optional[str]:
        """
        Extract the playlist ID from a YouTube URL.
        
        Args:
            url: The YouTube URL
            
        Returns:
            str: The playlist ID if found, None otherwise
        """
        if not cls.is_playlist(url):
            return None
            
        parsed_url = urlparse(url)
        query = parse_qs(parsed_url.query)
        return query.get('list', [None])[0] 