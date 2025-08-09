import subprocess

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
    'noplaylist': True,
    'postprocessors': [],
    'cachedir': False,
    'writethumbnail': False,
    'writesubtitles': False,
    'writeautomaticsub': False,
    'default_search': 'ytsearch',
    'ignoreerrors': True,
    'no_color': True
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
    'no_color': True
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
}

# Configuration FFMPEG - Modernized for improved stability
FFMPEG_OPTIONS = {
    'before_options': (
        '-reconnect 1 '
        '-reconnect_streamed 1 '
        '-reconnect_delay_max 5 '
        '-analyzeduration 0 '
        '-loglevel error '
        '-nostats '
    ),
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