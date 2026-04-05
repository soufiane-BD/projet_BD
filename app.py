
import os, datetime
from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, url_for, flash, current_app
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from routes.capteur_routes import capteur_bp
from routes.mesure_routes import mesure_bp
from routes.alerte_routes import alerte_bp
from routes.simulation_routes import simulation_bp
from services.alerte_service import get_alertes_for_view, add_alerte, toggle_alerte_status
from services.capteur_service import get_all_capteurs, add_capteur, delete_capteur
from services.cooperative_service import get_all_cooperatives, add_cooperative, delete_cooperative
from services.pompiers_service import get_all_pompiers, add_pompier, delete_pompier
from services.mesure_service import get_all_mesures, add_mesure
from services.notification_service import get_recent_notifications
from services.weather_service import get_weather_data
from services.simulation_service import simulate_propagation
from services.zone_service import get_zones_summary, get_all_zones_with_coop, delete_zone, add_zone
from services.user_service import get_all_users, add_user, delete_user
from utils.database import init_db, get_db_connection
from werkzeug.security import check_password_hash

# Charger les variables d'environnement depuis le fichier .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.register_blueprint(capteur_bp, url_prefix="/api")
app.register_blueprint(mesure_bp, url_prefix="/api")
app.register_blueprint(alerte_bp, url_prefix="/api")
app.register_blueprint(simulation_bp, url_prefix="/api")

# Configuration Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
login_manager.login_message_category = "info"

class User(UserMixin):
    def __init__(self, id, email, nom, id_cooperative, role):
        self.id = f"{role}_{id}"  # ID unique pour la session (ex: admin_1)
        self.db_id = id           # ID réel en base
        self.email = email
        self.nom = nom
        self.id_cooperative = id_cooperative
        self.role = role          # 'admin' ou 'pompier'

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    if user_id.startswith("admin_"):
        db_id = user_id.replace("admin_", "")
        row = conn.execute("SELECT * FROM user WHERE id = ?", (db_id,)).fetchone()
        conn.close()
        if row:
            return User(row["id"], row["email"], row["nom"], row["id_cooperative"], "admin")
    
    elif user_id.startswith("pompier_"):
        db_id = user_id.replace("pompier_", "")
        row = conn.execute("SELECT * FROM pompiers WHERE id = ?", (db_id,)).fetchone()
        conn.close()
        if row:
            return User(row["id"], row["email"], f"{row['nom']} {row['prenom']}", None, "pompier")
            
    return None

@app.route("/")
def index():
    conn = get_db_connection()
    stats = {
        "total_coops": conn.execute("SELECT COUNT(*) FROM cooperative").fetchone()[0],
        "total_capteurs": conn.execute("SELECT COUNT(*) FROM capteur").fetchone()[0],
        "total_alertes": conn.execute("SELECT COUNT(*) FROM alerte").fetchone()[0]
    }
    conn.close()

    # Récupération des 3 dernières alertes formatées
    recent_alerts = get_alertes_for_view()[:3]

    # Récupération de la météo actuelle pour Souss-Massa
    weather_data = get_weather_data()
    weather = weather_data.get("current") if weather_data else None

    return render_template("index.html", 
                           active_page="home", 
                           stats=stats, 
                           recent_alerts=recent_alerts, 
                           weather=weather)


