"""
Models module for TheStickerHouse application
"""

# Import main model functions for easy access
from .stickers_models import (
    create_sticker,
    get_sticker,
    get_stickers_by_user,
    get_public_stickers,
    update_sticker,
    delete_sticker,
    increment_usage_count,
    search_stickers_by_tags,
    get_stickers_by_category,
    get_recent_stickers
)

__all__ = [
    'create_sticker',
    'get_sticker',
    'get_stickers_by_user',
    'get_public_stickers',
    'update_sticker',
    'delete_sticker',
    'increment_usage_count',
    'search_stickers_by_tags',
    'get_stickers_by_category',
    'get_recent_stickers'
] 