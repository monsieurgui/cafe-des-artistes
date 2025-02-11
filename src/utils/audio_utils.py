from typing import Optional, Tuple
import math

class AudioUtils:
    """Utility class for audio-related operations."""
    
    @staticmethod
    def format_duration(seconds: Optional[int]) -> str:
        """
        Format duration in seconds to a human-readable string.
        
        Args:
            seconds: Duration in seconds
            
        Returns:
            str: Formatted duration string (e.g., "3:45" or "1:23:45")
        """
        if seconds is None:
            return "LIVE"
            
        hours = math.floor(seconds / 3600)
        minutes = math.floor((seconds % 3600) / 60)
        seconds = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    
    @staticmethod
    def parse_duration(duration_str: str) -> Optional[int]:
        """
        Parse a duration string into seconds.
        
        Args:
            duration_str: Duration string (e.g., "3:45" or "1:23:45")
            
        Returns:
            int: Duration in seconds, or None if invalid format
        """
        try:
            parts = duration_str.split(':')
            if len(parts) == 2:  # MM:SS
                minutes, seconds = map(int, parts)
                return minutes * 60 + seconds
            elif len(parts) == 3:  # HH:MM:SS
                hours, minutes, seconds = map(int, parts)
                return hours * 3600 + minutes * 60 + seconds
        except (ValueError, TypeError):
            pass
        return None
    
    @staticmethod
    def format_progress(current: int, total: Optional[int], width: int = 20) -> str:
        """
        Create a progress bar string.
        
        Args:
            current: Current position in seconds
            total: Total duration in seconds
            width: Width of the progress bar
            
        Returns:
            str: Progress bar string
        """
        if total is None:
            return f"[{'=' * width}] LIVE"
            
        progress = min(current / total if total > 0 else 0, 1)
        filled = math.floor(width * progress)
        empty = width - filled
        
        bar = '=' * filled + '>' + '-' * (empty - 1)
        current_str = AudioUtils.format_duration(current)
        total_str = AudioUtils.format_duration(total)
        
        return f"[{bar}] {current_str}/{total_str}"
    
    @staticmethod
    def get_volume_info(volume: float) -> Tuple[str, int]:
        """
        Get volume bar and percentage.
        
        Args:
            volume: Volume level (0.0 to 2.0)
            
        Returns:
            Tuple[str, int]: (Volume bar, Volume percentage)
        """
        volume = max(0.0, min(2.0, volume))
        percentage = int(volume * 100)
        
        bars = '█' * int((percentage / 200) * 10)
        dots = '▒' * (10 - len(bars))
        
        return f"{bars}{dots}", percentage 