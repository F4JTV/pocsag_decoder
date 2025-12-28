# POCSAG Decoder

Application web Django pour la réception et le décodage de trames POCSAG en temps réel à l'aide d'un récepteur RTL-SDR et de multimon-ng.

## Fonctionnalités

- 📡 Réception en temps réel des messages POCSAG (512, 1200, 2400 bauds)
- 🔍 Filtrage par RIC (adresse), date et contenu du message
- 🔄 Déduplication automatique des messages répétés
- 🌙 Mode sombre / clair
- 📊 Interface web responsive avec mise à jour automatique (HTMX)
- ⚙️ Configuration flexible (fréquence, gain, bias-t)

## Prérequis

### Matériel

- Clé RTL-SDR (RTL2832U)
- Antenne adaptée à la fréquence POCSAG cible

### Logiciels

- Python 3.10+
- rtl-sdr
- multimon-ng

### Installation des dépendances système (Debian/Ubuntu)

```bash
sudo apt update
sudo apt install rtl-sdr multimon-ng
```

### Installation des dépendances système (Arch Linux)

```bash
sudo pacman -S rtl-sdr multimon-ng
```

## Installation

### 1. Cloner le dépôt

```bash
git clone https://github.com/F4JTV/pocsag_decoder.git
cd pocsag_decoder
```

### 2. Créer un environnement virtuel

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# ou
venv\Scripts\activate     # Windows
```

### 3. Installer les dépendances Python

```bash
pip install -r requirements.txt
```

### 4. Initialiser la base de données

```bash
python manage.py migrate
```

### 5. (Optionnel) Créer un superutilisateur

```bash
python manage.py createsuperuser
```

## Utilisation

### Démarrer le serveur web

```bash
python manage.py runserver 0.0.0.0:8000
```

L'interface est accessible à l'adresse : http://localhost:8000

### Démarrer l'écoute POCSAG

Dans un autre terminal :

```bash
python manage.py listen_pocsag
```

#### Options disponibles

| Option | Court | Description | Défaut |
|--------|-------|-------------|--------|
| `--frequency` | `-f` | Fréquence d'écoute | 173.5125M |
| `--gain` | `-g` | Gain RTL-SDR (dB) | 49.6 |
| `--bias-t` | `-T` | Activer le bias-t | Désactivé |
| `--sample-rate` | `-s` | Taux d'échantillonnage (Hz) | 22050 |
| `--dedupe-minutes` | `-d` | Intervalle de déduplication (min) | 3 |
| `--pocsag-rates` | | Débits POCSAG à décoder | 512,1200,2400 |

#### Exemples

```bash
# Configuration par défaut
python manage.py listen_pocsag

# Fréquence personnalisée avec gain ajusté
python manage.py listen_pocsag -f 466.075M -g 40

# Activer le bias-t pour antenne active
python manage.py listen_pocsag -T

# Déduplication à 5 minutes
python manage.py listen_pocsag -d 5

# Configuration complète
python manage.py listen_pocsag -f 466.025M -g 42 -T -d 10 --pocsag-rates 512,1200
```

## Commandes de maintenance

### Vider la base de données

```bash
# Supprimer tous les messages (avec confirmation)
python manage.py clear_messages

# Supprimer sans confirmation
python manage.py clear_messages -y

# Garder les 100 messages les plus récents
python manage.py clear_messages --keep-recent 100

# Supprimer les messages de plus de 7 jours
python manage.py clear_messages --older-than 7

# Combiner les options
python manage.py clear_messages --older-than 30 --keep-recent 50 -y
```

## Structure du projet

```
pocsag_decoder/
├── decoder/
│   ├── management/
│   │   └── commands/
│   │       ├── listen_pocsag.py    # Commande d'écoute RTL-SDR
│   │       └── clear_messages.py   # Commande de purge
│   ├── migrations/
│   ├── templates/
│   │   └── decoder/
│   │       └── index.html          # Interface web
│   ├── admin.py
│   ├── apps.py
│   ├── models.py                   # Modèles PocsagMessage, ListenerStatus
│   ├── urls.py
│   └── views.py
├── pocsag_project/
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── manage.py
├── requirements.txt
└── README.md
```

## Configuration pour la production

### 1. Modifier les paramètres de sécurité

Dans `pocsag_project/settings.py` :

```python
DEBUG = False
SECRET_KEY = 'votre-clé-secrète-générée'
ALLOWED_HOSTS = ['votre-domaine.com', 'votre-ip']
```

### 2. Utiliser Gunicorn

```bash
pip install gunicorn
gunicorn pocsag_project.wsgi:application -b 0.0.0.0:8000
```

### 3. Service systemd (optionnel)

Créer `/etc/systemd/system/pocsag-web.service` :

```ini
[Unit]
Description=POCSAG Decoder Web
After=network.target

[Service]
User=votre-utilisateur
WorkingDirectory=/chemin/vers/pocsag_decoder
ExecStart=/chemin/vers/venv/bin/gunicorn pocsag_project.wsgi:application -b 127.0.0.1:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Créer `/etc/systemd/system/pocsag-listener.service` :

```ini
[Unit]
Description=POCSAG Listener
After=network.target

[Service]
User=votre-utilisateur
WorkingDirectory=/chemin/vers/pocsag_decoder
ExecStart=/chemin/vers/venv/bin/python manage.py listen_pocsag -f 173.5125M -g 49.6
Restart=always

[Install]
WantedBy=multi-user.target
```

Activer les services :

```bash
sudo systemctl enable pocsag-web pocsag-listener
sudo systemctl start pocsag-web pocsag-listener
```

## Dépannage

### Erreur "rtl_fm: command not found"

Installer rtl-sdr :
```bash
sudo apt install rtl-sdr
```

### Erreur "usb_claim_interface error -6"

Le périphérique est utilisé par un autre processus. Débrancher et rebrancher la clé RTL-SDR, ou :
```bash
sudo rmmod dvb_usb_rtl28xxu rtl2832
```

### Pas de messages reçus

1. Vérifier la fréquence POCSAG locale
2. Ajuster le gain (`-g`)
3. Vérifier l'antenne et sa connexion
4. Tester avec `rtl_test` pour vérifier le matériel

## Licence

Ce projet est sous licence MIT. Voir le fichier [LICENSE](LICENSE) pour plus de détails.

## Remerciements

- [multimon-ng](https://github.com/EliasOeworblmh/multimon-ng) - Décodeur multi-protocole
- [rtl-sdr](https://osmocom.org/projects/rtl-sdr/wiki) - Pilotes RTL-SDR
- [HTMX](https://htmx.org/) - Interactivité sans JavaScript complexe
- [Bootstrap](https://getbootstrap.com/) - Framework CSS
