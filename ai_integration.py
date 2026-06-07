from dotenv import load_dotenv
from pathlib import Path
import os
import json
import re
import textwrap
import warnings
from typing import Optional
import pandas as pd

# Anthropic SDK is optional — only needed for AI_MODE=real.
# Mock and Ollama modes work without it.
try:
    import anthropic
except ImportError:
    anthropic = None

warnings.filterwarnings(
    "ignore",
    message="urllib3 .* or chardet .*/charset_normalizer .* doesn't match a supported version!",
)
import requests

# ───────────── ENV LOADING ─────────────

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ⭐ AI MODE TOGGLE
# auto   -> free local Ollama first, then mock fallback
# ollama -> Ollama only
# real   -> Anthropic API only
# mock   -> local rule-based demo mode
AI_MODE = os.getenv("AI_MODE", "auto").lower()
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
LAST_AI_BACKEND = "uninitialized"


# ───────────── CLIENT ─────────────
class AIProvider:
    name = "unknown"

    def generate(self, system: str, user: str, max_tokens: int = 1024) -> str:
        raise NotImplementedError


class MockProvider(AIProvider):
    name = "mock"

    def generate(self, system: str, user: str, max_tokens: int = 1024) -> str:
        return _mock_claude_response(user)


class OllamaProvider(AIProvider):
    name = "ollama"

    def generate(self, system: str, user: str, max_tokens: int = 1024) -> str:
        return _call_ollama(system, user)


class AnthropicProvider(AIProvider):
    name = "anthropic"

    def generate(self, system: str, user: str, max_tokens: int = 1024) -> str:
        client = _get_client()
        message = client.messages.create(
            model=ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return message.content[0].text.strip()

def _get_client() -> "anthropic.Anthropic":
    if anthropic is None:
        raise EnvironmentError(
            "The 'anthropic' package is not installed. "
            "Run: pip install anthropic"
        )

    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY not found. Add it to your .env file."
        )

    return anthropic.Anthropic(api_key=api_key)


def _has_anthropic_key() -> bool:
    return anthropic is not None and bool(os.getenv("ANTHROPIC_API_KEY"))


def _call_ollama(system: str, user: str) -> str:
    response = requests.post(
        f"{OLLAMA_URL.rstrip('/')}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": f"{system}\n\n{user}",
            "stream": False,
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("response", "").strip()


# ───────────── MOCK AI HELPERS ─────────────
def _normalize_col(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name).lower())


def _find_column(df: pd.DataFrame, *candidates: str) -> Optional[str]:
    normalized = {_normalize_col(col): col for col in df.columns}
    for candidate in candidates:
        match = normalized.get(_normalize_col(candidate))
        if match:
            return match
    return None


def _extract_threshold(text: str, default: float = 70.0) -> float:
    match = re.search(r"(?:below|under|less than)\s+(\d+(?:\.\d+)?)", text.lower())
    if match:
        return float(match.group(1))

    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if match:
        return float(match.group(1))

    return default


def _extract_prompt_focus(user: str) -> str:
    for marker in ("QUESTION:", "TASK:"):
        if marker in user:
            return user.rsplit(marker, 1)[-1].strip()
    return user.strip()


def _extract_datasets_from_prompt(user: str) -> dict[str, pd.DataFrame]:
    datasets: dict[str, pd.DataFrame] = {}
    pattern = re.compile(
        r"--- (?P<label>.+?) DATA ---\n.*?JSON_DATA:\n(?P<json>\[.*?\])\n\nSTATISTICS:",
        re.DOTALL,
    )

    for match in pattern.finditer(user):
        label = match.group("label").strip().lower()
        payload = match.group("json")
        try:
            records = json.loads(payload)
            datasets[label] = pd.DataFrame(records)
        except json.JSONDecodeError:
            continue

    return datasets


def _pick_dataset(datasets: dict[str, pd.DataFrame], required_cols: tuple[str, ...]) -> pd.DataFrame:
    for df in datasets.values():
        if all(_find_column(df, col) for col in required_cols):
            return df.copy()

    for df in datasets.values():
        if any(_find_column(df, col) for col in required_cols):
            return df.copy()

    return pd.DataFrame()


def _vendor_column(df: pd.DataFrame) -> Optional[str]:
    return _find_column(df, "vendor_name", "vendor", "supplier_name", "supplier")


def _currency(value: float) -> str:
    return f"INR {value:,.2f}"


def _percent(value: float) -> str:
    return f"{value:.1f}%"


