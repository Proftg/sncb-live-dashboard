# 🚄 Dashboard Ponctualité Live — SNCB/NMBS

Dashboard interactif en temps réel de la ponctualité ferroviaire belge, combinant des données horaires statiques (GTFS) et flux temps réel (GTFS-RT).

**Objectif :** Démontrer la capacité à travailler avec des APIs temps réel, traiter des données géospatiales, et créer des visualisations actionnables pour les décideurs.

## 🎯 Pour ce projet impressionne les recruteurs SNCB/Infrabel

- ✅ **API temps réel** — pas juste des CSV statiques
- ✅ **GTFS** — standard mondial du transport public
- ✅ **Données géospatiales** — cartes interactives
- ✅ **Pipeline complet** — ingestion → nettoyage → visualisation → déploiement
- ✅ **Pertinence métier** — ponctualité = KPI #1 d'Infrabel

## 📊 Fonctionnalités

| Feature | Description |
|---------|-------------|
| 🗺️ Carte live | Positions des trains en temps réel sur carte Folium |
| 📈 KPI Ponctualité | % trains à l'heure, retard moyen, tendance |
| 🚨 Alertes | Trains avec retard > 15 min mis en évidence |
| 📊 Comparaison | Ponctualité par type (IC, L, S, P) |
| 🔮 Prédiction | Probabilité de retard basée sur historique |

## 🛠️ Stack

| Outil | Usage |
|-------|-------|
| Python 3.10+ | Langage principal |
| Pandas | Manipulation données |
| Folium | Cartographie interactive |
| Plotly | Graphiques interactifs |
| Streamlit | Dashboard web |
| Requests | API calls |
| GTFS-Realtime | Protocol Buffers SNCB |

## 📁 Structure

```
sncb-live-dashboard/
├── notebooks/
│   ├── 01_exploration_gtfs.ipynb     # Exploration données statiques
│   ├── 02_api_temps_reel.ipynb       # Connexion API temps réel
│   ├── 03_analyse_ponctualite.ipynb  # Analyse statistique
│   └── 04_cartographie.ipynb         # Cartes interactives
├── app/
│   └── dashboard.py                  # Dashboard Streamlit
├── src/
│   ├── gtfs_loader.py               # Chargement données GTFS
│   ├── realtime_api.py              # Connexion API temps réel
│   ├── kpi_calculator.py            # Calcul KPIs ponctualité
│   └── map_generator.py             # Génération cartes
├── data/
│   ├── raw/                          # Données brutes (gitignored)
│   └── clean/                        # Données nettoyées
├── docs/
│   └── screenshots/                  # Screenshots pour README
├── requirements.txt
├── .gitignore
└── README.md
```

## 🚀 Lancement

```bash
# Installer les dépendances
pip install -r requirements.txt

# 1. Explorer les données GTFS
jupyter notebook notebooks/01_exploration_gtfs.ipynb

# 2. Tester l'API temps réel
jupyter notebook notebooks/02_api_temps_reel.ipynb

# 3. Lancer le dashboard
streamlit run app/dashboard.py
```

## 📖 Sources de données

| Source | URL | Type |
|--------|-----|------|
| Belgian Mobility Data | https://data.belgianmobility.io | GTFS + GTFS-RT |
| SNCB GTFS Static | API Belgian Mobility | ZIP quotidien |
| SNCB GTFS Real-time | API Belgian Mobility | Protocol Buffers 30s |
| Infrabel Open Data | https://opendata.infrabel.be | Ponctualité mensuelle |

## 📅 Roadmap

- [ ] Étape 1 : Exploration données GTFS statiques
- [ ] Étape 2 : Connexion API temps réel SNCB
- [ ] Étape 3 : Analyse ponctualité (12 mois historique)
- [ ] Étape 4 : Carte interactive avec positions trains
- [ ] Étape 5 : Dashboard Streamlit complet
- [ ] Étape 6 : Déploiement + documentation

## 👤 Auteur

**Tahar Guenfoud** — Data Analyst & Data Scientist
- 🌐 [Portfolio](https://proftg.github.io/portfolio)
- 💼 [LinkedIn](https://linkedin.com/in/tahar-guenfoud)
- 📧 taharguenfoud@gmail.com

---

*Projet portfolio — Candidature ICT Traineeship Infrabel*
