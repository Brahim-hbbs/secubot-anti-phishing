# SecuBot : bot Discord anti-phishing

Bot Discord de sécurité qui **détecte les liens de phishing**, les supprime automatiquement et envoie une alerte dans un salon réservé à la modération. Il signale aussi les messages contenant des mots-clés typiques d'arnaques.

Projet personnel réalisé dans le cadre de ma reconversion en administration systèmes, réseaux et cybersécurité.

## Fonctionnalités

| Fonction | Détail |
|---|---|
| **Détection de phishing** | Compare chaque lien posté à une liste de plus de 43 000 domaines de phishing connus. Le message est supprimé et une alerte rouge est envoyée dans le salon de logs. |
| **Mots-clés sensibles** | Alerte orange (sans suppression) quand un message contient des termes comme « free nitro » ou « gagner de l'argent ». |
| **Badge vendeur vérifié** | Un rôle configurable par serveur ; la commande `/vendeur` indique si un membre le possède. |
| **Configuration par serveur** | Chaque serveur choisit son salon de logs et son rôle vendeur (stockés en SQLite). |

### Commandes

| Commande | Qui peut l'utiliser | Rôle |
|---|---|---|
| `/config_logs` | Administrateurs | Choisit le salon où arrivent les alertes |
| `/config_role` | Administrateurs | Choisit le rôle « vendeur vérifié » |
| `/vendeur` | Tout le monde | Vérifie si un membre est vendeur vérifié |

## Comment fonctionne la détection

1. Au démarrage, puis **toutes les 6 heures**, le bot télécharge la liste des domaines de phishing fournie par l'API publique [FishFish](https://api.fishfish.gg/v1).
2. Pour chaque message, il extrait les noms de domaine (avec ou sans `https://`) et les compare à la liste, y compris les domaines parents (`a.exemple.com` puis `exemple.com`).
3. Une courte liste de domaines fiables (`discord.com`, `github.com`, etc.) n'est jamais signalée.

La comparaison se fait **en local** : les messages des membres ne sont jamais envoyés à un service externe, seule la liste est téléchargée.

## Prérequis

- Python 3 récent (testé avec Python 3.14)
- Un compte Discord et un serveur de test

## Créer le bot sur Discord

1. Va sur le [Discord Developer Portal](https://discord.com/developers/applications) et clique sur **New Application**.
2. Dans l'onglet **Bot**, clique sur **Reset Token** et copie le token (il ne s'affiche qu'une fois).
3. Toujours dans l'onglet **Bot**, active **Message Content Intent** (obligatoire pour lire les messages).
4. Dans **OAuth2 → URL Generator**, coche les scopes `bot` et `applications.commands`.
5. Coche les permissions : *Voir les salons*, *Envoyer des messages*, *Intégrer des liens*, *Gérer les messages* (nécessaire pour supprimer les liens dangereux).
6. Ouvre l'URL générée pour inviter le bot sur ton serveur.

## Installation

Dans PowerShell :

```powershell
git clone https://github.com/Brahim-hbbs/secubot-anti-phishing.git
cd secubot-anti-phishing
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Ouvre ensuite le fichier `.env` et remplace `votre_token_ici` par ton token. **Ne partage jamais ce fichier** : il est exclu de Git par le `.gitignore`.

Lance le bot :

```powershell
python Bot.py
```

Tu dois voir dans la console : « Bot connecté », « Liste de phishing chargée » et « commande(s) Slash synchronisée(s) ».

Sur Discord, tape `/config_logs` pour choisir le salon d'alertes.

## Sécurité

- Le token est lu depuis un fichier `.env` (ou une variable d'environnement sur l'hébergeur), jamais écrit dans le code.
- Le bot demande le minimum de permissions et n'utilise pas l'intent « membres ».
- Les commandes de configuration sont réservées aux administrateurs et ne fonctionnent pas en message privé.

## Limites connues

- La détection repose sur une liste de domaines **déjà connus** : un site de phishing très récent peut passer entre les mailles.
- Les liens raccourcis (type bit.ly) ne sont pas suivis.
- Les alertes par mots-clés peuvent provoquer de fausses alertes (le mot « gratuit » est très courant).
- La liste vient d'un service tiers : si FishFish est indisponible au démarrage, la détection de phishing est inactive jusqu'au prochain rafraîchissement réussi.
- La base SQLite est stockée localement : sur un hébergeur sans stockage persistant, la configuration peut être perdue au redémarrage.

## Ce que j'ai appris

- Développer un bot avec `discord.py` : événements, commandes slash, permissions, intents.
- Stocker une configuration par serveur avec SQLite.
- Récupérer et mettre à jour des données externes avec `aiohttp` et une tâche planifiée.
- Gérer les secrets : fichier `.env`, `.gitignore`, régénération d'un token.
- Relire et tester son propre code : j'ai découvert que l'API que j'utilisais au départ n'existait pas, et je l'ai remplacée par une source documentée.

## Améliorations prévues

- Hébergement 24h/24
- Sanctions automatiques configurables (exclusion temporaire)
- Liste de domaines autorisés modifiable par serveur
- Résolution des liens raccourcis

## Crédits

Données de phishing : [FishFish](https://fishfish.gg).