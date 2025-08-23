import datetime
from typing import Optional

try:
    from pyfiglet import Figlet
except Exception:  # pragma: no cover - safe import guard
    Figlet = None  # type: ignore


def render_ascii_time(now: Optional[datetime.datetime] = None, font: str = "small") -> str:
    """
    Render current time as ASCII art in HH:MM:SS using a compact font.

    Args:
        now: Optional datetime to render. Defaults to local wall-clock now.
        font: PyFiglet font name. Defaults to a compact, readable font.

    Returns:
        ASCII art string representing the time.
    """
    current = now or datetime.datetime.now()
    time_str = current.strftime("%H:%M:%S")

    if Figlet is None:
        # Fallback if pyfiglet is unavailable
        return time_str

    try:
        fig = Figlet(font=font, width=80)
        return fig.renderText(time_str).rstrip()
    except Exception:
        # Fallback to default font if specified font fails
        try:
            fig = Figlet(width=80)
            return fig.renderText(time_str).rstrip()
        except Exception:
            return time_str


