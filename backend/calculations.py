import math
import json
from statistics import NormalDist

_STANDARD_NORMAL = NormalDist()

class AIRBCalculations:
    """Advanced Internal Ratings Based (AIRB) Approach calculations"""

    @staticmethod
    def calculate_pd(financial_metrics):
        """Calculate Probability of Default from financial metrics

        Args:
            financial_metrics (dict): Contains D/E, Interest Coverage, Profitability, Liquidity

        Returns:
            dict: PD value and calculation details
        """
        try:
            de_ratio = float(financial_metrics.get('de_ratio', 0))
            interest_coverage = float(financial_metrics.get('interest_coverage', 0))
            profitability = float(financial_metrics.get('profitability', 0))
            liquidity_ratio = float(financial_metrics.get('liquidity_ratio', 0))

            # Rule-based PD calculation
            pd = 0.01  # Base rate

            # D/E ratio impact (higher = more default risk)
            if de_ratio > 2:
                pd += 0.05
            elif de_ratio > 1.5:
                pd += 0.03
            elif de_ratio > 1:
                pd += 0.01

            # Interest coverage impact (lower = more default risk)
            if interest_coverage < 1.5:
                pd += 0.04
            elif interest_coverage < 2:
                pd += 0.02
            elif interest_coverage < 3:
                pd += 0.01

            # Profitability impact (negative = more default risk)
            if profitability < 0.02:
                pd += 0.03
            elif profitability < 0.05:
                pd += 0.02

            # Liquidity impact (lower = more default risk)
            if liquidity_ratio < 1:
                pd += 0.03
            elif liquidity_ratio < 1.5:
                pd += 0.01

            # Ensure PD is within valid range [0.0003, 1.0]
            pd = max(0.0003, min(1.0, pd))

            return {
                'pd': round(pd, 4),
                'pd_percentage': round(pd * 100, 2),
                'breakdown': {
                    'base_rate': 0.01,
                    'de_ratio_adjustment': de_ratio,
                    'interest_coverage_adjustment': interest_coverage,
                    'profitability_adjustment': profitability,
                    'liquidity_adjustment': liquidity_ratio
                }
            }
        except (ValueError, TypeError) as e:
            return {'error': f'Invalid input: {str(e)}', 'pd': None}

    @staticmethod
    def calculate_correlation(pd, exposure_class=None):
        """Calculate correlation coefficient R based on PD and Basel exposure class.

        Basel III AIRB specifies THREE different correlation treatments, not
        one - using the wholesale (corporate/sovereign/bank) formula for a
        retail exposure understates risk for low-PD retail mortgages and
        overstates it for revolving retail, and is not Basel-compliant:

        Wholesale (corporate/sovereign/bank/SME/etc. - the default):
            R = 0.12*(1-EXP(-50*PD))/(1-EXP(-50)) + 0.24*(1-(1-EXP(-50*PD))/(1-EXP(-50)))
        Retail residential mortgage: R = 0.15 (fixed, no PD dependence)
        Retail qualifying revolving (credit cards/overdrafts): R = 0.04 (fixed)
        Retail other (auto/personal/education loans):
            R = 0.03*(1-EXP(-35*PD))/(1-EXP(-35)) + 0.16*(1-(1-EXP(-35*PD))/(1-EXP(-35)))

        exposure_class is matched case-insensitively against the platform's
        EXPOSURE_CLASSES codes; anything not one of the three retail codes
        (including None/unrecognised) gets the wholesale formula, matching
        prior behaviour for every non-retail caller.
        """
        try:
            pd = float(pd)
            if pd <= 0 or pd > 1:
                return {'error': 'PD must be between 0.0001 and 1.0'}

            ec = (exposure_class or '').strip().upper()

            if ec == 'RETAIL_MORTGAGES':
                return {'r': 0.15, 'formula_used': 'Basel III AIRB retail residential mortgage (fixed R)'}
            if ec == 'RETAIL_REVOLVING':
                return {'r': 0.04, 'formula_used': 'Basel III AIRB qualifying revolving retail (fixed R)'}
            if ec == 'RETAIL_OTHER':
                exp_35 = math.exp(-35)
                exp_35_pd = math.exp(-35 * pd)
                part1 = 0.03 * (1 - exp_35_pd) / (1 - exp_35)
                part2 = 0.16 * (1 - (1 - exp_35_pd) / (1 - exp_35))
                return {'r': round(part1 + part2, 6), 'formula_used': 'Basel III AIRB other retail'}

            exp_50 = math.exp(-50)
            exp_50_pd = math.exp(-50 * pd)

            part1 = 0.12 * (1 - exp_50_pd) / (1 - exp_50)
            part2 = 0.24 * (1 - (1 - exp_50_pd) / (1 - exp_50))

            r = part1 + part2
            return {
                'r': round(r, 6),
                'formula_used': 'Basel III AIRB wholesale (corporate/sovereign/bank) correlation'
            }
        except (ValueError, TypeError) as e:
            return {'error': f'Invalid PD: {str(e)}'}

    @staticmethod
    def calculate_maturity_adjustment(maturity, lgd, pd, exposure_class=None):
        """Calculate maturity adjustment factor.

        Formula (wholesale exposures only):
        b = (0.11852 - 0.05478 × LN(PD))²
        MA = (1 + (M - 2.5) × 1.5 × b) / (1 - 1.5 × b)

        Basel III explicitly EXCLUDES retail exposures from the maturity
        adjustment (effective maturity is fixed at 1 year for retail AIRB) -
        applying the wholesale b-factor formula to a retail exposure
        overstates capital for maturities above 2.5 years and understates it
        below. Retail exposure classes therefore return a neutral MA=1.0
        rather than running the wholesale formula.
        """
        ec = (exposure_class or '').strip().upper()
        if ec in ('RETAIL_MORTGAGES', 'RETAIL_REVOLVING', 'RETAIL_OTHER'):
            try:
                m = float(maturity)
            except (ValueError, TypeError):
                m = 1.0
            return {'maturity_adjustment': 1.0, 'b_coefficient': 0.0, 'maturity_years': m,
                    'note': 'Retail exposures are excluded from the AIRB maturity adjustment under Basel III'}
        try:
            m = float(maturity)
            lgd_val = float(lgd)
            pd_val = float(pd)

            if m < 1 or m > 5:
                return {'error': 'Maturity must be between 1 and 5 years'}
            if pd_val <= 0 or pd_val > 1:
                return {'error': 'PD must be between 0.0001 and 1.0'}

            # Calculate b coefficient
            ln_pd = math.log(pd_val)
            b = (0.11852 - 0.05478 * ln_pd) ** 2

            # Calculate maturity adjustment
            numerator = 1 + (m - 2.5) * 1.5 * b
            denominator = 1 - 1.5 * b

            if denominator == 0:
                return {'error': 'Invalid maturity adjustment calculation'}

            ma = numerator / denominator

            return {
                'maturity_adjustment': round(ma, 6),
                'b_coefficient': round(b, 6),
                'maturity_years': m
            }
        except (ValueError, TypeError) as e:
            return {'error': f'Invalid input: {str(e)}'}

    @staticmethod
    def calculate_risk_weight(pd, lgd, ead, maturity, exposure_class=None, borrower_type=None):
        """Calculate risk weight using AIRB formula, correctly segmented by
        Basel exposure class (see calculate_correlation / calculate_maturity_adjustment
        docstrings for the wholesale-vs-retail distinction this now makes).

        `borrower_type` is accepted for backward compatibility with older
        callers but exposure_class is authoritative; if only borrower_type is
        given, it's used in its place (a caller previously passing a Basel
        exposure-class code as `borrower_type` keeps working unchanged).

        This is a simplified version - full AIRB is more complex.
        """
        try:
            pd_val = float(pd)
            lgd_val = float(lgd) / 100  # Convert percentage to decimal
            ec = exposure_class or borrower_type

            # Get correlation
            corr_result = AIRBCalculations.calculate_correlation(pd_val, ec)
            if 'error' in corr_result:
                return corr_result

            r = corr_result['r']

            # Get maturity adjustment
            ma_result = AIRBCalculations.calculate_maturity_adjustment(maturity, lgd_val, pd_val, ec)
            if 'error' in ma_result:
                return ma_result

            ma = ma_result['maturity_adjustment']

            # Basel II/III AIRB corporate risk-weight formula (BCBS128, para 272):
            #   K = [LGD * N( sqrt(1/(1-R))*G(PD) + sqrt(R/(1-R))*G(0.999) ) - PD*LGD] * MA
            #   RW% = K * 12.5 * 100
            #
            # PREVIOUSLY BUGGY: this used inverse_pd*sqrt(R/(1-R)) (wrong
            # coefficient - should be 1/sqrt(1-R) on the G(PD) term, and
            # sqrt(R/(1-R)) belongs on the G(0.999) term instead, matching
            # below) and, critically, never wrapped the bracketed term in the
            # standard normal CDF N(.) before treating it as a probability -
            # it used the raw Z-score-like value directly. That made RW
            # explode to the 1250% cap for completely ordinary PD/LGD
            # combinations (verified: PD=2%, LGD=35%, M=2.5y -> old code gave
            # 1250%; correct Basel formula gives ~45%).
            inverse_pd = AIRBCalculations._inverse_normal(pd_val)
            inverse_999 = 3.09  # Φ^(-1)(0.999)

            correlation_term = (
                (1.0 / math.sqrt(1 - r)) * inverse_pd
                + math.sqrt(r / (1 - r)) * inverse_999
            )
            conditional_pd = AIRBCalculations._normal_cdf(correlation_term)

            capital_requirement = (lgd_val * conditional_pd - pd_val * lgd_val) * ma

            # Cap at max 1250 (1250% in percentage terms, or 12.5 as decimal)
            rw = capital_requirement * 12.5 * 100  # Convert to percentage
            rw = max(0, min(rw, 1250))

            return {
                'risk_weight': round(rw, 2),
                'components': {
                    'correlation': round(r, 6),
                    'maturity_adjustment': round(ma, 6),
                    'b_coefficient': round(ma_result.get('b_coefficient', 0.0), 6),
                    'lgd': round(lgd_val * 100, 2)
                }
            }
        except (ValueError, TypeError) as e:
            return {'error': f'Invalid input: {str(e)}'}

    @staticmethod
    def _normal_cdf(x):
        """Standard normal CDF N(x), exact (via math.erf, not an approximation)."""
        return 0.5 * (1.0 + math.erf(x / math.sqrt(2)))

    @staticmethod
    def _inverse_normal(p):
        """Inverse standard normal CDF (exact, via statistics.NormalDist).

        PREVIOUSLY BUGGY: a hand-rolled rational approximation whose
        coefficients didn't correspond to any standard algorithm - e.g.
        Φ⁻¹(0.20) returned -2.12 instead of the correct -0.842. Silently
        wrong for every PD except round tail values, which is why the
        AIRB risk-weight formula (calculate_risk_weight, which consumes
        this) produced nonsensical results (see that function's docstring)."""
        if p <= 0 or p >= 1:
            return 0
        return _STANDARD_NORMAL.inv_cdf(p)

    # Basel III finalized-reforms minimum LGD input floor (BCBS 424, para 79) -
    # even a fully/over-collateralized exposure may not be treated as risk-free;
    # a regulator-set floor guards against an AIRB model implying near-zero loss
    # severity purely from collateral coverage assumptions.
    REGULATORY_LGD_FLOOR = 0.10  # 10%

    # Financial-collateral haircuts (Basel comprehensive approach, simplified
    # supervisory haircuts). Class-level constant so backend/collateral_store.py
    # can reuse the exact same table when persisting a collateral_register row,
    # instead of a second hand-typed copy silently drifting from this one.
    COLLATERAL_HAIRCUTS = {
        'Cash': 0.00,
        'Government Securities': 0.05,
        'Corporate Bonds': 0.10,
        'Equities': 0.20,
        'Other': 0.25,
    }
    DEFAULT_HAIRCUT = 0.25  # unrecognised collateral_type

    @staticmethod
    def calculate_lgd(seniority, collateral_type=None, collateral_value=0, exposure=0):
        """Calculate Loss Given Default from seniority and collateral

        Base LGD by seniority (must match the borrower-info.html seniority
        dropdown values exactly, or a submission silently falls through to the
        45% default and loses its tier - keep both lists in sync):
        - Senior Secured (Real Estate):     30%
        - Senior Secured (Financial Assets): 35%
        - Senior Secured (Other):            40%
        - Senior Secured (generic, direct API callers): 25%
        - Senior Unsecured:                  45%
        - Subordinated:                      75%
        - Junior:                            90%

        A regulatory minimum LGD floor (10%, see REGULATORY_LGD_FLOOR) is
        applied after the collateral adjustment, so no exposure - however
        well collateralized - is ever treated as carrying zero loss severity.
        """
        try:
            base_lgd_map = {
                'Senior Secured (Real Estate)':      0.30,
                'Senior Secured (Financial Assets)':  0.35,
                'Senior Secured (Other)':             0.40,
                'Senior Secured':                     0.25,
                'Senior Unsecured':                   0.45,
                'Subordinated':                       0.75,
                'Junior':                              0.90
            }

            base_lgd = base_lgd_map.get(seniority, 0.45)

            # Apply collateral adjustment
            if collateral_type and collateral_value > 0 and exposure > 0:
                haircut = AIRBCalculations.COLLATERAL_HAIRCUTS.get(
                    collateral_type, AIRBCalculations.DEFAULT_HAIRCUT)
                effective_collateral = collateral_value * (1 - haircut)

                # LGD applies only to the uncovered portion of exposure - NOT a
                # flat subtraction of the coverage ratio from the LGD rate.
                # (The old `base_lgd - coverage_ratio` formula treated a ratio
                # and a rate as the same unit, so any normally-collateralized
                # loan - coverage well above the ~25-45% base LGD itself -
                # floored straight to 0% instead of scaling down proportionally.)
                coverage_ratio = min(1.0, effective_collateral / exposure)
                lgd = base_lgd * (1 - coverage_ratio)
            else:
                lgd = base_lgd

            pre_floor_lgd = lgd
            lgd = max(AIRBCalculations.REGULATORY_LGD_FLOOR, lgd)
            floor_applied = lgd > pre_floor_lgd

            return {
                'lgd': round(lgd, 4),
                'lgd_percentage': round(lgd * 100, 2),
                'base_lgd': round(base_lgd * 100, 2),
                'regulatory_floor_pct': round(AIRBCalculations.REGULATORY_LGD_FLOOR * 100, 2),
                'floor_applied': floor_applied,
                'seniority': seniority
            }
        except (ValueError, TypeError, ZeroDivisionError) as e:
            return {'error': f'Invalid input: {str(e)}'}

    @staticmethod
    def calculate_rwa_and_capital(exposure, risk_weight):
        """Calculate Risk-Weighted Assets and Capital Requirement

        RWA = Exposure × Risk Weight
        Capital Required = RWA × 8%
        """
        try:
            ead = float(exposure)
            rw = float(risk_weight) / 100 if risk_weight > 10 else float(risk_weight)

            rwa = ead * rw
            capital_required = rwa * 0.08

            return {
                'rwa': round(rwa, 2),
                'capital_required': round(capital_required, 2),
                'exposure': round(ead, 2),
                'risk_weight': round(risk_weight, 2)
            }
        except (ValueError, TypeError) as e:
            return {'error': f'Invalid input: {str(e)}'}


