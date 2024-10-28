# Configuration YT-DLP
YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',  # Changé de opus à mp3 pour une meilleure compatibilité
    'noplaylist': True,  # Ne traite pas les playlists, uniquement les vidéos individuelles
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'quiet': True,
    'no_warnings': True,
    'extract_flat': True,  # Extrait uniquement les métadonnées initialement
    'lazy_playlist': True,  # Extrait les informations vidéo uniquement quand nécessaire
    'postprocessor_hooks': [],  # Réduit la charge du post-traitement
    'concurrent_fragment_downloads': 3,  # Télécharge les fragments simultanément
    'live_from_start': False,  # Ne télécharge pas depuis le début des diffusions en direct
    'source_address': '0.0.0.0',  # Laisse le système choisir la meilleure interface
    'preferredcodec': 'mp3',  # Codec préféré ajouté
    'preferredquality': '192'  # Paramètre de qualité ajouté
}

# Configuration FFMPEG
FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn -ar 48000 -ac 2 -f s16le -acodec pcm_s16le'  # Options mises à jour pour une meilleure compatibilité
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
    'QUEUE_PURGED': "Purge complete de la queue",
    'LOOP_ENABLED': "🔁 En boucle : {}",
    'LOOP_DISABLED': "➡️ Mode boucle désactivé",
    'LOOP_SINCE': "Depuis : {}",
    'LOOP_BY': "Loop initié par : {}",
    'PLAYLIST_ERROR': "Impossible de mettre une liste de lecture en boucle. Veuillez fournir un lien vers une seule vidéo."
}
