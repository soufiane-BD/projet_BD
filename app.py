import datetime
import logging

import config as app_config
from extensions import csrf, limiter
from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from routes.alerte_routes import alerte_bp
from routes.capteur_routes import capteur_bp
from routes.mesure_routes import mesure_bp
from routes.simulation_routes import simulation_bp
from services.alerte_service import add_alerte, get_alertes_for_view, toggle_alerte_status
from services.capteur_service import add_capteur, delete_capteur, get_all_capteurs
from services.cooperative_service import add_cooperative, delete_cooperative, get_all_cooperatives
from services.mesure_service import add_mesure, get_all_mesures
from services.notification_service import get_recent_notifications
from services.pompiers_service import add_pompier, delete_pompier, get_all_pompiers, update_pompier_password
from services.simulation_service import simulate_propagation
from services.user_service import add_user, delete_user, get_all_users, update_user_password
from services.weather_service import get_weather_data
from services.zone_service import add_zone, delete_zone, get_all_zones_with_coop, get_zones_summary
from utils.database import get_db_connection, init_db
from utils.security import (
    login_failure_tracker,
    log_security_event,
    progressive_delay_on_failure,
    validate_password_strength,
)

_security_log = logging.getLogger("argan_security")
_security_log.setLevel(logging.WARNING)
if not _security_log.handlers:
    _fh = logging.FileHandler("security.log", encoding="utf-8")
    _fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _security_log.addHandler(_fh)

app = Flask(__name__)
app.config.update(
    SECRET_KEY=app_config.SECRET_KEY,
    DEBUG=app_config.DEBUG,
    TESTING=app_config.TESTING,
    PROPAGATE_EXCEPTIONS=app_config.PROPAGATE_EXCEPTIONS,
    SESSION_COOKIE_HTTPONLY=app_config.SESSION_COOKIE_HTTPONLY,
    SESSION_COOKIE_SECURE=app_config.SESSION_COOKIE_SECURE,
    SESSION_COOKIE_SAMESITE=app_config.SESSION_COOKIE_SAMESITE,
    PERMANENT_SESSION_LIFETIME=app_config.PERMANENT_SESSION_LIFETIME,
    MAX_CONTENT_LENGTH=app_config.MAX_CONTENT_LENGTH,
    WTF_CSRF_TIME_LIMIT=app_config.WTF_CSRF_TIME_LIMIT,
)

csrf.init_app(app)
limiter.init_app(app)

app.register_blueprint(capteur_bp, url_prefix="/api")
app.register_blueprint(mesure_bp, url_prefix="/api")
app.register_blueprint(alerte_bp, url_prefix="/api")
app.register_blueprint(simulation_bp, url_prefix="/api")

# JSON /api : authentification session obligatoire ; CSRF porté par les formulaires HTML (évite 400 avant 401)
csrf.exempt(capteur_bp)
csrf.exempt(mesure_bp)
csrf.exempt(alerte_bp)
csrf.exempt(simulation_bp)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
login_manager.login_message_category = "info"


@login_manager.unauthorized_handler
def _unauthorized():
    if request.path.startswith("/api"):
        return jsonify({"error": "Authentification requise"}), 401
    return redirect(url_for("login", next=request.url))


class User(UserMixin):
    def __init__(self, id, email, nom, id_cooperative, role):
        self.id = f"{role}_{id}"
        self.db_id = id
        self.email = email
        self.nom = nom
        self.id_cooperative = id_cooperative
        self.role = role

    @property
    def is_admin(self):
        return self.role == "admin"


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


@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' https://unpkg.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com; "
        "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https:; "
        "connect-src 'self'; object-src 'none'; base-uri 'self'"
    )
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
    return response


@app.errorhandler(404)
def not_found(_e):
    if request.path.startswith("/api"):
        return jsonify({"error": "Ressource introuvable"}), 404
    return ("Ressource introuvable", 404)


@app.errorhandler(403)
def forbidden(_e):
    if request.path.startswith("/api"):
        return jsonify({"error": "Accès refusé"}), 403
    return ("Accès refusé", 403)


