import os
import secrets

from dotenv import load_dotenv

load_dotenv()


class Config:
    # App
    APP_NAME = "ML-Driven Vendor Optimization Platform"
    APP_VERSION = "2.0.0"
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"

    # Database
    DB_PATH = os.getenv("DB_PATH", "Data layer/vendors.db")

    # Auth — SECRET_KEY must come from the environment in production.
    # For local demo runs an ephemeral key is generated per process,
    # which invalidates JWTs on restart (acceptable for a demo).
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
    JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
    SESSION_TIMEOUT_MINUTES = int(os.getenv("SESSION_TIMEOUT_MINUTES", "60"))
    DEMO_ADMIN_USERNAME = os.getenv("DEMO_ADMIN_USERNAME", "admin")
    DEMO_ADMIN_PASSWORD = os.getenv("DEMO_ADMIN_PASSWORD", "admin123")
    DEMO_ADMIN_NAME = os.getenv("DEMO_ADMIN_NAME", "Administrator")
    DEMO_ADMIN_EMAIL = os.getenv("DEMO_ADMIN_EMAIL", "admin@company.com")
    PASSWORD_HASH_ITERATIONS = int(os.getenv("PASSWORD_HASH_ITERATIONS", "120000"))

    # Email
    EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_USER = os.getenv("EMAIL_USER", "")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")

    # ML
    ML_RISK_THRESHOLD = float(os.getenv("ML_RISK_THRESHOLD", "0.6"))
    ML_CHURN_THRESHOLD = float(os.getenv("ML_CHURN_THRESHOLD", "0.5"))

    # Alerts
    PERFORMANCE_ALERT_THRESHOLD = int(os.getenv("PERFORMANCE_ALERT_THRESHOLD", "70"))

    # Reports
    REPORTS_DIR = os.getenv("REPORTS_DIR", "reports")
