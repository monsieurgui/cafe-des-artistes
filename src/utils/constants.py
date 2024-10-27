# Configuration YT-DLP
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'opus',
    'noplaylist': True,  # Don't process playlists, only single videos
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'quiet': True,
    'no_warnings': True,
    'extract_flat': True,  # Only extract metadata initially
    'lazy_playlist': True,  # Only extract video information when needed
    'postprocessor_hooks': [],  # Reduce post-processing overhead
    'concurrent_fragment_downloads': 3,  # Download fragments concurrently
    'live_from_start': False,  # Don't download from start of livestreams
    'source_address': '0.0.0.0'  # Let system choose best interface
}

# Configuration FFMPEG
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -threads 3 -buffer_size 32768'
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
    'PLAYLIST_ADDED': "📑 Ajout a la queue",
    'SONGS_ADDED': "✅ {} chansons addées!",
    'SONG_ADDED': "✅ Ajoutée: {}",
    'ERROR_TITLE': "❌ Erreur",
    'GOODBYE': "On s'revoit bein tôt mon t'cham! 👋",
    'QUEUE_EMPTY': "La queue est vide. 🎵",
    'WAIT_MESSAGE': "⏰ Dans 30 minutes pas de son, chow",
    'QUEUE_EMPTY_SAD': "LLA queue est morte 😢",
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
    'QUEUE_PURGED': "Purge complete de la queue"
}