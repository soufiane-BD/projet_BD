"""
Argan-Fire Watch — serveur Flask pour les templates (dashboard, alertes).
Backend : remplacer les *_DEMO et les dicts dans chaque route par SQL / procédures — voir README.md (section intégration).

Exécution : si "python app.py" échoue avec "No module named flask", vous avez deux Pythons :
  pip installe souvent pour 3.14, alors que "python" lance 3.10. Utilisez :
    py -3.14 app.py
  ou double-cliquez sur run.bat
"""

from flask import Flask, redirect, render_template, request, url_for

app = Flask(__name__)

NOTIFICATIONS_DEMO = [
    {
        "title": "SMS pompiers — Coopérative B",
        "text": "Seuil 52 °C dépassé. Message envoyé aux secours (trigger base).",
        "time": "21 mars 2025 · 14:32",
        "iso": "2025-03-21T14:32:00",
        "kind": "sms",
        "unread": True,
        "meta": "Canal : SMS · Log immutable",
    },
    {
        "title": "Rappel humidité basse",
        "text": "Humidité sous 35 % sur la zone nord — risque propagation accru.",
        "time": "21 mars 2025 · 09:15",
        "iso": "2025-03-21T09:15:00",
        "kind": "alert",
        "unread": True,
        "meta": "Règle météo · Chergui",
    },
    {
        "title": "Synchronisation journaux",
        "text": "Export des événements de détection terminé (lecture seule).",
        "time": "20 mars 2025 · 23:00",
        "iso": "2025-03-20T23:00:00",
        "kind": "info",
        "unread": False,
        "meta": None,
    },
]

ZONES_DEMO = [
    {
        "nom": "Coopérative A — Taroudant Nord",
        "commune": "Taroudant",
        "surface_ha": 42,
        "capteurs": 4,
        "risk": "medium",
        "risk_label": "Risque modéré",
        "derniere_synchro": "21 mars 2025 · 14:30",
        "iso": "2025-03-21T14:30:00",
        "note": "Lisière boisée dense, accès piste forestière.",
    },
    {
        "nom": "Coopérative B — Ait Baha",
        "commune": "Aït Baha",
        "surface_ha": 58,
        "capteurs": 6,
        "risk": "high",
        "risk_label": "Risque élevé",
        "derniere_synchro": "21 mars 2025 · 14:32",
        "iso": "2025-03-21T14:32:00",
        "note": "Vent fort fréquent — capteur T2 a dépassé le seuil critique (démo).",
    },
    {
        "nom": "Coopérative C — Ida Outanane",
        "commune": "Ida Outanane",
        "surface_ha": 31,
        "capteurs": 3,
        "risk": "low",
        "risk_label": "Risque faible",
        "derniere_synchro": "20 mars 2025 · 22:10",
        "iso": "2025-03-20T22:10:00",
        "note": "Humidité relative plus stable, surveillance standard.",
    },
]

SIM_DEFAULTS = {
    "wind_kmh": 28,
    "wind_deg": 75,
    "humidity": 32,
}

ALERTES_DEMO = [
    {
        "horodatage": "21/03/2025 14:32:05",
        "iso": "2025-03-21T14:32:05",
        "lieu": "Coopérative B — capteur T2",
        "temp_c": 52,
        "action": "SMS pompiers + log trigger",
        "log_statut": "immutable",
        "critique": True,
    },
    {
        "horodatage": "21/03/2025 11:08:41",
        "iso": "2025-03-21T11:08:41",
        "lieu": "Coopérative A — capteur T1",
        "temp_c": 48,
        "action": "Enregistrement automatique",
        "log_statut": "lecture",
        "critique": False,
    },
    {
        "horodatage": "20/03/2025 18:55:12",
        "iso": "2025-03-20T18:55:12",
        "lieu": "Coopérative C — capteur T3",
        "temp_c": 35,
        "action": "Veille — pas d’envoi",
        "log_statut": "immutable",
        "critique": False,
    },
]


@app.route("/")
def index():
    return render_template("index.html", active_page="home")


@app.route("/dashboard")
def dashboard():
    map_data = {
        "center": [30.4278, -9.5981],
        "zoom": 11,
        "windDeg": 75,
        "spreadDeg": 78,
        "fireOrigin": [30.42, -9.61],
        "sensors": [
            {"id": "Coop A", "lat": 30.435, "lng": -9.59, "tempC": 38},
            {"id": "Coop B", "lat": 30.418, "lng": -9.605, "tempC": 52},
            {"id": "Coop C", "lat": 30.428, "lng": -9.62, "tempC": 35},
        ],
    }
    return render_template(
        "dashboard.html",
        active_page="dashboard",
        wind_speed_kmh=28,
        wind_direction_deg=75,
        humidity_pct=32,
        max_temp_c=52,
        map_data=map_data,
    )


@app.route("/zones")
def zones():
    return render_template(
        "zones.html",
        active_page="zones",
        zones=ZONES_DEMO,
    )


@app.route("/simulation")
def simulation():
    return render_template(
        "simulation.html",
        active_page="simulation",
        sim_defaults=SIM_DEFAULTS,
    )


@app.route("/alertes")
def alertes():
    return render_template(
        "alertes.html",
        active_page="alertes",
        alertes=ALERTES_DEMO,
    )


@app.route("/notifications")
def notifications():
    return render_template(
        "notifications.html",
        active_page="notifications",
        notifications=NOTIFICATIONS_DEMO,
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
        return redirect(url_for("dashboard"))
    return render_template("login.html", active_page="login")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
