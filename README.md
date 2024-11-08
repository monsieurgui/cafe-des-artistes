# Café des Artistes - Bot Musical Discord

Bot musical Discord développé spécifiquement pour le serveur Café des Artistes.

## Commandes

### Lecture
- `!p <lien/recherche>`: Joue une chanson ou ajoute à la queue
- `!skip`: Passe à la chanson suivante
- `!loop`: Active/désactive la lecture en boucle
- `!quit`: Arrête la musique et déconnecte le bot

### File d'attente
- `!queue`: Affiche les 10 prochaines chansons
- `!queue all`: Affiche toute la file d'attente
- `!purge`: Vide la file d'attente

### Administration
- `!cleanup`: Force le nettoyage des ressources (Admin uniquement)
- `!support <message>`: Envoie un message au support

## Configuration

1. Copier `config.template.yaml` vers `config.yaml`
2. Ajouter le token du bot dans `config.yaml`
3. Configurer les autres paramètres selon les besoins

## Déploiement

### Prérequis

- Python 3.11+
- FFmpeg
- Token du bot Discord

### Installation locale

1. Cloner le dépôt
2. Créer un environnement virtuel:

```bash
python -m venv venv
source venv/bin/activate # Linux/Mac
venv\Scripts\activate # Windows
```

3. Installer les dépendances:

```bash
pip install -r requirements.txt
```

4. Configurer le bot:

```bash
cp src/config/config.template.yaml src/config/config.yaml
```

5. Exécuter le bot:
```bash
python src/main.py
```

### Déploiement avec Docker

1. Configurer le bot:

```bash
cp src/config/config.template.yaml config.yaml
```

2. Construire et exécuter avec docker-compose:

```bash
docker-compose up -d
```

## Maintenance

### Logs
Les logs sont stockés dans le répertoire `logs/` lors de l'exécution avec Docker. Surveillez-les pour les problèmes.

### Gestion de la mémoire
Le bot se nettoie automatiquement:
- Après la lecture
- Après 30 minutes d'inactivité
- Avec des limites de mémoire lors de l'exécution dans Docker

### Limites de ressources Docker
Les limites de mémoire sont configurées dans docker-compose.yml:

```yaml
deploy:
resources:
limits:
memory: 512M
reservations:
memory: 256M
```

## Résolution des problèmes

1. **Le bot ne joue pas de musique**
   - Vérifiez que FFmpeg est installé
   - Vérifiez que le bot a les permissions appropriées
   - Vérifiez la connexion au canal vocal

2. **Utilisation excessive de la mémoire**
   - Vérifiez les logs pour les fuites de mémoire
   - Vérifiez que le nettoyage fonctionne
   - Ajustez les limites de mémoire Docker

3. **Problèmes de connexion**
   - Vérifiez la connectivité réseau
   - Vérifiez l'état de l'API Discord
   - Examinez les logs d'erreurs

## Contribution

1. Forker le dépôt
2. Créer une branche de fonctionnalité
3. Valider les modifications
4. Envoyer la branche
5. Créer une Pull Request

## Licence

Apache License 2.0

Copyright 2024 Guillaume Lévesque

Licencié sous la Licence Apache, Version 2.0 (la "Licence");
vous ne pouvez pas utiliser ce fichier excepté en conformité avec la Licence.
Vous pouvez obtenir une copie de la Licence à

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.