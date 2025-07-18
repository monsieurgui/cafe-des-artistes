"""
Standardized Embed Templates for Cafe des Artistes Bot
=====================================================

This module provides consistent, standardized Discord embed templates
for all user-facing messages. It implements the messaging standard
defined in Epic 5, User Story 5.1.

Templates available:
- Success embeds (green with checkmark)
- Error embeds (red with cross/warning)  
- Informational embeds (blue with hourglass/info)
"""

import discord
from typing import Optional
from utils.constants import COLORS


def create_success_embed(title: Optional[str] = None, description: str = "", footer: Optional[str] = None) -> discord.Embed:
    """
    Create a standardized success embed with green color and checkmark.
    
    Args:
        title: Optional title for the embed. If None, uses checkmark as prefix
        description: Main message content (required)
        footer: Optional footer text
        
    Returns:
        discord.Embed: Success embed with green color (#2ecc71)
    """
    if title is None:
        title = "✅ Success"
    elif not title.startswith("✅"):
        title = f"✅ {title}"
    
    embed = discord.Embed(
        title=title,
        description=description,
        color=COLORS['SUCCESS']
    )
    
    if footer:
        embed.set_footer(text=footer)
    
    return embed


def create_error_embed(title: Optional[str] = None, description: str = "", footer: Optional[str] = None) -> discord.Embed:
    """
    Create a standardized error embed with red color and cross/warning.
    
    Args:
        title: Optional title for the embed. If None, uses cross as prefix
        description: Main message content (required)
        footer: Optional footer text
        
    Returns:
        discord.Embed: Error embed with red color (#e74c3c)
    """
    if title is None:
        title = "❌ Error"
    elif not title.startswith(("❌", "⚠️")):
        title = f"❌ {title}"
    
    embed = discord.Embed(
        title=title,
        description=description,
        color=COLORS['ERROR']
    )
    
    if footer:
        embed.set_footer(text=footer)
    
    return embed


def create_warning_embed(title: Optional[str] = None, description: str = "", footer: Optional[str] = None) -> discord.Embed:
    """
    Create a standardized warning embed with yellow color and warning sign.
    
    Args:
        title: Optional title for the embed. If None, uses warning as prefix
        description: Main message content (required)
        footer: Optional footer text
        
    Returns:
        discord.Embed: Warning embed with yellow color (#f1c40f)
    """
    if title is None:
        title = "⚠️ Warning"
    elif not title.startswith("⚠️"):
        title = f"⚠️ {title}"
    
    embed = discord.Embed(
        title=title,
        description=description,
        color=COLORS['WARNING']
    )
    
    if footer:
        embed.set_footer(text=footer)
    
    return embed


def create_info_embed(title: Optional[str] = None, description: str = "", footer: Optional[str] = None) -> discord.Embed:
    """
    Create a standardized informational embed with blue color and info/hourglass.
    
    Args:
        title: Optional title for the embed. If None, uses info as prefix
        description: Main message content (required)
        footer: Optional footer text
        
    Returns:
        discord.Embed: Informational embed with blue color (#3498db)
    """
    if title is None:
        title = "ℹ️ Information"
    elif not title.startswith(("ℹ️", "⏳")):
        title = f"ℹ️ {title}"
    
    embed = discord.Embed(
        title=title,
        description=description,
        color=COLORS['INFO']
    )
    
    if footer:
        embed.set_footer(text=footer)
    
    return embed


def create_loading_embed(title: Optional[str] = None, description: str = "", footer: Optional[str] = None) -> discord.Embed:
    """
    Create a standardized loading/waiting embed with blue color and hourglass.
    
    Args:
        title: Optional title for the embed. If None, uses hourglass as prefix
        description: Main message content (required)
        footer: Optional footer text
        
    Returns:
        discord.Embed: Loading embed with blue color (#3498db)
    """
    if title is None:
        title = "⏳ Loading"
    elif not title.startswith("⏳"):
        title = f"⏳ {title}"
    
    embed = discord.Embed(
        title=title,
        description=description,
        color=COLORS['INFO']
    )
    
    if footer:
        embed.set_footer(text=footer)
    
    return embed


# Convenience functions for common use cases
def success(message: str, footer: Optional[str] = None) -> discord.Embed:
    """Quick success embed with just a message."""
    return create_success_embed(description=message, footer=footer)


def error(message: str, footer: Optional[str] = None) -> discord.Embed:
    """Quick error embed with just a message."""
    return create_error_embed(description=message, footer=footer)


def warning(message: str, footer: Optional[str] = None) -> discord.Embed:
    """Quick warning embed with just a message."""
    return create_warning_embed(description=message, footer=footer)


def info(message: str, footer: Optional[str] = None) -> discord.Embed:
    """Quick info embed with just a message."""
    return create_info_embed(description=message, footer=footer)


def loading(message: str, footer: Optional[str] = None) -> discord.Embed:
    """Quick loading embed with just a message."""
    return create_loading_embed(description=message, footer=footer)