@app.route("/dashboard")
def dashboard():
    capteurs = get_all_capteurs()
    mesures = get_all_mesures()
    latest = mesures[0] if mesures else {}

    # Récupérer les IDs des mesures ayant des alertes NON traitées (toujours actives)
    conn = get_db_connection()
    active_alerts = conn.execute("SELECT mesure_id FROM alerte WHERE est_traite = 0").fetchall()
    active_mesure_ids = [row["mesure_id"] for row in active_alerts]
    conn.close()

    # 1. Récupération météo (Current + Hourly)
    weather_data = get_weather_data()
    weather = weather_data.get("current", {}) if weather_data else {}
    hourly = weather_data.get("hourly", {}) if weather_data else {}

    current_temp = weather.get("temperature") if weather else None
    humidity_pct = (
        weather.get("humidity")
        if weather and weather.get("humidity") is not None
        else latest.get("humidite", 32)
    )
    
    # Calcul de la température max pour l'interface : on ne considère que les alertes actives
    active_sensor_temps = [m["temperature"] for m in mesures if m["id"] in active_mesure_ids and m["temperature"] is not None]
    max_active_sensor = max(active_sensor_temps) if active_sensor_temps else 0
    max_temp = max(current_temp or 0, max_active_sensor)
    
    # Priorité aux données du dernier capteur pour le vent, sinon API météo
    wind_speed = latest.get("vitesse_vent") if latest.get("vitesse_vent") is not None else (weather.get("wind_speed") if weather else 28)
    wind_direction = latest.get("direction_vent") if latest.get("direction_vent") is not None else (weather.get("wind_deg") if weather else 75)
    # Calcul de la déviation du front de flamme selon la sécheresse (humidité basse = plus de déviation)
    spread_direction = (float(wind_direction) + ((100 - humidity_pct) / 10)) % 360

    map_data = {
        "center": [30.4278, -9.5981],
        "zoom": 11,
        "windDeg": wind_direction,
        "spreadDeg": spread_direction,
        "fireOrigin": [30.4278, -9.5981],  # Position par défaut (centre)
        "sensors": [],
    }

    # 2. Préparation du graphique (Fenêtre de 6 heures)
    now = datetime.datetime.now()
    six_hours_ago = now - datetime.timedelta(hours=6)
    combined_points = []

    # Ajouter les points de l'API Météo
    if hourly:
        h_times = hourly.get("time", [])
        h_temps = hourly.get("temperature_2m", [])
        h_hums = hourly.get("relativehumidity_2m", [])
        for i in range(len(h_times)):
            try:
                dt = datetime.datetime.fromisoformat(h_times[i])
                if six_hours_ago <= dt <= now:
                    combined_points.append({
                        "time": dt, "temp": h_temps[i], "hum": h_hums[i]
                    })
            except: continue

    # Ajouter vos mesures réelles (Capteurs)
    for m in mesures:
        try:
            dt = datetime.datetime.strptime(m['created_at'], "%Y-%m-%d %H:%M:%S")
            if dt >= six_hours_ago:
                combined_points.append({
                    "time": dt, "temp": m['temperature'], "hum": m['humidite']
                })
        except: continue

    # Trier tous les points par date et formater pour Chart.js
    combined_points.sort(key=lambda x: x["time"])
    
    chart_data = {
        "labels": [p["time"].strftime("%H:%M") for p in combined_points],
        "temps": [p["temp"] for p in combined_points],
        "hums": [p["hum"] for p in combined_points]
    }

    # Build simple map sensor data from actual capteurs and latest measure values.
    for index, capteur in enumerate(capteurs):
        sensor_temp = None
        current_mesure_id = None
        for mesure in mesures:
            if mesure.get("capteur_id") == capteur.get("id"):
                sensor_temp = mesure.get("temperature")
                current_mesure_id = mesure.get("id")
                break
        
        # Utilise les coordonnées réelles (converties en float) ou une valeur par défaut
        lat_val = capteur.get("latitude")
        lng_val = capteur.get("longitude")

        if lat_val in [None, ""]:
            lat = 30.4278 + (index * 0.005)
            lng = -9.5981 - (index * 0.005)
        else:
            lat = float(lat_val)
            lng = float(lng_val)

        # On définit si l'incendie est toujours considéré comme "actif" visuellement
        # Condition : Temp > 50 ET l'alerte n'est pas marquée comme traitée
        is_active_fire = (current_mesure_id in active_mesure_ids and sensor_temp is not None and sensor_temp > 50)

        # Dynamisation : si le feu est actif, les lignes de propagation partent de lui
        if is_active_fire:
            map_data["fireOrigin"] = [lat, lng]

        map_data["sensors"].append(
            {
                "id": capteur.get("nom") or f"Capteur {capteur.get('id')}",
                "lat": lat,
                "lng": lng,
                # Pour la carte : on force à 50 si traité pour enlever le cercle rouge (qui est > 50)
                "tempC": sensor_temp if (sensor_temp is not None and (sensor_temp <= 50 or is_active_fire)) else (50 if sensor_temp else 0),
            }
        )

    return render_template(
        "dashboard.html",
        active_page="dashboard",
        wind_speed_kmh=wind_speed,
        wind_direction_deg=wind_direction,
        humidity_pct=humidity_pct,
        max_temp_c=max_temp,
        map_data=map_data,
        chart_data=chart_data
    )


@app.route("/zones")
def zones():
    return render_template(
        "zones.html",
        active_page="zones",
        zones=get_zones_summary(),
    )


