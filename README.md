# Real-time Clickstream Analytics

**Business problem.** E-commerce teams usually see yesterday's funnel. When a product page breaks or a campaign drives traffic that does not convert, they find out a day late. The goal: views, add-to-carts, purchases and revenue per product, updated within seconds.

**Key result.** A local streaming pipeline that replays a real cosmetics-shop event log (view, cart, remove_from_cart, purchase) through Kafka. Spark Structured Streaming computes 1-minute windows (30 s slide) and 5-minute windows (1 min slide), a view → cart → purchase funnel and top products by views, purchases and revenue, written to Delta Lake and shown in an auto-refreshing Streamlit dashboard.

TODO(arnaud): add measured throughput and end-to-end latency (none are recorded in the repo).

**Stack.** Apache Kafka + Zookeeper, PySpark 3.5 Structured Streaming, Delta Lake 3.1, Streamlit + Plotly, Docker Compose.

**How to run.**
```bash
# download the Kaggle "eCommerce Events History in Cosmetics Shop" CSVs into data/raw/
make pipeline          # starts Kafka, Spark job, producer and dashboard
# dashboard: http://localhost:8501 · Spark UI: http://localhost:4040
make stop
```

---

## Apercu

Ce projet implémente une pipeline complète de streaming analytics qui :
- Ingère des événements clickstream en temps réel via Kafka
- Traite et agrège les données avec Spark Structured Streaming
- Stocke les résultats dans Delta Lake
- Visualise les métriques dans un dashboard Streamlit avec auto-refresh

### Use Case Business

> "En tant qu'analyste e-commerce, je veux voir en temps réel le comportement des utilisateurs sur mon site (sessions actives, pages vues, conversions, funnel) pour détecter rapidement les anomalies et optimiser l'expérience."

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────────┐     ┌─────────────┐     ┌───────────────┐
│   Dataset   │────▶│    Kafka    │────▶│   Spark Streaming   │────▶│  Delta Lake │────▶│   Streamlit   │
│    (CSV)    │     │   Producer  │     │   (PySpark)         │     │  (Parquet)  │     │   Dashboard   │
└─────────────┘     └─────────────┘     └─────────────────────┘     └─────────────┘     └───────────────┘
                           │                      │
                           ▼                      ▼
                    ┌─────────────┐        ┌─────────────┐
                    │    Kafka    │        │  Spark UI   │
                    │   Broker    │        │  :4040      │
                    └─────────────┘        └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │  Zookeeper  │
                    └─────────────┘
```

## Stack Technique

| Composant | Technologie | Version |
|-----------|-------------|---------|
| Message Broker | Apache Kafka | Latest |
| Coordination | Zookeeper | Latest |
| Stream Processing | PySpark Structured Streaming | 3.5.0 |
| Storage | Delta Lake | 3.1.0 |
| Dashboard | Streamlit | 1.31.0 |
| Visualisation | Plotly | 5.18.0 |
| Orchestration | Docker Compose | v2 |

## Prérequis

- Docker & Docker Compose v2
- ~6-8 Go de RAM disponible pour Docker
- ~3 Go d'espace disque pour le dataset et les données

## Dataset

Ce projet utilise le dataset Kaggle **"eCommerce Events History in Cosmetics Shop"** :

- **Source** : [Kaggle](https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop)
- **Taille** : ~2.3 Go (5 fichiers CSV)
- **Période** : Octobre 2019 - Février 2020
- **Events** : view, cart, remove_from_cart, purchase

### Structure des données

| Colonne | Type | Description |
|---------|------|-------------|
| event_time | timestamp | Date/heure de l'événement |
| event_type | string | Type : view, cart, purchase |
| product_id | string | ID du produit |
| category_id | string | ID de la catégorie |
| category_code | string | Code catégorie (ex: electronics.smartphone) |
| brand | string | Marque du produit |
| price | float | Prix en USD |
| user_id | string | ID utilisateur |
| user_session | string | ID de session |

## Installation

### 1. Cloner le projet

```bash
git clone <repo-url>
cd realtime-clickstream-analytics
```

### 2. Télécharger le dataset

1. Téléchargez depuis [Kaggle](https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop)
2. Extrayez dans `data/raw/`

```bash
unzip ecommerce-events-history-in-cosmetics-shop.zip -d data/raw/
```

### 3. Démarrer la pipeline

```bash
# Démarrer l'infrastructure (Kafka + Zookeeper)
make start

# Dans un terminal : démarrer le streaming Spark
make streaming

# Dans un autre terminal : démarrer le producer
make producer

# Dans un autre terminal : démarrer le dashboard
make dashboard
```

### 4. Accéder aux interfaces

| Service | URL |
|---------|-----|
| Dashboard Streamlit | http://localhost:8501 |
| Spark UI | http://localhost:4040 |

## Commandes Make

```bash
make help           # Afficher l'aide complète

# Infrastructure
make start          # Démarrer Kafka + Zookeeper
make stop           # Arrêter tous les services
make restart        # Redémarrer tous les services
make status         # Voir l'état des containers
make logs           # Suivre les logs de tous les services
make clean          # Nettoyer tout (containers + données Delta)

# Applications
make producer       # Lancer le Kafka Producer
make streaming      # Lancer le job Spark Streaming
make dashboard      # Lancer le dashboard Streamlit

