import os
import sqlite3
from werkzeug.security import generate_password_hash

# Database file path in the project root.
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database.db")


def get_db_connection():
    """Return a SQLite database connection with row access by column name."""
    connection = sqlite3.connect(DB_PATH, timeout=30) # Augmentation du délai de sécurité
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    """Create the database tables if they do not exist."""
    connection = get_db_connection()
    cursor = connection.cursor()
    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS cooperative (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            region TEXT,
            ville TEXT,
            latitude REAL,
            longitude REAL,
            adresse TEXT,
            date_de_creation TEXT
        );

        CREATE TABLE IF NOT EXISTS zone (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            niveau_risque TEXT,
            id_cooperative INTEGER,
            FOREIGN KEY(id_cooperative) REFERENCES cooperative(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS capteur (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            localisation TEXT,
            latitude REAL,
            longitude REAL,
            id_zone INTEGER,
            actif INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(id_zone) REFERENCES zone(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS mesure (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            temperature REAL,
            humidite REAL,
            vitesse_vent REAL,
            direction_vent TEXT,
            capteur_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(capteur_id) REFERENCES capteur(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS alerte (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mesure_id INTEGER,
            niveau_risque TEXT,
            message TEXT,
            est_traite INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(mesure_id) REFERENCES mesure(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS notification (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date_envoi TEXT,
            message TEXT,
            statut_envoi TEXT,
            alerte_id INTEGER,
            FOREIGN KEY(alerte_id) REFERENCES alerte(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS user (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nom TEXT,
            id_cooperative INTEGER,
            FOREIGN KEY(id_cooperative) REFERENCES cooperative(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS pompiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            prenom TEXT,
            email TEXT,
            telephone TEXT,
            password_hash TEXT,
            created_by_admin_id INTEGER,
            FOREIGN KEY(created_by_admin_id) REFERENCES user(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS simulation_de_propagation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            probabilite REAL,
            vitesse_de_propagation REAL,
            surface_estime REAL,
            date_simulation TEXT,
            direction_du_feu TEXT,
            methode_calcule TEXT
        );

        CREATE TABLE IF NOT EXISTS recoit (
            notification_id INTEGER NOT NULL,
            pompiers_id INTEGER NOT NULL,
            PRIMARY KEY(notification_id, pompiers_id),
            FOREIGN KEY(notification_id) REFERENCES notification(id) ON DELETE CASCADE,
            FOREIGN KEY(pompiers_id) REFERENCES pompiers(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS recoit1 (
            user_id INTEGER NOT NULL,
            notification_id INTEGER NOT NULL,
            PRIMARY KEY(user_id, notification_id),
            FOREIGN KEY(user_id) REFERENCES user(id) ON DELETE CASCADE,
            FOREIGN KEY(notification_id) REFERENCES notification(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS donne_lieu (
            alerte_id INTEGER NOT NULL,
            simulation_id INTEGER NOT NULL,
            PRIMARY KEY(alerte_id, simulation_id),
            FOREIGN KEY(alerte_id) REFERENCES alerte(id) ON DELETE CASCADE,
            FOREIGN KEY(simulation_id) REFERENCES simulation_de_propagation(id) ON DELETE CASCADE
        );
        """
    )

    # Mise à jour pour les bases de données existantes : ajoute les colonnes si elles manquent
    try:
        cursor.execute("ALTER TABLE capteur ADD COLUMN latitude REAL")
    except sqlite3.OperationalError:
        pass  # La colonne existe déjà
    try:
        cursor.execute("ALTER TABLE capteur ADD COLUMN longitude REAL")
    except sqlite3.OperationalError:
        pass  # La colonne existe déjà
    try:
        cursor.execute("ALTER TABLE cooperative ADD COLUMN latitude REAL")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE cooperative ADD COLUMN longitude REAL")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE user ADD COLUMN id_cooperative INTEGER")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE alerte ADD COLUMN est_traite INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE pompiers ADD COLUMN password_hash TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE pompiers ADD COLUMN created_by_admin_id INTEGER")
    except sqlite3.OperationalError:
        pass

    # Création d'un utilisateur admin par défaut si la table est vide
    cursor.execute("SELECT COUNT(*) FROM user")
    if cursor.fetchone()[0] == 0:
        # Identifiants par défaut : admin@argan.ma / admin123
        admin_hash = generate_password_hash("admin123")
        cursor.execute("INSERT INTO user (email, password_hash, nom) VALUES (?, ?, ?)",
                       ("admin@argan.ma", admin_hash, "Administrateur"))

    connection.commit()
    connection.close()