def _performance_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, Optional[str]]:
    if df.empty:
        return df, None

    vendor_col = _vendor_column(df)
    metric_cols = [
        col for col in (
            _find_column(df, "compliance_score", "compliance"),
            _find_column(df, "on_time_delivery", "on_time_delivery_rate", "delivery_rate"),
            _find_column(df, "quality_score", "quality"),
            _find_column(df, "performance_score", "performance"),
        )
        if col
    ]

    perf_df = df.copy()
    for col in metric_cols:
        perf_df[col] = pd.to_numeric(perf_df[col], errors="coerce")

    if metric_cols:
        perf_df["_composite_score"] = perf_df[metric_cols].mean(axis=1, skipna=True)

    return perf_df, vendor_col


def _financial_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, Optional[str], Optional[str]]:
    if df.empty:
        return df, None, None

    vendor_col = _vendor_column(df)
    variance_col = _find_column(df, "cost_variance", "cost_overrun", "variance")
    actual_col = _find_column(df, "actual_cost", "actual_spend")
    contract_col = _find_column(df, "contract_value", "budget", "planned_cost")

    fin_df = df.copy()
    for col in (variance_col, actual_col, contract_col):
        if col:
            fin_df[col] = pd.to_numeric(fin_df[col], errors="coerce")

    if not variance_col and actual_col and contract_col:
        variance_col = "_derived_cost_variance"
        fin_df[variance_col] = fin_df[actual_col] - fin_df[contract_col]

    return fin_df, vendor_col, variance_col


def _build_alert_json(user: str) -> str:
    values = {}
    for field in ("VENDOR", "METRIC", "PREVIOUS VALUE", "CURRENT VALUE", "CHANGE", "ALERT THRESHOLD"):
        match = re.search(rf"{re.escape(field)}:\s*(.+)", user)
        if match:
            values[field] = match.group(1).strip()

    vendor_name = values.get("VENDOR", "Vendor")
    metric = values.get("METRIC", "metric")
    previous_value = float(values.get("PREVIOUS VALUE", "0"))
    current_value = float(values.get("CURRENT VALUE", "0"))
    pct_change = float(str(values.get("CHANGE", "0")).replace("%", ""))
    threshold = float(values.get("ALERT THRESHOLD", "0"))

    threshold_gap_pct = 0.0 if threshold == 0 else ((threshold - current_value) / threshold) * 100

    if pct_change <= -20 or threshold_gap_pct > 30:
        severity = "critical"
        urgency = "immediate"
    elif pct_change <= -10 or threshold_gap_pct > 10:
        severity = "warning"
        urgency = "within 48 hours"
    else:
        severity = "info"
        urgency = "this week"

    payload = {
        "severity": severity,
        "subject": f"{metric.title()} alert for {vendor_name}",
        "headline": f"{vendor_name} {metric} moved from {previous_value:g} to {current_value:g}.",
        "explanation": (
            f"The latest {metric} reading is now below the target threshold of {threshold:g}. "
            f"This change suggests rising vendor risk and should be reviewed against recent operating performance."
        ),
        "recommendation": f"Review {vendor_name}'s {metric} trend and agree a corrective plan with the vendor owner.",
        "urgency": urgency,
    }
    return json.dumps(payload)