# Utilitaires
make test-kafka     # Tester la connectivité Kafka
make setup-topic    # Créer le topic Kafka manuellement
make consume        # Consommer les messages (debug)
```

## Structure du Projet

```
realtime-clickstream-analytics/
├── docker-compose.yml          # Orchestration des services
├── Makefile                    # Commandes utilitaires
├── README.md                   # Documentation
├── requirements.txt            # Dépendances Python
├── .gitignore                  # Fichiers ignorés par Git
│
├── docker/
│   ├── producer/
│   │   └── Dockerfile          # Image pour le Kafka Producer
│   └── streamlit/
│       └── Dockerfile          # Image pour le Dashboard
│
├── src/
│   ├── producer/
│   │   └── kafka_producer.py   # Replay CSV → Kafka
│   ├── streaming/
│   │   └── spark_streaming.py  # Kafka → Delta Lake
│   └── dashboard/
│       └── app.py              # Dashboard Streamlit
│
├── config/
│   └── config.yaml             # Configuration centralisée
│
├── data/
│   └── raw/                    # Dataset CSV source
│       ├── 2019-Oct.csv
│       ├── 2019-Nov.csv
│       └── ...
│
└── delta/                      # Tables Delta Lake (générées)
    ├── events_raw/             # Events bruts
    ├── checkpoints/            # État du streaming
    └── aggregations/
        ├── events_1min/        # Agrégations 1 minute
        ├── events_5min/        # Agrégations 5 minutes
        ├── products/           # Top produits
        └── funnel/             # Métriques funnel
```

## Métriques Calculées

### Agrégations par fenêtre temporelle

| Métrique | Fenêtre 1 min | Fenêtre 5 min |
|----------|---------------|---------------|
| Nombre d'events par type | ✓ | ✓ |
| Sessions actives uniques | ✓ | ✓ |
| Utilisateurs uniques | ✓ | ✓ |
| Revenue total | ✓ | ✓ |
| Prix moyen | ✓ | ✓ |

### Conversion Funnel

- Views → Add to Cart → Purchase
- Taux de conversion par étape
- Utilisateurs uniques par étape

### Top Produits

- Produits les plus vus
- Produits les plus ajoutés au panier
- Produits les plus achetés
- Revenue par produit

## Dashboard

Le dashboard Streamlit affiche en temps réel :

1. **KPIs principaux** : Sessions actives, Events/min, Taux de conversion, Revenue
2. **Graphique temporel** : Evolution des events par type
3. **Funnel de conversion** : Visualisation des étapes du parcours client
4. **Distribution des events** : Pie chart par type d'event
5. **Top produits** : Tableau des produits les plus populaires
6. **Métriques détaillées** : Table des agrégations 5 minutes

### Configuration du refresh

Le dashboard se rafraîchit automatiquement (configurable de 1 à 30 secondes).

## Configuration

### Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| KAFKA_BOOTSTRAP_SERVERS | kafka:9093 | Adresse du broker Kafka |
| KAFKA_TOPIC | clickstream | Nom du topic |
| DELTA_PATH | /app/delta | Chemin des tables Delta |

### Fichier config.yaml

```yaml
kafka:
  bootstrap_servers: "kafka:9093"
  topic: "clickstream"

producer:
  csv_path: "/app/data/raw/2019-Oct.csv"
  message_delay: 0.01  # 100 events/sec

spark:
  trigger_interval: "10 seconds"
  watermark: "1 minute"

dashboard:
  refresh_interval: 5  # seconds
```

## Troubleshooting

### Kafka ne démarre pas

```bash
# Vérifier les logs
make logs-kafka

# Redémarrer proprement
make clean && make start
```

### Pas de données dans le dashboard

1. Vérifier que le producer envoie des messages :
```bash
make consume
```

2. Vérifier les logs Spark :
```bash
docker logs spark-streaming
```

3. Vérifier que les tables Delta existent :
```bash
ls -la delta/aggregations/
```

### Erreur de mémoire

Ajuster la mémoire Docker (recommandé : 8 Go minimum) ou réduire les ressources Spark dans `docker-compose.yml`.

### Le dashboard n'affiche pas les graphiques

Attendre que Spark ait traité au moins un batch (10-30 secondes après le démarrage).

## Performance

### Ressources utilisées

| Service | CPU | RAM |
|---------|-----|-----|
| Kafka + Zookeeper | ~0.5 core | ~1 Go |
| Spark Streaming | ~1-2 cores | ~2-3 Go |
| Streamlit | ~0.2 core | ~500 Mo |
| **Total** | ~2-3 cores | ~4-5 Go |

### Débit

- Producer : ~100-500 events/sec (configurable)
- Spark processing : ~10 sec micro-batches
- Dashboard refresh : 5 sec

## Améliorations possibles

- [ ] Ajouter des alertes en temps réel (anomaly detection)
- [ ] Implémenter le sessionization (calcul de sessions utilisateur)
- [ ] Ajouter des métriques de latence end-to-end
- [ ] Déployer sur Kubernetes
- [ ] Ajouter des tests unitaires et d'intégration
- [ ] Implémenter le backpressure Kafka
- [ ] Ajouter l'authentification au dashboard

## Licence

MIT

---

Projet réalisé dans le cadre d'un portfolio Data Engineering.
