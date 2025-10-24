import subprocess

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

DEFAULT_HTTP_HEADERS = {
    'User-Agent': DEFAULT_USER_AGENT,
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': '*/*',
    'Referer': 'https://www.youtube.com/'
}

YOUTUBE_EXTRACTOR_ARGS = {
    'youtube': {
        'player_client': ['android'],
    }
}

# Configuration YT-DLP - Modernized and reduced to valid, stable options
YTDL_OPTIONS = {
    'format': 'bestaudio[acodec=opus]/bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'skip_download': True,
    'extract_flat': False,
    'nocheckcertificate': False,
    'prefer_free_formats': True,
    'socket_timeout': 30,
    'retries': 5,
    'noplaylist': False,  # Allow playlists
    'postprocessors': [],
    'cachedir': False,
    'writethumbnail': False,
    'writesubtitles': False,
    'writeautomaticsub': False,
    'default_search': 'ytsearch',
    'ignoreerrors': True,
    'no_color': True,
    'user_agent': DEFAULT_USER_AGENT,
    'http_headers': DEFAULT_HTTP_HEADERS,
    'force_ipv4': True,
    'extractor_args': YOUTUBE_EXTRACTOR_ARGS,
}

# Configuration YT-DLP pour le téléchargement
YTDL_DOWNLOAD_OPTIONS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'outtmpl': '%(id)s.%(ext)s',  # Format du nom de fichier
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
    'nocheckcertificate': True,
    'ignoreerrors': True,
    'no_color': True,
    'user_agent': DEFAULT_USER_AGENT,
    'http_headers': DEFAULT_HTTP_HEADERS,
    'force_ipv4': True,
    'extractor_args': YOUTUBE_EXTRACTOR_ARGS,
}

YTDL_OPTIONS_LIVE = {
    'format': 'bestaudio[acodec=opus]/bestaudio[ext=m4a]/bestaudio/best[ext=mp4]/best',
    'noplaylist': True,
    'nocheckcertificate': False,
    'prefer_free_formats': True,
    'ignoreerrors': False,
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'lazy_playlist': False,
    'postprocessor_hooks': [],
    'socket_timeout': 30,
    'retries': 5,
    'user_agent': DEFAULT_USER_AGENT,
    'http_headers': DEFAULT_HTTP_HEADERS,
    'force_ipv4': True,
    'extractor_args': YOUTUBE_EXTRACTOR_ARGS,
}

# Configuration FFMPEG - Modernized for improved stability
FFMPEG_HEADERS = ''.join([
    f"User-Agent: {DEFAULT_USER_AGENT}\r\n",
    'Accept: */*\r\n',
    'Accept-Language: en-US,en;q=0.9\r\n',
    'Referer: https://www.youtube.com/\r\n',
])

FFMPEG_OPTIONS = {
    'before_options': (
        '-reconnect 1 '
        '-reconnect_streamed 1 '
        '-reconnect_delay_max 5 '
        '-user_agent "{user_agent}" '
        '-headers "{headers}" '
        '-protocol_whitelist "file,http,https,tcp,tls" '
        '-nostdin '
        '-loglevel error '
        '-nostats '
    ).format(user_agent=DEFAULT_USER_AGENT, headers=FFMPEG_HEADERS),
    'options': '-vn'
}

# Couleurs des Embeds Discord
COLORS = {
    'SUCCESS': 0x2ecc71,  # Vert
    'ERROR': 0xe74c3c,    # Rouge
    'WARNING': 0xf1c40f,  # Jaune
    'INFO': 0x3498db      # Bleu
}

# Messages du bot
MESSAGES = {
    'PLAYLIST_ADDED': "✅ {} tounes ajoutées à la queue",
    'SONGS_ADDED': "✅ {total} chansons ajoutées à la file d'attente",
    'SONG_ADDED': "✅ {title} ajoutée à la queue ({queue_size} dans la queue)",
    'ERROR_TITLE': "❌ Erreur",
    'GOODBYE': "On s'revoit bein tôt mon t'cham! 👋",
    'QUEUE_EMPTY': "La queue est vide. 🎵",
    'WAIT_MESSAGE': "⏰ Dans 30 minutes pas de son, chow",
    'QUEUE_EMPTY_SAD': "La queue est dead 😢",
    'NOW_PLAYING': "🎵 En lecture",
    'NEXT_SONGS': "Prochaine chanson",
    'REMAINING_SONGS': "+{} autres chanzons en attente",
    'SUPPORT_TITLE': "🆘 Demande de Support",
    'SUPPORT_SENT': "✅ Votre message a été envoyé au god du bot!",
    'DM_ERROR': "Je ne peux pas vous envoyer de messages privés. Veuillez activer les messages privés pour ce serveur.",
    'SUPPORT_ERROR': "Impossible d'envoyer le message de support. Veuillez réessayer plus tard.",
    'VOICE_CHANNEL_REQUIRED': "Ça prend un channel",
    'NOTHING_PLAYING': "Rian joue mon'homme",
    'SKIPPED': "Skippé",
    'QUEUE_PURGED': "Purge complete de la queue",
    'LOOP_ENABLED': "🔁 En boucle : {}",
    'LOOP_DISABLED': "➡️ Mode boucle désactivé",
    'LOOP_SINCE': "Depuis : {}",
    'LOOP_BY': "Loop initié par : {}",
    'PLAYLIST_ERROR': "Impossible de mettre une liste de lecture en boucle. Veuillez fournir un lien vers une seule vidéo.",
    'CLEANUP_START': "🧹 Nettoyage en cours...",
    'CLEANUP_COMPLETE': "✨ Nettoyage complet effectué!",
    'CLEANUP_ERROR': "Erreur lors du nettoyage: {}",
    'LIVE_STARTED': "🔴 Diffusion en direct démarrée",
    'LIVE_STOPPED': "⭕ Diffusion en direct arrêtée",
    'LIVE_ERROR': "❌ Erreur lors du chargement du direct",
    'LIVE_NOT_FOUND': "❌ Aucune diffusion en direct trouvée",
    'PLAYBACK_STOPPED': '⏹️ Lecture arrêtée',
    'VIDEO_UNAVAILABLE': "❌ Cette vidéo n'est pas disponible",
    'LELIM_LOADING': "⏳ Chargement de la playlist Lelim...",
    'LELIM_ERROR': "❌ Erreur lors du chargement de la playlist Lelim",
    'LELIM_DOWNLOADING': "⏳ Téléchargement des chansons Lelim en cours...",
    'LELIM_DOWNLOAD_COMPLETE': "✅ Téléchargement des chansons Lelim terminé",
    'LELIM_DOWNLOAD_ERROR': "❌ Erreur lors du téléchargement des chansons Lelim: {}",
    'LELIM_MENU_EXPIRED': "⏰ Menu expiré. Utilisez à nouveau la commande `!lelim` pour afficher le menu."
}

# URL de la playlist Lelim
LELIM_PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLjJXgtuafBUV2FsqKE5RWdF1NTXIdSoBw"

# Chemin du dossier de cache pour les chansons Lelim
LELIM_CACHE_DIR = "cache/lelim"