def _answer_data_question(question: str, datasets: dict[str, pd.DataFrame]) -> str:
    perf_df, perf_vendor_col = _performance_dataframe(
        _pick_dataset(datasets, ("compliance_score", "on_time_delivery", "quality_score"))
    )
    fin_df, fin_vendor_col, variance_col = _financial_dataframe(
        _pick_dataset(datasets, ("cost_variance", "actual_cost", "contract_value"))
    )

    question_lower = question.lower()

    if "how many vendor" in question_lower and perf_vendor_col:
        vendor_count = perf_df[perf_vendor_col].nunique()
        return f"There are {vendor_count} vendors in the available performance dataset."

    if ("average compliance" in question_lower or "mean compliance" in question_lower) and not perf_df.empty:
        compliance_col = _find_column(perf_df, "compliance_score", "compliance")
        if compliance_col:
            avg = pd.to_numeric(perf_df[compliance_col], errors="coerce").mean()
            return f"The average compliance score is {_percent(avg)}."

    if ("compliance" in question_lower and any(term in question_lower for term in ("below", "under", "less than"))) and not perf_df.empty:
        compliance_col = _find_column(perf_df, "compliance_score", "compliance")
        if compliance_col and perf_vendor_col:
            threshold = _extract_threshold(question)
            filtered = perf_df[pd.to_numeric(perf_df[compliance_col], errors="coerce") < threshold]
            if filtered.empty:
                return f"No vendors are below the {_percent(threshold)} compliance threshold."
            vendors = ", ".join(
                f"{row[perf_vendor_col]} ({_percent(float(row[compliance_col]))})"
                for _, row in filtered.sort_values(compliance_col).iterrows()
            )
            return f"The vendors below {_percent(threshold)} compliance are {vendors}."

    if any(term in question_lower for term in ("highest cost", "cost overrun", "cost escalation", "highest variance")) and not fin_df.empty:
        if variance_col and fin_vendor_col:
            row = fin_df.sort_values(variance_col, ascending=False).iloc[0]
            return f"{row[fin_vendor_col]} has the highest cost variance at {_currency(float(row[variance_col]))}."

    if any(term in question_lower for term in ("top vendor", "best vendor", "top performing", "highest performer")) and not perf_df.empty:
        if "_composite_score" in perf_df.columns and perf_vendor_col:
            row = perf_df.sort_values("_composite_score", ascending=False).iloc[0]
            return f"{row[perf_vendor_col]} is the top performing vendor with a composite score of {_percent(float(row['_composite_score']))}."

    if any(term in question_lower for term in ("at risk", "risk vendor", "lowest performing", "underperforming")) and not perf_df.empty:
        if "_composite_score" in perf_df.columns and perf_vendor_col:
            risk_rows = perf_df.sort_values("_composite_score").head(3)
            vendors = ", ".join(
                f"{row[perf_vendor_col]} ({_percent(float(row['_composite_score']))})"
                for _, row in risk_rows.iterrows()
            )
            return f"The highest-risk vendors are {vendors} based on the lowest combined performance metrics."

    if "on-time" in question_lower and any(term in question_lower for term in ("best", "highest", "top")) and not perf_df.empty:
        delivery_col = _find_column(perf_df, "on_time_delivery", "on_time_delivery_rate", "delivery_rate")
        if delivery_col and perf_vendor_col:
            row = perf_df.sort_values(delivery_col, ascending=False).iloc[0]
            return f"{row[perf_vendor_col]} has the strongest on-time delivery performance at {_percent(float(row[delivery_col]))}."

    if "quality" in question_lower and any(term in question_lower for term in ("best", "highest", "top")) and not perf_df.empty:
        quality_col = _find_column(perf_df, "quality_score", "quality")
        if quality_col and perf_vendor_col:
            row = perf_df.sort_values(quality_col, ascending=False).iloc[0]
            return f"{row[perf_vendor_col]} has the highest quality score at {_percent(float(row[quality_col]))}."

    if not perf_df.empty and perf_vendor_col:
        vendor_count = perf_df[perf_vendor_col].nunique()
        return (
            f"I found data for {vendor_count} vendors, but the mock AI cannot answer that question precisely yet. "
            "Try asking about compliance thresholds, top vendors, cost variance, average compliance, or risk."
        )

    return "I could not find enough structured vendor data in the prompt to answer reliably."


