## 👥 Équipe

### 🏗️ Architecture & Développement
- [ELBADAOUI Soufiane](https://github.com/soufiane-BD)
- [EL Ouafi Souad](https://github.com/souad-elouafi)
- [ELLAOUI Amal](https://github.com/amalellaoui)

### 🔐 Sécurité
- [El Mehdi](https://github.com/el-mehdi33)
- [FAJRI Rania](https://github.com/RaniaFJ)
- [EL BARAKA Rim](https://github.com/Reemap1)
- [EL Lkhessouani Ilyas](https://github.com/Ilyas122ux)
- [HADAD Haytam](https://github.com/haytam-hadad)
- [Gourmije Ferdaousse](https://github.com/ferdaoussegourmije)
## 🎥 Démonstration

![Aperçu](demo.gif)

👉 [Voir la vidéo complète](./app_video.mp4)
# Argan-Fire Watch — projet_BD

Application Flask : templates dans `templates/`, styles et scripts dans `static/`, logique et données dans `app.py`.

## Pour la personne backend (intégration simple)

Tout se joue dans **`app.py`** : remplacer les listes `*_DEMO` et les dictionnaires construits dans chaque `@app.route` par le résultat de vos **requêtes SQL**, **procédures stockées** ou **API**.

| Route | Vue | À brancher côté base / API |
|-------|-----|----------------------------|
| `GET /` | `index.html` | Aucune donnée obligatoire (`active_page="home"`). |
| `GET /dashboard` | `dashboard.html` | Météo + capteurs + **`map_data`** (JSON pour la carte Leaflet). |
| `GET /zones` | `zones.html` | Liste **`zones`** : chaque élément a `nom`, `commune`, `surface_ha`, `capteurs`, `risk` (`low`/`medium`/`high`), `risk_label`, `derniere_synchro`, `iso`, `note`. |
| `GET /simulation` | `simulation.html` | **`sim_defaults`** : `wind_kmh`, `wind_deg`, `humidity` (valeurs initiales des curseurs). Le calcul démo est dans `static/js/simulation.js` — remplacez par un `POST /api/simulation` qui appelle votre procédure si besoin. |
| `GET /alertes` | `alertes.html` | Liste **`alertes`** : `horodatage`, `iso`, `lieu`, `temp_c`, `action`, `log_statut` (`immutable` ou `lecture`), `critique` (bool). |
| `GET /notifications` | `notifications.html` | Liste **`notifications`** : `title`, `text`, `time`, `iso`, `kind` (`sms`/`alert`/`info`), `unread`, `meta` (optionnel). |
| `GET/POST /login` | `login.html` | Brancher ici votre auth (session, JWT, LDAP). |

### Carte (`/dashboard`) — clé `map_data`

À passer en JSON dans le template via `{{ map_data|tojson }}` (déjà câblé dans `dashboard.html`) :

- `center` : `[lat, lng]`
- `zoom` : entier
- `windDeg`, `spreadDeg` : degrés (0 = Nord)
- `fireOrigin` : `[lat, lng]`
- `sensors` : `[{ "id", "lat", "lng", "tempC" }, …]`

### Bonnes pratiques

- Sortir la connexion SGBD et les requêtes dans un module séparé (`db.py`, `repositories.py`) quand le projet grossit.
- Ne pas exposer les identifiants de base dans le dépôt : variables d’environnement (`python-dotenv`).
- Les **logs immuables** et **triggers SMS** restent côté base ; le front affiche seulement l’état courant.

## Installation & Setup (Collaborateurs)

1. **Environnement virtuel** :
   ```bash
   python -m venv .venv
   # Activer (Windows): .venv\Scripts\activate
   ```
2. **Dépendances** :
   ```bash
   pip install -r requirements.txt
   ```
3. **Configuration Secrets** :
   Copiez `.env.example` vers `.env` et remplissez vos identifiants Gmail (Mot de passe d'application).

4. **Lancer le serveur** :
   ```bash
   python app.py
   ```
   Accès : http://127.0.0.1:5000 | Admin par défaut : `admin@argan.ma` / `admin123`