@app.errorhandler(500)
def internal_error(_e):
    app.logger.exception("Erreur interne")
    if request.path.startswith("/api"):
        return jsonify({"error": "Erreur interne"}), 500
    return ("Erreur interne", 500)


@app.route("/")
def index():
    conn = get_db_connection()
    stats = {
        "total_coops": conn.execute("SELECT COUNT(*) FROM cooperative").fetchone()[0],
        "total_capteurs": conn.execute(
            "SELECT COUNT(*) FROM capteur WHERE COALESCE(actif, 1) = 1"
        ).fetchone()[0],
        "total_alertes": conn.execute("SELECT COUNT(*) FROM alerte").fetchone()[0],
    }
    conn.close()

    recent_alerts = get_alertes_for_view()[:3]

    weather_data = get_weather_data()
    weather = weather_data.get("current") if weather_data else None

    return render_template(
        "index.html",
        active_page="home",
        stats=stats,
        recent_alerts=recent_alerts,
        weather=weather,
    )


@app.route("/dashboard")
@login_required
def dashboard():
    capteurs = get_all_capteurs()
    mesures = get_all_mesures()
    latest = mesures[0] if mesures else {}

    conn = get_db_connection()
    active_alerts = conn.execute("SELECT mesure_id FROM alerte WHERE est_traite = 0").fetchall()
    active_mesure_ids = [row["mesure_id"] for row in active_alerts]
    conn.close()

    weather_data = get_weather_data()
    weather = weather_data.get("current", {}) if weather_data else {}
    hourly = weather_data.get("hourly", {}) if weather_data else {}

    current_temp = weather.get("temperature") if weather else None
    humidity_pct = (
        weather.get("humidity")
        if weather and weather.get("humidity") is not None
        else latest.get("humidite", 32)
    )

    active_sensor_temps = [
        m["temperature"] for m in mesures if m["id"] in active_mesure_ids and m["temperature"] is not None
    ]
    max_active_sensor = max(active_sensor_temps) if active_sensor_temps else 0
    max_temp = max(current_temp or 0, max_active_sensor)

    wind_speed = (
        latest.get("vitesse_vent")
        if latest.get("vitesse_vent") is not None
        else (weather.get("wind_speed") if weather else 28)
    )
    wind_direction = (
        latest.get("direction_vent")
        if latest.get("direction_vent") is not None
        else (weather.get("wind_deg") if weather else 75)
    )
    spread_direction = (float(wind_direction) + ((100 - humidity_pct) / 10)) % 360

    map_data = {
        "center": [30.4278, -9.5981],
        "zoom": 11,
        "windDeg": wind_direction,
        "spreadDeg": spread_direction,
        "fireOrigin": [30.4278, -9.5981],
        "sensors": [],
    }

    now = datetime.datetime.now()
    six_hours_ago = now - datetime.timedelta(hours=6)
    combined_points = []

    if hourly:
        h_times = hourly.get("time", [])
        h_temps = hourly.get("temperature_2m", [])
        h_hums = hourly.get("relativehumidity_2m", [])
        for i in range(len(h_times)):
            try:
                dt = datetime.datetime.fromisoformat(h_times[i])
                if six_hours_ago <= dt <= now:
                    combined_points.append({"time": dt, "temp": h_temps[i], "hum": h_hums[i]})
            except Exception:
                continue

    for m in mesures:
        try:
            dt = datetime.datetime.strptime(m["created_at"], "%Y-%m-%d %H:%M:%S")
            if dt >= six_hours_ago:
                combined_points.append({"time": dt, "temp": m["temperature"], "hum": m["humidite"]})
        except Exception:
            continue

    combined_points.sort(key=lambda x: x["time"])

    chart_data = {
        "labels": [p["time"].strftime("%H:%M") for p in combined_points],
        "temps": [p["temp"] for p in combined_points],
        "hums": [p["hum"] for p in combined_points],
    }

    for index, capteur in enumerate(capteurs):
        sensor_temp = None
        current_mesure_id = None
        for mesure in mesures:
            if mesure.get("capteur_id") == capteur.get("id"):
                sensor_temp = mesure.get("temperature")
                current_mesure_id = mesure.get("id")
                break

        lat_val = capteur.get("latitude")
        lng_val = capteur.get("longitude")

        if lat_val in [None, ""]:
            lat = 30.4278 + (index * 0.005)
            lng = -9.5981 - (index * 0.005)
        else:
            lat = float(lat_val)
            lng = float(lng_val)

        is_active_fire = current_mesure_id in active_mesure_ids and sensor_temp is not None and sensor_temp > 50

        if is_active_fire:
            map_data["fireOrigin"] = [lat, lng]

        map_data["sensors"].append(
            {
                "id": capteur.get("nom") or f"Capteur {capteur.get('id')}",
                "lat": lat,
                "lng": lng,
                "tempC": sensor_temp
                if (sensor_temp is not None and (sensor_temp <= 50 or is_active_fire))
                else (50 if sensor_temp else 0),
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
        chart_data=chart_data,
    )


@app.route("/zones")
@login_required
def zones():
    return render_template(
        "zones.html",
        active_page="zones",
        zones=get_zones_summary(),
    )


@app.route("/simulation")
@login_required
def simulation():
    weather_data = get_weather_data()
    current = weather_data.get("current", {}) if weather_data else {}

    mesures = get_all_mesures()
    live_sim = None
    if mesures:
        latest = mesures[0]
        temp = latest.get("temperature")
        hum = latest.get("humidite")
        if temp is not None and hum is not None:
            live_sim = simulate_propagation(
                temp,
                hum,
                latest.get("vitesse_vent") or 0,
                wind_deg=latest.get("direction_vent"),
                mesure_id=latest.get("id"),
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
        live_sim=live_sim,
    )


@app.route("/alertes")
@login_required
def alertes():
    return render_template(
        "alertes.html",
        active_page="alertes",
        alertes=get_alertes_for_view(),
    )


@app.route("/alerte/traiter/<int:alerte_id>", methods=["POST"])
@login_required
def traiter_alerte(alerte_id):
    if current_user.role != "pompier":
        flash("Seuls les pompiers sont autorisés à traiter les alertes.", "error")
        return redirect(url_for("alertes"))

    toggle_alerte_status(alerte_id)
    flash("Le statut de l'alerte a été mis à jour.", "success")
    return redirect(url_for("alertes"))


@app.route("/notifications")
@login_required
def notifications():
    return render_template(
        "notifications.html",
        active_page="notifications",
        notifications=get_recent_notifications(),
    )


IDENTIFIANTS_INVALIDES = "Identifiants invalides."

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if request.method == "POST":
        ip = request.remote_addr or "unknown"
        if login_failure_tracker.is_locked(ip):
            log_security_event("Tentative de login pendant verrouillage IP %s", ip)
            return render_template("login.html", active_page="login", error=IDENTIFIANTS_INVALIDES)

        email = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        if not email or not password:
            return render_template("login.html", active_page="login", error=IDENTIFIANTS_INVALIDES)

        conn = get_db_connection()
        row = conn.execute("SELECT * FROM user WHERE email = ?", (email,)).fetchone()
        if row and check_password_hash(row["password_hash"], password):
            login_failure_tracker.reset(ip)
            user_obj = User(row["id"], row["email"], row["nom"], row["id_cooperative"], "admin")
            login_user(user_obj)
            conn.close()
            return redirect(url_for("dashboard"))

        row = conn.execute("SELECT * FROM pompiers WHERE email = ?", (email,)).fetchone()
        if row and row["password_hash"] and check_password_hash(row["password_hash"], password):
            login_failure_tracker.reset(ip)
            user_obj = User(row["id"], row["email"], f"{row['nom']} {row['prenom']}", None, "pompier")
            login_user(user_obj)
            conn.close()
            return redirect(url_for("dashboard"))

        conn.close()
        prev = login_failure_tracker.get_consecutive(ip)
        progressive_delay_on_failure(prev + 1)
        login_failure_tracker.register_failure(ip)
        log_security_event("Échec de connexion pour email=%s ip=%s", email, ip)
        return render_template("login.html", active_page="login", error=IDENTIFIANTS_INVALIDES)

    return render_template("login.html", active_page="login")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Vous avez été déconnecté.", "info")
    return redirect(url_for("index"))


@app.route("/changer-mot-de-passe", methods=["GET", "POST"])
@login_required
def changer_mot_de_passe():
    if request.method == "POST":
        old_password = request.form.get("old_password") or ""
        new_password = request.form.get("new_password") or ""
        confirm = request.form.get("confirm_password") or ""
        if new_password != confirm:
            flash("Les mots de passe ne correspondent pas.", "error")
            return render_template("change_password.html", active_page="account")
        if not validate_password_strength(new_password):
            flash("Mot de passe trop faible (min. 8 caractères, majuscule, chiffre, caractère spécial).", "error")
            return render_template("change_password.html", active_page="account")

        conn = get_db_connection()
        if current_user.role == "admin":
            row = conn.execute("SELECT password_hash FROM user WHERE id = ?", (current_user.db_id,)).fetchone()
        else:
            row = conn.execute("SELECT password_hash FROM pompiers WHERE id = ?", (current_user.db_id,)).fetchone()
        conn.close()

        if not row or not row["password_hash"] or not check_password_hash(row["password_hash"], old_password):
            flash(IDENTIFIANTS_INVALIDES, "error")
            return render_template("change_password.html", active_page="account")

        new_hash = generate_password_hash(new_password)
        if current_user.role == "admin":
            update_user_password(current_user.db_id, new_hash)
        else:
            update_pompier_password(current_user.db_id, new_hash)
        flash("Mot de passe mis à jour.", "success")
        return redirect(url_for("dashboard"))

    return render_template("change_password.html", active_page="account")


@app.route("/gestion", methods=["GET", "POST"])
@login_required
def gestion():
    if current_user.role != "admin":
        flash("Accès refusé. Cette page est réservée aux administrateurs.", "error")
        return redirect(url_for("index"))

    if request.method == "POST":
        form_type = request.form.get("form_type")
        try:
            if form_type == "capteur":
                nom = request.form.get("nom", "").strip()
                loc = request.form.get("localisation", "").strip()
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
                    res = add_mesure(
                        int(c_id),
                        float(temp),
                        float(hum),
                        vitesse_vent=float(wind) if wind else None,
                        direction_vent=float(wind_dir) if wind_dir else None,
                    )
                    msg = "Mesure enregistrée."
                    if res.get("alerte"):
                        msg += " ALERTE DÉTECTÉE !"
                    flash(msg, "success")

            elif form_type == "alerte":
                m_id = request.form.get("mesure_id")
                lvl = request.form.get("niveau_risque", "modéré")
                msg = request.form.get("message", "Alerte créée manuellement")
                if m_id:
                    add_alerte(int(m_id), lvl, msg, created_by_user_ref=current_user.id)
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
                password = request.form.get("password", "").strip()
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
                conn = get_db_connection()
                conn.execute("PRAGMA foreign_keys = OFF")
                tables = [
                    "donne_lieu",
                    "recoit1",
                    "recoit",
                    "simulation_de_propagation",
                    "pompiers",
                    "notification",
                    "alerte",
                    "mesure",
                    "capteur",
                    "zone",
                    "cooperative",
                ]
                for t in tables:
                    conn.execute(f"DELETE FROM {t}")
                    conn.execute("DELETE FROM sqlite_sequence WHERE name=?", (t,))
                conn.execute("PRAGMA foreign_keys = ON")
                conn.commit()
                conn.close()
                flash("Tout le réseau a été réinitialisé. Les comptes utilisateurs ont été conservés.", "warning")

        except ValueError:
            flash("Données invalides.", "error")
        except Exception:
            app.logger.exception("gestion")
            flash("Une erreur est survenue.", "error")

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
        pompiers=pompiers,
    )


def setup_database():
    init_db()


setup_database()

if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=app_config.DEBUG, port=5000)