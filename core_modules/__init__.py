# core_modules package initializer

from .auth import Authentication
from .database import DatabaseManager
from .analytics import AnalyticsEngine
from .email_service import EmailService
from .config import Config

# IMPORTANT:
# Do NOT import report_generator here.
# ReportGenerator is located inside: enhancements/report_generator.py
# and should be imported directly from enhancements in app.py
