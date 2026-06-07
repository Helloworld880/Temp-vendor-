import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    def __init__(self, db):
        self.db = db

    def get_kpi_summary(self) -> dict:
        """Return high-level KPIs for the overview dashboard."""
        try:
            vendors = self.db.get_vendors()
            perf = self.db.get_performance_data()
            risk = self.db.get_risk_data()
            fin = self.db.get_financial_summary()

            total_vendors = len(vendors)
            active_vendors = int((vendors["status"].str.lower() == "active").sum()) if not vendors.empty else 0
            avg_performance = round(float(perf["overall_score"].mean()), 1) if not perf.empty else 0.0
            high_risk_count = int((risk["risk_level"].str.lower() == "high").sum()) if not risk.empty else 0
            total_contract = float(vendors["contract_value"].sum()) if not vendors.empty else 0.0
            total_savings = float(fin["cost_savings"].sum()) if not fin.empty else 0.0

            return {
                "total_vendors": total_vendors,
                "active_vendors": active_vendors,
                "avg_performance": avg_performance,
                "high_risk_count": high_risk_count,
                "total_contract_value": total_contract,
                "total_cost_savings": total_savings,
            }
        except Exception as e:
            logger.error(f"KPI summary error: {e}")
            return {}

    def get_performance_trends(self) -> pd.DataFrame:
        try:
            return self.db.get_performance_trends()
        except Exception as e:
            logger.error(f"Performance trends error: {e}")
            return pd.DataFrame()

    def get_risk_distribution(self) -> pd.DataFrame:
        try:
            risk = self.db.get_risk_data()
            if risk.empty:
                return pd.DataFrame()
            return risk["risk_level"].value_counts().reset_index().rename(
                columns={"index": "risk_level", "risk_level": "count"})
        except Exception as e:
            logger.error(f"Risk distribution error: {e}")
            return pd.DataFrame()

    def get_recent_alerts(self) -> list:
        try:
            perf = self.db.get_vendors_with_performance()
            alerts = []
            if perf.empty:
                return alerts
            threshold = 70
            low_perf = perf[perf["avg_performance"].fillna(0) < threshold]
            for _, row in low_perf.head(5).iterrows():
                alerts.append({
                    "type": "⚠️ Low Performance",
                    "vendor": row.get("name", "Unknown"),
                    "message": f"Performance score {row.get('avg_performance', 0):.1f}% < {threshold}% threshold",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                })
            return alerts
        except Exception as e:
            logger.error(f"Alerts error: {e}")
            return []