def _build_summary(task: str, datasets: dict[str, pd.DataFrame]) -> str:
    perf_df, perf_vendor_col = _performance_dataframe(
        _pick_dataset(datasets, ("compliance_score", "on_time_delivery", "quality_score"))
    )
    fin_df, fin_vendor_col, variance_col = _financial_dataframe(
        _pick_dataset(datasets, ("cost_variance", "actual_cost", "contract_value"))
    )

    if perf_df.empty or not perf_vendor_col or "_composite_score" not in perf_df.columns:
        return "The available data is not sufficient to produce a reliable summary."

    compliance_col = _find_column(perf_df, "compliance_score", "compliance")
    top_row = perf_df.sort_values("_composite_score", ascending=False).iloc[0]
    risk_rows = perf_df.sort_values("_composite_score").head(3)
    low_row = risk_rows.iloc[0]
    task_lower = task.lower()

    if "compliance-focused" in task_lower or "compliance threshold" in task_lower:
        if not compliance_col:
            return "Compliance data is not available for a compliance summary."
        below = perf_df[pd.to_numeric(perf_df[compliance_col], errors="coerce") < 70]
        if below.empty:
            return (
                f"Vendor compliance is currently stable, with no vendors below the 70.0% threshold. "
                f"{top_row[perf_vendor_col]} remains the strongest overall performer at {_percent(float(top_row['_composite_score']))}. "
                "Leadership should continue routine monitoring and maintain the current compliance review cadence."
            )
        names = ", ".join(
            f"{row[perf_vendor_col]} ({_percent(float(row[compliance_col]))})"
            for _, row in below.sort_values(compliance_col).iterrows()
        )
        return (
            f"Compliance performance is mixed, with {names} currently below the 70.0% threshold. "
            f"{low_row[perf_vendor_col]} presents the most immediate concern based on the weakest overall operating score of {_percent(float(low_row['_composite_score']))}. "
            "Management should prioritize remediation plans for the non-compliant vendors and review progress in the next reporting cycle."
        )

    if "financial analytics" in task_lower or "financial" in task_lower:
        if fin_df.empty or not fin_vendor_col or not variance_col:
            return "Financial data is not available for a financial summary."
        highest_variance = fin_df.sort_values(variance_col, ascending=False).iloc[0]
        return (
            f"Financial performance shows concentrated cost pressure across the vendor base. "
            f"{highest_variance[fin_vendor_col]} has the highest cost variance at {_currency(float(highest_variance[variance_col]))}, creating the clearest near-term financial exposure. "
            f"Operationally, {low_row[perf_vendor_col]} remains the weakest performer, which may increase downstream spend risk if performance declines continue. "
            "Leadership should review the highest-variance contracts and tighten cost controls on the most volatile suppliers."
        )

    if "risk assessment" in task_lower or "top 3 at-risk" in task_lower or "high risk" in task_lower:
        risk_text = ", ".join(
            f"{row[perf_vendor_col]} ({_percent(float(row['_composite_score']))})"
            for _, row in risk_rows.iterrows()
        )
        return (
            f"Current vendor risk is concentrated in {risk_text}, based on the weakest combined performance metrics. "
            f"{low_row[perf_vendor_col]} is the most exposed vendor in the portfolio and should be treated as the highest intervention priority. "
            f"In contrast, {top_row[perf_vendor_col]} continues to set the benchmark with a composite score of {_percent(float(top_row['_composite_score']))}. "
            "Procurement leaders should assign recovery owners to the highest-risk vendors and monitor progress weekly."
        )

    summary_parts = [
        f"Overall vendor performance is stable, led by {top_row[perf_vendor_col]} with a composite score of {_percent(float(top_row['_composite_score']))}.",
        f"{low_row[perf_vendor_col]} is currently the most at-risk vendor at {_percent(float(low_row['_composite_score']))} based on combined operational metrics.",
    ]
    if not fin_df.empty and fin_vendor_col and variance_col:
        highest_variance = fin_df.sort_values(variance_col, ascending=False).iloc[0]
        summary_parts.append(
            f"Financial exposure is highest for {highest_variance[fin_vendor_col]}, which shows a cost variance of {_currency(float(highest_variance[variance_col]))}."
        )
    summary_parts.append("Leadership should focus on stabilizing the lowest-performing vendors while preserving momentum with the strongest suppliers.")
    return " ".join(summary_parts)


def _mock_claude_response(user: str) -> str:
    prompt_focus = _extract_prompt_focus(user)
    datasets = _extract_datasets_from_prompt(user)
    user_lower = prompt_focus.lower()

    if '"severity"' in user or "return valid json" in user_lower:
        return _build_alert_json(user)

    if "summary" in user_lower or "write " in user_lower:
        return _build_summary(prompt_focus, datasets)

    return _answer_data_question(prompt_focus, datasets)


def _call_claude(system: str, user: str, max_tokens: int = 1024) -> str:
    global LAST_AI_BACKEND
    mode = AI_MODE.lower()
    mock_provider = MockProvider()

    if mode == "mock":
        LAST_AI_BACKEND = mock_provider.name
        return mock_provider.generate(system, user, max_tokens=max_tokens)

    if mode in {"auto", "ollama"}:
        try:
            response = OllamaProvider().generate(system, user, max_tokens=max_tokens)
            LAST_AI_BACKEND = f"ollama:{OLLAMA_MODEL}"
            return response
        except Exception:
            if mode == "ollama":
                raise

    if mode == "real" and _has_anthropic_key():
        try:
            response = AnthropicProvider().generate(system, user, max_tokens=max_tokens)
            LAST_AI_BACKEND = f"anthropic:{ANTHROPIC_MODEL}"
            return response
        except Exception:
            raise

    if mode == "real":
        raise EnvironmentError(
            "AI_MODE is set to 'real' but ANTHROPIC_API_KEY is missing."
        )

    LAST_AI_BACKEND = mock_provider.name
    return mock_provider.generate(system, user, max_tokens=max_tokens)


# ───────────── HELPERS ─────────────

