# Guide de Déploiement VPS

Ce guide explique comment déployer la pipeline Real-time Clickstream Analytics sur un VPS.

## Prérequis VPS

### Configuration minimale recommandée

| Ressource | Minimum | Recommandé |
|-----------|---------|------------|
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 Go | 8 Go |
| Stockage | 20 Go SSD | 40 Go SSD |
| OS | Ubuntu 22.04 LTS | Ubuntu 22.04 LTS |

### Providers recommandés

| Provider | Config 4vCPU/8GB | Lien |
|----------|------------------|------|
| Hetzner | ~7€/mois | [hetzner.com/cloud](https://www.hetzner.com/cloud) |
| OVH | ~12€/mois | [ovhcloud.com](https://www.ovhcloud.com/fr/vps/) |
| DigitalOcean | ~24$/mois | [digitalocean.com](https://www.digitalocean.com/pricing/droplets) |
| Vultr | ~24$/mois | [vultr.com](https://www.vultr.com/pricing/) |

---

## Déploiement rapide (Script automatisé)

### 1. Créer le VPS

Créez un VPS Ubuntu 22.04 chez le provider de votre choix.

### 2. Se connecter au VPS

```bash
ssh root@<IP_DU_VPS>
```

### 3. Lancer le script de déploiement

```bash
# Télécharger et exécuter le script
curl -fsSL https://raw.githubusercontent.com/<username>/realtime-clickstream-analytics/master/scripts/deploy.sh | bash
```

Ou manuellement :

```bash
# Cloner le repo
git clone https://github.com/<username>/realtime-clickstream-analytics.git
cd realtime-clickstream-analytics

# Lancer le déploiement
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

---

## Déploiement manuel (étape par étape)

### Étape 1 : Préparer le serveur

```bash
# Mettre à jour le système
apt update && apt upgrade -y

# Installer les dépendances
apt install -y curl git wget unzip

# Installer Docker
curl -fsSL https://get.docker.com | sh

# Ajouter l'utilisateur au groupe docker
usermod -aG docker $USER

# Installer Docker Compose plugin
apt install -y docker-compose-plugin

# Vérifier l'installation
docker --version
docker compose version
```

### Étape 2 : Configurer le swap (recommandé pour 4GB RAM)

```bash
# Créer un fichier swap de 4GB
fallocate -l 4G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile

# Rendre permanent
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# Optimiser le swap
echo 'vm.swappiness=10' >> /etc/sysctl.conf
sysctl -p
```

### Étape 3 : Cloner le projet

```bash
# Créer un utilisateur dédié (optionnel mais recommandé)
useradd -m -s /bin/bash clickstream
usermod -aG docker clickstream
su - clickstream

# Cloner le repo
git clone https://github.com/<username>/realtime-clickstream-analytics.git
cd realtime-clickstream-analytics
```

### Étape 4 : Télécharger le dataset

```bash
# Option 1 : Via Kaggle CLI
pip install kaggle
kaggle datasets download -d mkechinov/ecommerce-events-history-in-cosmetics-shop
unzip ecommerce-events-history-in-cosmetics-shop.zip -d data/raw/

# Option 2 : Dataset sample (plus petit, pour démo)
# Créer un sample de 100k lignes
head -100001 data/raw/2019-Oct.csv > data/raw/sample.csv
# Puis modifier config/config.yaml pour utiliser sample.csv
```

### Étape 5 : Configurer le firewall

```bash
# Installer ufw
apt install -y ufw

# Configurer les règles
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp      # HTTP
ufw allow 443/tcp     # HTTPS
ufw allow 8501/tcp    # Streamlit (temporaire, à retirer après config Nginx)

# Activer le firewall
ufw enable
```

### Étape 6 : Démarrer la pipeline

```bash
cd ~/realtime-clickstream-analytics

# Builder les images
make build

# Démarrer la pipeline complète
make pipeline

# Vérifier le statut
make status
```

### Étape 7 : Configurer Nginx (reverse proxy + HTTPS)

```bash
# Installer Nginx et Certbot
apt install -y nginx certbot python3-certbot-nginx

# Créer la configuration Nginx
cat > /etc/nginx/sites-available/clickstream << 'EOF'
server {
    listen 80;
    server_name votre-domaine.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
EOF

# Activer le site
ln -s /etc/nginx/sites-available/clickstream /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default

# Tester et recharger Nginx
nginx -t
systemctl reload nginx

# Configurer HTTPS avec Let's Encrypt
certbot --nginx -d votre-domaine.com
```

### Étape 8 : Configurer le démarrage automatique

```bash
# Créer un service systemd
cat > /etc/systemd/system/clickstream.service << 'EOF'
[Unit]
Description=Clickstream Analytics Pipeline
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
User=clickstream
WorkingDirectory=/home/clickstream/realtime-clickstream-analytics
ExecStart=/usr/bin/make pipeline
ExecStop=/usr/bin/make stop

[Install]
WantedBy=multi-user.target
EOF

# Activer le service
systemctl daemon-reload
systemctl enable clickstream
systemctl start clickstream
```

---

## Configuration DNS

1. Achetez un nom de domaine (ou utilisez un sous-domaine gratuit)
2. Configurez un enregistrement DNS :
   - Type : `A`
   - Nom : `@` ou `clickstream`
   - Valeur : `<IP_DU_VPS>`
   - TTL : 300

### Domaines gratuits

- [freenom.com](https://www.freenom.com) - .tk, .ml, .ga, .cf
- [duckdns.org](https://www.duckdns.org) - sous-domaines gratuits
- [noip.com](https://www.noip.com) - sous-domaines gratuits

---

## Optimisations pour la production

### Limiter les ressources Docker

Modifier `docker-compose.yml` :

```yaml
spark-streaming:
  # ...
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 3G
      reservations:
        cpus: '1'
        memory: 2G
```

### Réduire la fréquence du producer

Dans `config/config.yaml` :

```yaml
producer:
  message_delay: 0.1  # 10 events/sec au lieu de 100
```

### Utiliser un dataset sample

```bash
# Créer un fichier avec seulement 50k lignes
head -50001 data/raw/2019-Oct.csv > data/raw/sample.csv
```

Puis dans `config/config.yaml` :

```yaml
producer:
  csv_path: "/app/data/raw/sample.csv"
```

---

## Monitoring

### Voir les logs en temps réel

```bash
# Tous les services
make logs

# Service spécifique
make logs-spark
make logs-kafka
make logs-dashboard
```

### Vérifier l'utilisation des ressources

```bash
# Docker stats
docker stats

# Système
htop
free -h
df -h
```

### Redémarrer un service

```bash
# Redémarrer tout
make restart

# Redémarrer un service spécifique
docker compose restart spark-streaming
```

---

## Troubleshooting

### Le serveur manque de RAM

```bash
# Augmenter le swap
fallocate -l 8G /swapfile2
chmod 600 /swapfile2
mkswap /swapfile2
swapon /swapfile2
```

### Spark crash avec OOM

Réduire la mémoire Spark dans `docker-compose.yml` :

```yaml
spark-streaming:
  command: >
    /opt/spark/bin/spark-submit
    --master local[1]
    --conf spark.driver.memory=1g
    # ...
```

### Le dashboard ne se charge pas

```bash
# Vérifier les logs
docker logs streamlit

# Vérifier que le port est ouvert
curl localhost:8501

# Vérifier Nginx
nginx -t
systemctl status nginx
```

### Kafka ne démarre pas

```bash
# Vérifier les logs
docker logs kafka
docker logs zookeeper

# Redémarrer proprement
make clean
make start
```

---

## Coûts estimés

| Composant | Coût mensuel |
|-----------|--------------|
| VPS Hetzner CX31 (4vCPU/8GB) | ~7€ |
| Domaine .com | ~1€/mois (~12€/an) |
| **Total** | **~8€/mois** |

---

## Checklist de déploiement

- [ ] VPS créé et accessible via SSH
- [ ] Docker et Docker Compose installés
- [ ] Swap configuré (si RAM < 8GB)
- [ ] Projet cloné
- [ ] Dataset téléchargé
- [ ] Pipeline démarrée (`make pipeline`)
- [ ] Dashboard accessible sur le port 8501
- [ ] Nginx configuré
- [ ] HTTPS activé avec Let's Encrypt
- [ ] Service systemd créé pour démarrage auto
- [ ] Firewall configuré