@app.route("/simulation")
def simulation():
    # 1. Données météo pour les curseurs
    weather_data = get_weather_data()
    current = weather_data.get("current", {}) if weather_data else {}
    
    # 2. Lancer la simulation automatique sur la dernière mesure
    mesures = get_all_mesures()
    live_sim = None
    if mesures:
        latest = mesures[0]
        temp = latest.get("temperature")
        hum = latest.get("humidite")
        # On ne lance la simulation que si les données numériques sont présentes
        if temp is not None and hum is not None:
            live_sim = simulate_propagation(
                temp, 
                hum, 
                latest.get("vitesse_vent") or 0,
                wind_deg=latest.get("direction_vent"),
                mesure_id=latest.get("id")
            )

    sim_defaults = {
        "wind_kmh": current.get("wind_speed", 28),
        "wind_deg": current.get("wind_deg", 75),
        "humidity": current.get("humidity", 32),
    }
    return render_template(
        "simulation.html",
        active_page="simulation",
        sim_defaults=sim_defaults,
        live_sim=live_sim  # On envoie le résultat au HTML
    )


@app.route("/alertes")
def alertes():
    return render_template(
        "alertes.html",
        active_page="alertes",
        alertes=get_alertes_for_view(),
    )

@app.route("/alerte/traiter/<int:alerte_id>", methods=["POST"])
@login_required
def traiter_alerte(alerte_id):
    # Sécurité : Seuls les pompiers peuvent changer l'état d'une alerte
    if current_user.role != "pompier":
        flash("Seuls les pompiers sont autorisés à traiter les alertes.", "error")
        return redirect(url_for("alertes"))

    toggle_alerte_status(alerte_id)
    flash("Le statut de l'alerte a été mis à jour.", "success")
    return redirect(url_for("alertes"))