def _dataframe_to_context(df: pd.DataFrame, max_rows: int = 50) -> str:
    sample = df.head(max_rows)
    stats = df.describe(include="all").to_string()
    return (
        f"COLUMNS: {list(df.columns)}\n\n"
        f"SAMPLE DATA:\n{sample.to_string(index=False)}\n\n"
        f"JSON_DATA:\n{sample.to_json(orient='records')}\n\n"
        f"STATISTICS:\n{stats}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE 1 — Ask Your Data
# ═══════════════════════════════════════════════════════════════════════════════

class VendorDataChat:
    """
    Natural language interface over vendor DataFrames.

    Usage (standalone):
        chat = VendorDataChat(performance_df, financial_df)
        answer = chat.ask("Which vendors have compliance below 70% this month?")
        print(answer)

    Usage (Streamlit):
        Add to app.py — see streamlit_chat_widget() below.
    """

    SYSTEM_PROMPT = textwrap.dedent("""
        You are a senior data analyst assistant for VendorInsight360, a vendor 
        performance analytics platform. You have access to vendor performance, 
        compliance, and financial data provided below.

        Rules:
        - Answer only based on the data provided. Never make up numbers.
        - Be concise and specific. Lead with the direct answer, then support with data.
        - When listing vendors, include their metric values.
        - If the data does not contain enough information to answer, say so clearly.
        - Format numbers cleanly: percentages as X%, currency with 2 decimal places.
        - Keep responses under 150 words unless a detailed breakdown is explicitly requested.
    """).strip()

    def __init__(self, *dataframes: pd.DataFrame, labels: Optional[list[str]] = None):
        """
        Pass one or more DataFrames. Optionally name them with labels=[...].
        Example:
            VendorDataChat(perf_df, fin_df, labels=["performance", "financial"])
        """
        if labels and len(labels) != len(dataframes):
            raise ValueError("labels length must match number of dataframes")

        self._context_parts = []
        for i, df in enumerate(dataframes):
            label = labels[i] if labels else f"Dataset {i + 1}"
            self._context_parts.append(
                f"--- {label.upper()} DATA ---\n{_dataframe_to_context(df)}"
            )

        self._context = "\n\n".join(self._context_parts)
        self._history: list[dict] = []

    def ask(self, question: str, use_history: bool = True) -> str:
        """Ask a plain-English question. Returns the AI answer as a string."""
        user_prompt = f"DATA CONTEXT:\n{self._context}\n\nQUESTION: {question}"

        if use_history and self._history:
            # Append history as prior context summary to keep tokens low
            prior = "\n".join(
                f"Q: {h['q']}\nA: {h['a']}" for h in self._history[-3:]
            )
            user_prompt = f"PRIOR CONVERSATION:\n{prior}\n\n{user_prompt}"

        answer = _call_claude(self.SYSTEM_PROMPT, user_prompt, max_tokens=512)

        if use_history:
            self._history.append({"q": question, "a": answer})

        return answer

    def reset_history(self):
        self._history = []


def streamlit_chat_widget(chat: VendorDataChat):
    """
    Drop-in Streamlit widget for the Ask Your Data feature.

    Add this to app.py:

        from ai_integration import VendorDataChat, streamlit_chat_widget
        import pandas as pd
        import streamlit as st

        perf_df = pd.read_csv("Data layer/performance.csv")
        fin_df  = pd.read_csv("Data layer/financial_metrics.csv")

        chat = VendorDataChat(perf_df, fin_df, labels=["performance", "financial"])

        st.header("Ask Your Vendor Data")
        streamlit_chat_widget(chat)
    """
    try:
        import streamlit as st
    except ImportError:
        raise ImportError("streamlit is required for streamlit_chat_widget()")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    # Render prior messages
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Input
    if prompt := st.chat_input("Ask about your vendors e.g. 'Which vendors are at risk?'"):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Analyzing..."):
                answer = chat.ask(prompt)
            st.markdown(answer)

        st.session_state.chat_history.append({"role": "assistant", "content": answer})


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE 2 — AI Report Summary Generator
# ═══════════════════════════════════════════════════════════════════════════════

class ReportSummaryGenerator:
    """
    Generates AI-written executive summaries for vendor reports.

    Usage:
        gen = ReportSummaryGenerator()

        summary = gen.generate(
            vendor_df=performance_df,
            financial_df=financial_df,
            period="Q1 2025",
            summary_type="executive"   # or "compliance" / "financial" / "risk"
        )

        # Inject into report_generator.py before PDF/HTML render
        print(summary)
    """

    SYSTEM_PROMPT = textwrap.dedent("""
        You are a senior data analyst writing formal vendor performance reports 
        for VendorInsight360. Your summaries are read by C-level executives and 
        procurement managers.

        Writing rules:
        - Use formal, professional language.
        - Be data-specific: always include real numbers from the data.
        - Structure: 1 sentence on overall status, 2-3 sentences on key findings, 
          1 sentence on recommended action.
        - Never use bullet points — write in flowing paragraphs.
        - Keep to 4-5 sentences maximum unless instructed otherwise.
        - Do not invent data. Only reference figures present in the provided dataset.
    """).strip()

    SUMMARY_PROMPTS = {
        "executive": (
            "Write an executive summary of overall vendor performance. "
            "Highlight the top performing vendor, the most at-risk vendor, "
            "and one clear recommendation for leadership."
        ),
        "compliance": (
            "Write a compliance-focused summary. Identify vendors below the 70% "
            "compliance threshold, note the trend direction, and recommend "
            "a specific compliance action."
        ),
        "financial": (
            "Write a financial analytics summary. Highlight cost trends, identify "
            "the vendor with the highest cost escalation, and recommend "
            "a financial risk mitigation step."
        ),
        "risk": (
            "Write a risk assessment summary. Identify the top 3 at-risk vendors "
            "based on combined performance and compliance metrics, explain what "
            "makes each high risk, and suggest priority actions."
        ),
    }

    def generate(
        self,
        vendor_df: pd.DataFrame,
        period: str = "Current Period",
        financial_df: Optional[pd.DataFrame] = None,
        summary_type: str = "executive",
    ) -> str:
        """
        Generate an AI executive summary.

        Args:
            vendor_df:     Performance/compliance DataFrame
            period:        Reporting period label e.g. "Q1 2025"
            financial_df:  Optional financial metrics DataFrame
            summary_type:  One of: executive | compliance | financial | risk

        Returns:
            A formatted string ready to embed in PDF/HTML reports.
        """
        if summary_type not in self.SUMMARY_PROMPTS:
            raise ValueError(
                f"summary_type must be one of: {list(self.SUMMARY_PROMPTS.keys())}"
            )

        data_context = f"REPORTING PERIOD: {period}\n\n"
        data_context += f"--- PERFORMANCE DATA ---\n{_dataframe_to_context(vendor_df)}"

        if financial_df is not None:
            data_context += (
                f"\n\n--- FINANCIAL DATA ---\n{_dataframe_to_context(financial_df)}"
            )

        task = self.SUMMARY_PROMPTS[summary_type]
        user_prompt = f"{data_context}\n\nTASK: {task}"

        return _call_claude(self.SYSTEM_PROMPT, user_prompt, max_tokens=400)

    def generate_all(
        self,
        vendor_df: pd.DataFrame,
        period: str = "Current Period",
        financial_df: Optional[pd.DataFrame] = None,
    ) -> dict[str, str]:
        """Generate all 4 summary types at once. Returns a dict keyed by type."""
        return {
            stype: self.generate(vendor_df, period, financial_df, stype)
            for stype in self.SUMMARY_PROMPTS
        }


def inject_summary_into_report(html_template: str, summaries: dict[str, str]) -> str:
    """
    Helper to inject AI summaries into an existing HTML report template.

    Expects placeholders in the HTML like:
        {{AI_EXECUTIVE_SUMMARY}}
        {{AI_COMPLIANCE_SUMMARY}}
        {{AI_FINANCIAL_SUMMARY}}
        {{AI_RISK_SUMMARY}}

    Usage:
        with open("report_template.html") as f:
            html = f.read()

        gen = ReportSummaryGenerator()
        summaries = gen.generate_all(perf_df, "Q1 2025", fin_df)
        final_html = inject_summary_into_report(html, summaries)
    """
    replacements = {
        "{{AI_EXECUTIVE_SUMMARY}}": summaries.get("executive", ""),
        "{{AI_COMPLIANCE_SUMMARY}}": summaries.get("compliance", ""),
        "{{AI_FINANCIAL_SUMMARY}}": summaries.get("financial", ""),
        "{{AI_RISK_SUMMARY}}": summaries.get("risk", ""),
    }
    for placeholder, content in replacements.items():
        html_template = html_template.replace(placeholder, f"<p>{content}</p>")
    return html_template


# ═══════════════════════════════════════════════════════════════════════════════
# FEATURE 3 — Smart Alert Explanations
# ═══════════════════════════════════════════════════════════════════════════════

class SmartAlertEngine:
    """
    Generates contextual, plain-English alert explanations with recommended actions.

    Usage:
        engine = SmartAlertEngine()

        alert = engine.explain(
            vendor_name="Vendor B",
            metric="compliance score",
            current_value=62,
            previous_value=78,
            threshold=70,
            historical_df=performance_df   # optional — for richer context
        )

        print(alert.subject)
        print(alert.body)
        print(alert.severity)   # "critical" | "warning" | "info"

        # Pass to email_service.py
        email_service.send(to=manager_email, subject=alert.subject, body=alert.body)
    """

    SYSTEM_PROMPT = textwrap.dedent("""
        You are an intelligent alert system for VendorInsight360, a vendor analytics 
        platform. Your job is to explain anomalies in vendor metrics clearly and 
        concisely for procurement managers who are not data experts.

        Response format — always return valid JSON exactly like this:
        {
            "severity": "critical|warning|info",
            "subject": "one-line email subject under 10 words",
            "headline": "one sentence summary of what happened",
            "explanation": "2 sentences explaining what this likely means and why it matters",
            "recommendation": "one specific, actionable recommendation",
            "urgency": "immediate|within 48 hours|this week"
        }

        Severity rules:
        - critical: drop > 20% or value > 30% below threshold
        - warning:  drop 10-20% or value 10-30% below threshold
        - info:     drop < 10% or value just at threshold

        Only return the JSON. No preamble, no explanation outside the JSON.
    """).strip()

    def explain(
        self,
        vendor_name: str,
        metric: str,
        current_value: float,
        previous_value: float,
        threshold: float,
        historical_df: Optional[pd.DataFrame] = None,
    ) -> "AlertResult":
        """
        Generate a smart alert explanation.

        Args:
            vendor_name:    Name of the vendor triggering the alert
            metric:         Metric name e.g. "compliance score", "on-time delivery rate"
            current_value:  Current metric value
            previous_value: Previous period's value
            threshold:      The alert threshold that was breached
            historical_df:  Optional DataFrame with vendor's history for richer context

        Returns:
            AlertResult dataclass with severity, subject, body, recommendation etc.
        """
        if previous_value == 0:
            pct_change = 0.0 if current_value == 0 else 100.0
        else:
            pct_change = round(
                ((current_value - previous_value) / previous_value) * 100, 1
            )

        user_prompt = (
            f"VENDOR: {vendor_name}\n"
            f"METRIC: {metric}\n"
            f"PREVIOUS VALUE: {previous_value}\n"
            f"CURRENT VALUE: {current_value}\n"
            f"CHANGE: {pct_change}%\n"
            f"ALERT THRESHOLD: {threshold}\n"
        )

        if historical_df is not None:
            vendor_history = historical_df[
                historical_df.apply(
                    lambda r: vendor_name.lower() in str(r.values).lower(), axis=1
                )
            ]
            if not vendor_history.empty:
                user_prompt += (
                    f"\nVENDOR HISTORICAL DATA:\n"
                    f"{_dataframe_to_context(vendor_history, max_rows=10)}"
                )

        raw = _call_claude(self.SYSTEM_PROMPT, user_prompt, max_tokens=300)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Fallback if model returns slightly malformed JSON
            data = {
                "severity": "warning",
                "subject": f"Alert: {vendor_name} {metric} dropped",
                "headline": f"{vendor_name} {metric} dropped from {previous_value} to {current_value}.",
                "explanation": f"The {metric} has fallen below the threshold of {threshold}.",
                "recommendation": "Review vendor performance and schedule a check-in call.",
                "urgency": "within 48 hours",
            }

        return AlertResult(
            vendor_name=vendor_name,
            metric=metric,
            current_value=current_value,
            previous_value=previous_value,
            pct_change=pct_change,
            threshold=threshold,
            **data,
        )

    def batch_explain(
        self,
        alerts: list[dict],
        historical_df: Optional[pd.DataFrame] = None,
    ) -> list["AlertResult"]:
        """
        Process multiple alerts at once.

        Args:
            alerts: list of dicts, each with keys:
                    vendor_name, metric, current_value, previous_value, threshold
            historical_df: optional shared historical DataFrame

        Returns:
            List of AlertResult objects sorted by severity (critical first)
        """
        results = [
            self.explain(**alert, historical_df=historical_df)
            for alert in alerts
        ]
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        return sorted(results, key=lambda r: severity_order.get(r.severity, 3))


class AlertResult:
    """Structured result from SmartAlertEngine.explain()"""

    SEVERITY_EMOJI = {"critical": "[CRITICAL]", "warning": "[WARNING]", "info": "[INFO]"}

    def __init__(
        self,
        vendor_name: str,
        metric: str,
        current_value: float,
        previous_value: float,
        pct_change: float,
        threshold: float,
        severity: str,
        subject: str,
        headline: str,
        explanation: str,
        recommendation: str,
        urgency: str,
    ):
        self.vendor_name = vendor_name
        self.metric = metric
        self.current_value = current_value
        self.previous_value = previous_value
        self.pct_change = pct_change
        self.threshold = threshold
        self.severity = severity
        self.subject = subject
        self.headline = headline
        self.explanation = explanation
        self.recommendation = recommendation
        self.urgency = urgency

    @property
    def email_subject(self) -> str:
        emoji = self.SEVERITY_EMOJI.get(self.severity, "")
        return f"{emoji} VendorInsight360 Alert: {self.subject}"

    @property
    def email_body(self) -> str:
        return textwrap.dedent(f"""
            VendorInsight360 - Automated Alert
            {'=' * 40}

            Vendor  : {self.vendor_name}
            Metric  : {self.metric}
            Change  : {self.previous_value} -> {self.current_value} ({self.pct_change:+.1f}%)
            Severity: {self.severity.upper()}
            Urgency : {self.urgency}

            WHAT HAPPENED
            {self.headline}

            ANALYSIS
            {self.explanation}

            RECOMMENDED ACTION
            {self.recommendation}

            {'-' * 40}
            This alert was generated automatically by VendorInsight360.
        """).strip()

    def to_dict(self) -> dict:
        return {
            "vendor_name": self.vendor_name,
            "metric": self.metric,
            "current_value": self.current_value,
            "previous_value": self.previous_value,
            "pct_change": self.pct_change,
            "severity": self.severity,
            "subject": self.subject,
            "headline": self.headline,
            "explanation": self.explanation,
            "recommendation": self.recommendation,
            "urgency": self.urgency,
        }

    def __repr__(self):
        return (
            f"AlertResult(vendor={self.vendor_name!r}, "
            f"metric={self.metric!r}, severity={self.severity!r})"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# QUICK TEST — run this file directly to verify all 3 features work
# python ai_integration.py
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import io

    # ── Synthetic test data ──────────────────────────────────────────────────
    PERF_CSV = """vendor_name,compliance_score,on_time_delivery,quality_score,month
Vendor A,85,92,88,2025-01
Vendor B,62,74,70,2025-01
Vendor C,91,95,93,2025-01
Vendor D,55,68,60,2025-01
Vendor E,78,85,82,2025-01"""

    FIN_CSV = """vendor_name,contract_value,actual_cost,cost_variance,month
Vendor A,100000,98000,-2000,2025-01
Vendor B,80000,95000,15000,2025-01
Vendor C,120000,118000,-2000,2025-01
Vendor D,60000,72000,12000,2025-01
Vendor E,90000,91000,1000,2025-01"""

    perf_df = pd.read_csv(io.StringIO(PERF_CSV))
    fin_df  = pd.read_csv(io.StringIO(FIN_CSV))

    print(f"AI mode: {AI_MODE}")

    print("\n" + "=" * 60)
    print("FEATURE 1 - Ask Your Data")
    print("=" * 60)
    chat = VendorDataChat(perf_df, fin_df, labels=["performance", "financial"])
    q1 = "Which vendors have compliance below 70%?"
    print(f"\nQ: {q1}")
    print(f"A: {chat.ask(q1)}")
    print(f"Backend used: {LAST_AI_BACKEND}")

    q2 = "Which vendor has the highest cost overrun?"
    print(f"\nQ: {q2}")
    print(f"A: {chat.ask(q2)}")
    print(f"Backend used: {LAST_AI_BACKEND}")

    print("\n" + "=" * 60)
    print("FEATURE 2 - AI Report Summary")
    print("=" * 60)
    gen = ReportSummaryGenerator()
    summary = gen.generate(perf_df, period="Q1 2025", financial_df=fin_df, summary_type="executive")
    print(f"\nExecutive Summary:\n{summary}")
    print(f"Backend used: {LAST_AI_BACKEND}")

    print("\n" + "=" * 60)
    print("FEATURE 3 - Smart Alert Explanation")
    print("=" * 60)
    engine = SmartAlertEngine()
    alert = engine.explain(
        vendor_name="Vendor B",
        metric="compliance score",
        current_value=62,
        previous_value=78,
        threshold=70,
        historical_df=perf_df,
    )
    print(f"\n{alert.email_subject}")
    print(f"\n{alert.email_body}")
    print(f"\nBackend used: {LAST_AI_BACKEND}")
