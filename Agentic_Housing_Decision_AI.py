from dataclasses import dataclass
from typing import Optional, Dict
import math

# ----------------------------
# 1. Data models
# ----------------------------

@dataclass
class UserProfile:
    location: str              # e.g. "Columbus, OH 43215"
    annual_income: float       # household income
    down_payment: float        # dollars (not %)
    cash_savings_after_dp: float  # savings remaining after down payment + closing
    current_rent: float        # monthly
    rent_growth_assumption: float = 0.03  # 3% default
    time_horizon_years: int = 7
    other_monthly_debts: float = 0.0      # loans, min CC payments
    credit_score_band: str = "680-720"    # rough band

@dataclass
class MarketSnapshot:
    mortgage_rate_30yr: float      # e.g. 0.065 for 6.5%
    median_price: float            # local median home price
    price_trend_1y: float          # % change over 1y, e.g. 0.08 for +8%
    price_trend_5y: float          # % change over 5y
    property_tax_rate: float       # annual % of home value
    insurance_rate: float          # annual % of home value
    typical_hoa_monthly: float     # ballpark

@dataclass
class EvaluationResult:
    metrics: Dict[str, float]
    score_breakdown: Dict[str, float]
    total_score: float
    label: str
    narrative_summary: str

# ----------------------------
# 2. Tools (stubs)
# ----------------------------

def fetch_market_snapshot(location: str, credit_band: str) -> MarketSnapshot:
    """
    TODO: Replace with real calls:
     - Mortgage API (Freddie Mac, etc.)
     - Zillow/Redfin/local MLS stats
    For now, return dummy but realistic values.
    """
    # Dummy values – replace with real data
    return MarketSnapshot(
        mortgage_rate_30yr=0.067,        # 6.7%
        median_price=350_000,
        price_trend_1y=0.04,             # +4% YoY
        price_trend_5y=0.35,             # +35% over 5y
        property_tax_rate=0.013,         # 1.3% of value /year
        insurance_rate=0.005,            # 0.5% of value /year
        typical_hoa_monthly=75.0
    )

def mortgage_payment(principal: float, annual_rate: float, years: int = 30) -> float:
    """Standard fixed-rate mortgage monthly payment (P&I)."""
    r = annual_rate / 12
    n = years * 12
    if r == 0:
        return principal / n
    return principal * (r * (1 + r)**n) / ((1 + r)**n - 1)

# ----------------------------
# 3. Core evaluator logic
# ----------------------------