class StandardizedApproachCalculations:
    """Standardized Approach for Credit Risk calculations"""

    RISK_WEIGHT_TABLES = {
        'Corporate': {
            'AAA': 20, 'AA+': 20, 'AA': 20, 'AA-': 20,
            'A+': 50, 'A': 50, 'A-': 50,
            'BBB+': 75, 'BBB': 75, 'BBB-': 75,
            'BB+': 100, 'BB': 100, 'BB-': 100,
            'B+': 100, 'B': 100, 'B-': 100,
            'CCC+': 150, 'CCC': 150, 'CCC-': 150,
            'CC': 150, 'C': 150, 'D': 150,
            'Unrated': 100
        },
        'Sovereign': {
            'AAA': 0, 'AA+': 20, 'AA': 20, 'AA-': 20,
            'A+': 50, 'A': 50, 'A-': 50,
            'BBB+': 50, 'BBB': 50, 'BBB-': 50,
            'BB+': 100, 'BB': 100, 'BB-': 100,
            'B+': 100, 'B': 100, 'B-': 100,
            'CCC+': 150, 'CCC': 150, 'CCC-': 150,
            'CC': 150, 'C': 150, 'D': 150,
            'Unrated': 100
        },
        'Bank': {
            'AAA': 20, 'AA+': 20, 'AA': 20, 'AA-': 20,
            'A+': 50, 'A': 50, 'A-': 50,
            'BBB+': 75, 'BBB': 75, 'BBB-': 75,
            'BB+': 100, 'BB': 100, 'BB-': 100,
            'B+': 100, 'B': 100, 'B-': 100,
            'CCC+': 150, 'CCC': 150, 'CCC-': 150,
            'CC': 150, 'C': 150, 'D': 150,
            'Unrated': 100
        },
        'Financial': {
            'AAA': 20, 'AA+': 20, 'AA': 20, 'AA-': 20,
            'A+': 50, 'A': 50, 'A-': 50,
            'BBB+': 75, 'BBB': 75, 'BBB-': 75,
            'BB+': 100, 'BB': 100, 'BB-': 100,
            'B+': 100, 'B': 100, 'B-': 100,
            'CCC+': 150, 'CCC': 150, 'CCC-': 150,
            'CC': 150, 'C': 150, 'D': 150,
            'Unrated': 100
        }
    }

    # Phase 6 — was a hand-typed duplicate of AIRBCalculations.COLLATERAL_HAIRCUTS
    # (identical values, by luck, with nothing enforcing that). Reference the
    # single source instead so the AIRB and SA collateral haircut tables can
    # never silently diverge.
    HAIRCUTS = AIRBCalculations.COLLATERAL_HAIRCUTS

    @staticmethod
    def get_risk_weight(category, rating):
        """Get risk weight from tables

        Args:
            category (str): Exposure category (Corporate, Sovereign, Bank, Financial)
            rating (str): External rating (AAA to D, or Unrated)

        Returns:
            dict: Risk weight or error
        """
        try:
            if category not in StandardizedApproachCalculations.RISK_WEIGHT_TABLES:
                return {'error': f'Invalid category: {category}'}

            table = StandardizedApproachCalculations.RISK_WEIGHT_TABLES[category]

            if rating not in table:
                return {'error': f'Invalid rating: {rating}'}

            rw = table[rating]

            return {
                'risk_weight': rw,
                'category': category,
                'rating': rating
            }
        except Exception as e:
            return {'error': f'Error getting risk weight: {str(e)}'}

    @staticmethod
    def calculate_with_collateral(exposure, collateral_type=None, collateral_value=0):
        """Calculate exposure adjusted for collateral

        Formula: Adjusted Exposure = Max(Exposure - (Collateral × (1 - Haircut)), 0)
        """
        try:
            ead = float(exposure)

            if not collateral_type or collateral_value <= 0:
                return {
                    'adjusted_exposure': round(ead, 2),
                    'collateral_effect': 0,
                    'haircut': 0
                }

            haircut = StandardizedApproachCalculations.HAIRCUTS.get(collateral_type, 0.25)
            collateral_value = float(collateral_value)

            # Collateral can't exceed exposure
            collateral_value = min(collateral_value, ead)

            # Calculate effective collateral value after haircut
            effective_collateral = collateral_value * (1 - haircut)

            # Adjusted exposure
            adjusted_exposure = max(ead - effective_collateral, 0)

            return {
                'adjusted_exposure': round(adjusted_exposure, 2),
                'original_exposure': round(ead, 2),
                'collateral_effect': round(ead - adjusted_exposure, 2),
                'collateral_type': collateral_type,
                'haircut': round(haircut * 100, 2),
                'effective_collateral': round(effective_collateral, 2)
            }
        except (ValueError, TypeError) as e:
            return {'error': f'Invalid input: {str(e)}'}

    @staticmethod
    def calculate_rwa_and_capital(exposure, risk_weight, collateral_type=None, collateral_value=0):
        """Calculate RWA and capital for Standardized Approach

        Args:
            exposure (float): Exposure amount
            risk_weight (float): Risk weight percentage (0-1250%)
            collateral_type (str, optional): Type of collateral
            collateral_value (float, optional): Collateral value

        Returns:
            dict: RWA, capital required, and component details
        """
        try:
            # Adjust for collateral
            collateral_result = StandardizedApproachCalculations.calculate_with_collateral(
                exposure, collateral_type, collateral_value
            )

            if 'error' in collateral_result:
                return collateral_result

            adjusted_exp = collateral_result['adjusted_exposure']
            rw = float(risk_weight) / 100

            # Calculate RWA
            rwa = adjusted_exp * rw

            # Calculate capital requirement (8% of RWA)
            capital_required = rwa * 0.08

            return {
                'rwa': round(rwa, 2),
                'capital_required': round(capital_required, 2),
                'adjusted_exposure': round(adjusted_exp, 2),
                'risk_weight': round(risk_weight, 2),
                'risk_weight_decimal': round(rw, 4),
                'collateral_adjustment': collateral_result
            }
        except (ValueError, TypeError) as e:
            return {'error': f'Invalid input: {str(e)}'}


