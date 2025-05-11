import subprocess

# Configuration YT-DLP
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'skip_download': True,
    'force_generic_extractor': False,
    'socket_timeout': 2,
    'retries': 1,
    'nocheckcertificate': True,
    'noplaylist': True,
    'concurrent_fragment_downloads': 1,
    'buffersize': 32768,
    'postprocessors': [],
    'cachedir': False,
    'writethumbnail': False,
    'writesubtitles': False,
    'writeautomaticsub': False,
    'get_duration': True,
    'extract_metadata': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'ignoreerrors': True,
    'no_color': True,
    'extract_flat': 'in_playlist'
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
    'format': 'bestaudio[ext=m4a]/bestaudio/best[ext=mp4]/best',
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'quiet': True,
    'no_warnings': True,
    'extract_flat': False,
    'lazy_playlist': False,
    'postprocessor_hooks': [],
    'concurrent_fragment_downloads': 3,
    'live_from_start': True,
    'wait_for_video': True,
    'source_address': '0.0.0.0',
    'is_live': True,
    'live_buffer': 1800,
}

# Configuration FFMPEG
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -analyzeduration 0 -probesize 32000 -thread_queue_size 4096',
    'options': '-vn -ar 48000 -ac 2 -f s16le -acodec pcm_s16le -flags low_delay -threads 1'
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