class HousingDecisionAgent:
    def evaluate(self, user: UserProfile) -> EvaluationResult:
        market = fetch_market_snapshot(user.location, user.credit_score_band)

        # Assume user is looking roughly at the local median price
        home_price = market.median_price
        loan_amount = home_price - user.down_payment

        monthly_pi = mortgage_payment(loan_amount, market.mortgage_rate_30yr, years=30)
        monthly_taxes = home_price * market.property_tax_rate / 12
        monthly_insurance = home_price * market.insurance_rate / 12
        monthly_hoa = market.typical_hoa_monthly

        monthly_housing_cost = monthly_pi + monthly_taxes + monthly_insurance + monthly_hoa

        # Income metrics
        monthly_gross_income = user.annual_income / 12
        housing_dti = monthly_housing_cost / monthly_gross_income
        total_dti = (monthly_housing_cost + user.other_monthly_debts) / monthly_gross_income

        price_to_income = home_price / user.annual_income

        # Simple rent vs buy break-even heuristic
        rent_vs_own_gap = monthly_housing_cost - user.current_rent

        metrics = {
            "home_price": home_price,
            "loan_amount": loan_amount,
            "monthly_housing_cost": monthly_housing_cost,
            "monthly_pi": monthly_pi,
            "monthly_taxes": monthly_taxes,
            "monthly_insurance": monthly_insurance,
            "monthly_hoa": monthly_hoa,
            "housing_dti": housing_dti,
            "total_dti": total_dti,
            "price_to_income": price_to_income,
            "mortgage_rate_30yr": market.mortgage_rate_30yr,
            "price_trend_1y": market.price_trend_1y,
            "price_trend_5y": market.price_trend_5y,
            "rent_vs_own_gap": rent_vs_own_gap,
        }

        score_breakdown = self._score(user, market, metrics)
        total_score = sum(score_breakdown.values())
        label = self._label(total_score)

        narrative = self._narrative_summary(user, market, metrics, score_breakdown, label)

        return EvaluationResult(
            metrics=metrics,
            score_breakdown=score_breakdown,
            total_score=total_score,
            label=label,
            narrative_summary=narrative
        )

    # ------------------------
    # 4. Scoring rules
    # ------------------------

    def _score(self, user: UserProfile, market: MarketSnapshot, m: Dict[str, float]) -> Dict[str, float]:
        scores = {}

        # Rates
        r = market.mortgage_rate_30yr
        if r < 0.04:
            scores["rates"] = 3
        elif r < 0.06:
            scores["rates"] = 2
        elif r < 0.075:
            scores["rates"] = 1
        else:
            scores["rates"] = -1

        # Price-to-income
        pti = m["price_to_income"]
        if pti <= 3.5:
            scores["price_to_income"] = 3
        elif pti <= 5:
            scores["price_to_income"] = 1.5
        else:
            scores["price_to_income"] = -1

        # DTI & cash buffer
        dti = m["total_dti"]
        if dti < 0.33 and user.cash_savings_after_dp >= 6 * (m["monthly_housing_cost"] + user.other_monthly_debts):
            scores["affordability"] = 4
        elif dti < 0.43 and user.cash_savings_after_dp >= 3 * (m["monthly_housing_cost"] + user.other_monthly_debts):
            scores["affordability"] = 2
        else:
            scores["affordability"] = -2

        # Market trend
        if market.price_trend_5y > 0.4 and market.price_trend_1y > 0.08:
            scores["market_trend"] = -1    # possibly overheated
        elif 0 <= market.price_trend_1y <= 0.05:
            scores["market_trend"] = 2     # steady
        elif market.price_trend_1y < 0:
            scores["market_trend"] = 0.5   # slight softening
        else:
            scores["market_trend"] = 1

        # Rent vs buy horizon
        # Rough break-even years: if owning costs more per month, how long until equity likely offsets?
        extra_annual_cost = max(m["monthly_housing_cost"] - user.current_rent, 0) * 12
        typical_appreciation = market.price_trend_5y / 5 if market.price_trend_5y > 0 else 0.02
        expected_equity_gain_per_year = home_price * typical_appreciation * 0.5  # very rough
        if extra_annual_cost == 0:
            breakeven_years = 0
        else:
            breakeven_years = extra_annual_cost / (expected_equity_gain_per_year + 1e-6)

        if user.time_horizon_years > breakeven_years + 2:
            scores["horizon"] = 3
        elif user.time_horizon_years >= breakeven_years:
            scores["horizon"] = 1
        else:
            scores["horizon"] = -1

        return scores

    def _label(self, total_score: float) -> str:
        if total_score >= 11:
            return "Leaning BUY (financially favorable if you're emotionally ready)"
        elif total_score >= 7:
            return "Borderline / Depends on your risk tolerance and non-financial priorities"
        else:
            return "Leaning WAIT (numbers suggest caution or more preparation)"

    # ------------------------
    # 5. Narrative explanation
    # ------------------------

    def _narrative_summary(
        self,
        user: UserProfile,
        market: MarketSnapshot,
        m: Dict[str, float],
        sb: Dict[str, float],
        label: str
    ) -> str:
        # In a full "agentic" build, you'd actually call an LLM here,
        # passing metrics + scores and asking it to explain in plain English.
        # For now, we do a simple handcrafted summary.
        lines = []

        lines.append(f"Decision: {label}")
        lines.append("")
        lines.append("Key metrics:")
        lines.append(f"- Local median home price: ${m['home_price']:,.0f}")
        lines.append(f"- 30-year fixed mortgage rate: {m['mortgage_rate_30yr']*100:.2f}%")
        lines.append(f"- Price-to-income ratio: {m['price_to_income']:.2f}x")
        lines.append(f"- Monthly housing cost (PITI+HOA): ${m['monthly_housing_cost']:,.0f}")
        lines.append(f"- Total DTI with new mortgage: {m['total_dti']*100:.1f}%")
        lines.append(f"- Current rent: ${user.current_rent:,.0f}")
        lines.append("")

        lines.append("Interpretation:")
        if sb["affordability"] <= 0:
            lines.append("- Your affordability metrics (DTI and/or cash buffer) are a major constraint.")
        else:
            lines.append("- Your affordability metrics suggest this purchase is reasonably within reach.")

        if sb["rates"] < 0:
            lines.append("- Mortgage rates are relatively high by historical standards, which argues for caution.")
        elif sb["rates"] >= 2:
            lines.append("- Mortgage rates are relatively attractive, which supports buying sooner rather than later.")

        if sb["price_to_income"] < 0:
            lines.append("- The local price-to-income ratio is elevated, indicating your market may be expensive.")
        else:
            lines.append("- The price-to-income ratio in your area is within a historically reasonable range.")

        if sb["horizon"] < 0:
            lines.append("- Given your time horizon, you may not own long enough to offset transaction costs.")
        else:
            lines.append("- Your expected holding period is long enough to potentially benefit from equity growth.")

        lines.append("")
        lines.append("Remember: This is an educational model, not individualized financial advice. "
                     "Consider also job stability, health, family plans, and your emotional comfort with risk.")

        return "\n".join(lines)


# ----------------------------
# 6. Example usage
# ----------------------------

if __name__ == "__main__":
    user = UserProfile(
        location="Columbus, OH 43215",
        annual_income=90_000,
        down_payment=50_000,
        cash_savings_after_dp=25_000,
        current_rent=1_600,
        other_monthly_debts=300,
        time_horizon_years=7
    )

    agent = HousingDecisionAgent()
    result = agent.evaluate(user)

    print(result.narrative_summary)
    print("\nScore breakdown:", result.score_breakdown)
    print("Total score:", result.total_score)