@app.route("/notifications")
def notifications():
    return render_template(
        "notifications.html",
        active_page="notifications",
        notifications=get_recent_notifications(),
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        if not email or not password:
            return render_template(
                "login.html",
                active_page="login",
                error="Veuillez renseigner l’identifiant et le mot de passe.",
            )
        
        conn = get_db_connection()
        # 1. Tester si l'utilisateur est un Administrateur (table 'user')
        row = conn.execute("SELECT * FROM user WHERE email = ?", (email,)).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            user_obj = User(row["id"], row["email"], row["nom"], row["id_cooperative"], "admin")
            login_user(user_obj)
            conn.close()
            return redirect(url_for("dashboard"))
            
        # 2. Tester si l'utilisateur est un Pompier (table 'pompiers')
        row = conn.execute("SELECT * FROM pompiers WHERE email = ?", (email,)).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            # Les pompiers n'ont pas d'ID coopérative direct dans leur table
            user_obj = User(row["id"], row["email"], f"{row['nom']} {row['prenom']}", None, "pompier")
            login_user(user_obj)
            conn.close()
            return redirect(url_for("dashboard"))
            
        conn.close()
        return render_template("login.html", active_page="login", error="Identifiants incorrects.")

    return render_template("login.html", active_page="login")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Vous avez été déconnecté.", "info")
    return redirect(url_for("index"))

@app.route("/gestion", methods=["GET", "POST"])
@login_required
def gestion():
    # Restriction : Seul l'Admin a accès à la gestion
    if current_user.role != "admin":
        flash("Accès refusé. Cette page est réservée aux administrateurs.", "error")
        return redirect(url_for("index"))

    """Page de gestion pour ajouter manuellement des capteurs, mesures et alertes."""
    if request.method == "POST":
        form_type = request.form.get("form_type")
        try:
            if form_type == "capteur":
                nom = request.form.get("nom", "").strip()
                loc = request.form.get("localisation", "").strip()
                
                # Conversion sécurisée : on veut des nombres ou None, pas des chaînes vides
                try:
                    lat = float(request.form.get("latitude")) if request.form.get("latitude") else None
                    lng = float(request.form.get("longitude")) if request.form.get("longitude") else None
                    id_zone = int(request.form.get("id_zone")) if request.form.get("id_zone") else None
                except ValueError:
                    lat = lng = id_zone = None

                if nom:
                    add_capteur(nom, loc, latitude=lat, longitude=lng, id_zone=id_zone)
                    flash(f"Capteur '{nom}' ajouté avec succès !", "success")
                else:
                    flash("Le nom du capteur est obligatoire.", "error")

            elif form_type == "cooperative":
                nom = request.form.get("nom", "").strip()
                region = request.form.get("region", "").strip()
                ville = request.form.get("ville", "").strip()
                adresse = request.form.get("adresse", "").strip()
                date_crea = request.form.get("date_crea", "").strip()
                lat = request.form.get("latitude")
                lng = request.form.get("longitude")
                if nom:
                    add_cooperative(nom, region, ville, lat, lng, adresse, date_crea)
                    flash(f"Coopérative '{nom}' créée.", "success")

            elif form_type == "zone":
                nom = request.form.get("nom", "").strip()
                id_coop = request.form.get("id_cooperative")
                if nom:
                    add_zone(nom, id_coop)
                    flash(f"Zone '{nom}' ajoutée.", "success")

            elif form_type == "mesure":
                c_id = request.form.get("capteur_id")
                temp = request.form.get("temperature")
                hum = request.form.get("humidite")
                wind = request.form.get("vitesse_vent")
                wind_dir = request.form.get("direction_vent")
                if c_id and temp and hum:
                    res = add_mesure(int(c_id), float(temp), float(hum), 
                                     vitesse_vent=float(wind) if wind else None,
                                     direction_vent=float(wind_dir) if wind_dir else None)
                    msg = "Mesure enregistrée."
                    if res.get("alerte"):
                        msg += " ALERTE DÉTECTÉE !"
                    flash(msg, "success")

            elif form_type == "alerte":
                m_id = request.form.get("mesure_id")
                lvl = request.form.get("niveau_risque", "modéré")
                msg = request.form.get("message", "Alerte créée manuellement")
                if m_id:
                    add_alerte(int(m_id), lvl, msg)
                    flash("Alerte manuelle créée avec succès.", "success")

            elif form_type == "delete_capteur":
                cap_id = request.form.get("id")
                if cap_id:
                    delete_capteur(int(cap_id))
                    flash("Capteur supprimé.", "info")

            elif form_type == "delete_zone":
                z_id = request.form.get("id")
                if z_id:
                    delete_zone(int(z_id))
                    flash("Zone supprimée.", "info")

            elif form_type == "delete_cooperative":
                c_id = request.form.get("id")
                if c_id:
                    delete_cooperative(int(c_id))
                    flash("Coopérative supprimée.", "info")

            elif form_type == "user":
                email = request.form.get("email", "").strip()
                password = request.form.get("password")
                nom = request.form.get("nom", "").strip()
                
                # On s'assure que si aucune coopérative n'est choisie, on envoie None (NULL)
                id_coop = request.form.get("id_cooperative")
                id_coop = int(id_coop) if id_coop else None

                if email and password:
                    add_user(email, password, nom, id_coop)
                    flash(f"Utilisateur '{email}' créé.", "success")

            elif form_type == "pompier":
                nom = request.form.get("nom", "").strip()
                prenom = request.form.get("prenom", "").strip()
                email = request.form.get("email", "").strip()
                telephone = request.form.get("telephone", "").strip()
                password = request.form.get("password", "pompier123")
                # created_by_admin_id utilise l'ID de l'admin connecté (db_id)
                if nom and telephone and password:
                    add_pompier(nom, prenom, email, telephone, password, current_user.db_id)
                    flash(f"Pompier '{nom} {prenom}' ajouté avec succès.", "success")

            elif form_type == "delete_user":
                u_id = request.form.get("id")
                if u_id:
                    delete_user(int(u_id))
                    flash("Utilisateur supprimé.", "info")

            elif form_type == "delete_pompier":
                p_id = request.form.get("id")
                if p_id:
                    delete_pompier(int(p_id))
                    flash("Pompier supprimé.", "info")

            elif form_type == "reset_all":
                # Réinitialisation de tout le réseau sauf la table 'user'
                conn = get_db_connection()
                conn.execute("PRAGMA foreign_keys = OFF")
                # Liste des tables à vider (ordre sans importance grâce au PRAGMA OFF)
                tables = ["donne_lieu", "recoit1", "recoit", "simulation_de_propagation", 
                          "pompiers", "notification", "alerte", "mesure", "capteur", 
                          "zone", "cooperative"]
                for t in tables:
                    conn.execute(f"DELETE FROM {t}")
                    # Réinitialiser les compteurs d'ID (AUTOINCREMENT)
                    conn.execute("DELETE FROM sqlite_sequence WHERE name=?", (t,))
                conn.execute("PRAGMA foreign_keys = ON")
                conn.commit()
                conn.close()
                flash("Tout le réseau a été réinitialisé. Les comptes utilisateurs ont été conservés.", "warning")

        except Exception as e:
            flash(f"Erreur : {str(e)}", "error")

        return redirect(url_for("gestion"))

    capteurs = get_all_capteurs()
    mesures = get_all_mesures()
    cooperatives = get_all_cooperatives()
    zones = get_all_zones_with_coop()
    users = get_all_users()
    pompiers = get_all_pompiers()

    return render_template(
        "gestion.html",
        active_page="gestion",
        capteurs=capteurs,
        mesures=mesures,
        cooperatives=cooperatives,
        zones=zones,
        users=users,
        pompiers=pompiers
    )


def setup_database():
    init_db()


# Create the database tables when the module is loaded.
setup_database()


if __name__ == "__main__":
    app.run(debug=True, port=5000)