class PortfolioCalculations:
    """Portfolio-level calculations and summaries"""

    @staticmethod
    def calculate_portfolio_summary(loans):
        """Calculate summary statistics for a portfolio of loans

        Args:
            loans (list): List of loan dictionaries

        Returns:
            dict: Portfolio summary statistics
        """
        if not loans:
            return {
                'total_loans': 0,
                'total_exposure': 0,
                'total_rwa': 0,
                'average_risk_density': 0,
                'total_capital_required': 0,
                'loans_by_method': {'AIRB': 0, 'SA': 0},
                'average_pd': 0,
                'average_risk_weight': 0
            }

        total_exposure = 0
        total_rwa = 0
        total_capital = 0
        total_pd = 0
        total_rw = 0
        airb_loans = 0
        sa_loans = 0

        for loan in loans:
            try:
                exposure = float(loan.get('exposure', 0))
                rwa = float(loan.get('rwa', 0))
                capital = float(loan.get('capital_required', 0))
                method = loan.get('calculation_method', 'AIRB')

                total_exposure += exposure
                total_rwa += rwa
                total_capital += capital

                if method == 'AIRB':
                    airb_loans += 1
                    pd = float(loan.get('pd', 0)) if 'pd' in loan else 0
                    total_pd += pd
                else:
                    sa_loans += 1
                    rw = float(loan.get('risk_weight', 0)) if 'risk_weight' in loan else 0
                    total_rw += rw

            except (ValueError, TypeError):
                continue

        total_loans = len(loans)
        risk_density = (total_rwa / total_exposure * 100) if total_exposure > 0 else 0

        return {
            'total_loans': total_loans,
            'total_exposure': round(total_exposure, 2),
            'total_rwa': round(total_rwa, 2),
            'average_risk_density': round(risk_density, 2),
            'total_capital_required': round(total_capital, 2),
            'capital_ratio': round(total_capital / total_exposure * 100, 2) if total_exposure > 0 else 0,
            'loans_by_method': {
                'AIRB': airb_loans,
                'SA': sa_loans
            },
            'average_pd': round(total_pd / airb_loans, 4) if airb_loans > 0 else 0,
            'average_risk_weight': round(total_rw / sa_loans, 2) if sa_loans > 0 else 0
        }
