/**
 * Flask API Integration
 * Replaces local JavaScript calculations with calls to Flask backend
 *
 * This file provides helper functions to call the Flask API endpoints
 * and integrates them with the borrower-info.html application.
 */

// ============================================================================
// API CONFIGURATION
// ============================================================================

const API_CONFIG = {
    BASE_URL: '/api',
    TIMEOUT: 10000,  // 10 seconds
    RETRY_ATTEMPTS: 1
};

// ============================================================================
// GENERIC API CALL FUNCTION
// ============================================================================

/**
 * Generic function to make API calls to Flask backend
 * @param {string} endpoint - API endpoint path (e.g., '/calculate-pd')
 * @param {object} data - Request body data
 * @param {string} method - HTTP method (default: 'POST')
 * @returns {Promise<object>} API response data or null on error
 */
async function apiCall(endpoint, data = null, method = 'POST') {
    try {
        const url = `${API_CONFIG.BASE_URL}${endpoint}`;

        const options = {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            }
        };

        if (data && (method === 'POST' || method === 'PUT')) {
            options.body = JSON.stringify(data);
        }

        const response = await fetch(url, options);

        // Handle non-200 responses
        if (!response.ok) {
            console.error(`API error: ${response.status} ${response.statusText}`);
            showNotification('Error', `API call failed: ${response.status}`);
            return null;
        }

        // Parse and return JSON
        const result = await response.json();
        return result;

    } catch (error) {
        console.error(`API call failed: ${endpoint}`, error);

        if (error.name === 'TypeError' && error.message.includes('Failed to fetch')) {
            showNotification('Error', 'Cannot connect to Flask server. Make sure it is running on http://127.0.0.1:5000');
        } else {
            showNotification('Error', `API call failed: ${error.message}`);
        }

        return null;
    }
}

// ============================================================================
// HEALTH CHECK
// ============================================================================

/**
 * Check if Flask API is available
 * @returns {Promise<boolean>} True if API is healthy
 */
async function checkAPIHealth() {
    try {
        const response = await fetch(`${API_CONFIG.BASE_URL}/health`, { timeout: 5000 });
        return response.ok;
    } catch (error) {
        return false;
    }
}

// ============================================================================
// AIRB CALCULATION FUNCTIONS
// ============================================================================

/**
 * Calculate Probability of Default via Flask API
 * Supports both Rule-Based and ML methods
 * @param {number} debtToEquity - Debt-to-Equity ratio
 * @param {number} interestCoverage - Interest coverage ratio
 * @param {number} profitabilityMargin - Profitability margin
 * @param {number} liquidityRatio - Liquidity ratio
 * @param {string} pdMethod - Calculation method ('ml' for ML model, 'rule-based' for formulas)
 * @returns {Promise<object>} PD result with components and method info
 */
async function calculatePDFromAPI(debtToEquity, interestCoverage, profitabilityMargin, liquidityRatio, pdMethod = 'ml', kyc = {}) {
    const requestData = {
        de_ratio: debtToEquity,
        interest_coverage: interestCoverage,
        profitability: profitabilityMargin,
        liquidity_ratio: liquidityRatio,
        ...kyc
    };

    const endpoint = pdMethod === 'ml' ? '/predict-pd-ml' : '/calculate-pd';
    const result = await apiCall(endpoint, requestData);

    if (!result || result.error) {
        console.error('PD calculation error:', result?.error);
        // Fallback to rule-based if ML fails
        if (pdMethod === 'ml' && result?.error) {
            console.warn('ML prediction failed, falling back to rule-based');
            // Call rule-based endpoint directly to avoid infinite recursion
            const ruleBased = await apiCall('/calculate-pd', requestData);
            if (ruleBased && !ruleBased.error) {
                return {
                    pd: ruleBased.pd_percentage,
                    method: 'rule-based (fallback from ML)',
                    components: {
                        baseRate: ruleBased.breakdown?.base_rate || 0,
                        leverageImpact: ruleBased.breakdown?.de_ratio_adjustment || 0,
                        profitImpact: ruleBased.breakdown?.profitability_adjustment || 0,
                        liquidityImpact: ruleBased.breakdown?.liquidity_adjustment || 0,
                        coverageImpact: ruleBased.breakdown?.interest_coverage_adjustment || 0
                    }
                };
            }
        }
        return null;
    }

    // Convert to percentage for display. No component breakdown here - the ML
    // endpoint returns a single classifier output, not a formula decomposition
    // (see SHAP attribution for what actually drove this number).
    return {
        pd: result.pd_percentage,  // Already in percentage
        method: result.method || pdMethod,
    };
}

/**
 * Calculate Loss Given Default via Flask API
 * @param {string} seniority - Loan seniority level
 * @param {number} exposureAmount - Total exposure amount
 * @param {number} collateralValue - Collateral value (if any)
 * @param {string} collateralType - Type of collateral
 * @param {string} sector - Borrower sector
 * @returns {Promise<object>} LGD result with components
 */
async function calculateLGDFromAPI(seniority, exposureAmount, collateralValue, collateralType, sector) {
    // Map HTML collateral types to API types
    const collateralTypeMap = {
        'None': null,
        'Real Estate': 'Government Securities',  // Conservative mapping
        'Financial Assets': 'Corporate Bonds',
        'Equipment': 'Equities',
        'Inventory': 'Other',
        'Other': 'Other'
    };

    const apiCollateralType = collateralTypeMap[collateralType] || null;

    const result = await apiCall('/calculate-lgd', {
        seniority: seniority,
        collateral_type: apiCollateralType,
        collateral_value: collateralValue || 0,
        exposure: exposureAmount
    });

    if (!result || result.error) {
        console.error('LGD calculation error:', result?.error);
        return null;
    }

    // Map API result to expected format
    return {
        lgd: result.lgd_percentage,  // Already in percentage
        components: {
            baseLGD: result.base_lgd,  // Actual base rate by seniority tier, before collateral
            coverageRatio: (collateralValue / exposureAmount).toFixed(2),
            coverageAdj: result.lgd_percentage - result.base_lgd,  // Real reduction applied (<= 0)
            sectorAdj: 0,  // Sector adjustment is internal to Flask now
            regulatoryFloorPct: result.regulatory_floor_pct,
            floorApplied: result.floor_applied,
            finalLGD: result.lgd_percentage
        }
    };
}

/**
 * Calculate Risk Weight via Flask API (AIRB)
 * @param {number} pd - Probability of Default
 * @param {number} lgd - Loss Given Default
 * @param {number} ead - Exposure at Default
 * @param {number} maturity - Maturity in years
 * @param {string} borrowerType - Type of borrower
 * @returns {Promise<number>} Risk weight percentage
 */
async function calculateRiskWeightAIRBFromAPI(pd, lgd, ead, maturity, borrowerType = 'Corporate') {
    const result = await apiCall('/calculate-risk-weight-airb', {
        pd: pd / 100,  // Convert percentage to decimal
        lgd: lgd,
        ead: ead,
        maturity: maturity,
        borrower_type: borrowerType
    });

    if (!result || result.error) {
        console.error('Risk weight calculation error:', result?.error);
        return 0;
    }

    return result.risk_weight;
}

/**
 * Calculate RWA and Capital (AIRB) via Flask API
 * @param {number} exposure - Exposure amount
 * @param {number} riskWeight - Risk weight percentage
 * @returns {Promise<object>} RWA and capital requirement
 */
async function calculateRWAAIRBFromAPI(exposure, riskWeight) {
    const result = await apiCall('/calculate-rwa-airb', {
        exposure: exposure,
        risk_weight: riskWeight
    });

    if (!result || result.error) {
        console.error('RWA calculation error:', result?.error);
        return null;
    }

    return {
        rwa: result.rwa,
        capital: result.capital_required
    };
}

// ============================================================================
// STANDARDIZED APPROACH FUNCTIONS
// ============================================================================

/**
 * Get Risk Weight for Standardized Approach via Flask API
 * @param {string} category - Exposure category (Corporate, Sovereign, Bank, Financial)
 * @param {string} rating - External credit rating
 * @returns {Promise<number>} Risk weight percentage
 */
async function getRiskWeightSAFromAPI(category, rating) {
    const result = await apiCall('/get-risk-weight-sa', {
        category: category,
        rating: rating
    });

    if (!result || result.error) {
        console.error('SA risk weight error:', result?.error);
        return 100;  // Default to 100% on error
    }

    return result.risk_weight;
}

/**
 * Calculate adjusted exposure with collateral via Flask API
 * @param {number} exposure - Original exposure amount
 * @param {string} collateralType - Type of collateral
 * @param {number} collateralValue - Collateral value
 * @returns {Promise<number>} Adjusted exposure amount
 */
async function getAdjustedExposureFromAPI(exposure, collateralType, collateralValue) {
    const collateralTypeMap = {
        'None': null,
        'Real Estate': 'Government Securities',
        'Financial Assets': 'Corporate Bonds',
        'Equipment': 'Equities',
        'Inventory': 'Other',
        'Other': 'Other'
    };

    const apiCollateralType = collateralTypeMap[collateralType] || null;

    const result = await apiCall('/calculate-adjusted-exposure', {
        exposure: exposure,
        collateral_type: apiCollateralType,
        collateral_value: collateralValue || 0
    });

    if (!result || result.error) {
        return exposure;  // Return original if error
    }

    return result.adjusted_exposure;
}

/**
 * Calculate RWA and Capital (SA) via Flask API
 * @param {number} exposure - Exposure amount
 * @param {number} riskWeight - Risk weight percentage
 * @param {string} collateralType - Type of collateral
 * @param {number} collateralValue - Collateral value
 * @returns {Promise<object>} RWA and capital requirement
 */
async function calculateRWASAFromAPI(exposure, riskWeight, collateralType, collateralValue) {
    const collateralTypeMap = {
        'None': null,
        'Real Estate': 'Government Securities',
        'Financial Assets': 'Corporate Bonds',
        'Equipment': 'Equities',
        'Inventory': 'Other',
        'Other': 'Other'
    };

    const apiCollateralType = collateralTypeMap[collateralType] || null;

    const result = await apiCall('/calculate-rwa-sa', {
        exposure: exposure,
        risk_weight: riskWeight,
        collateral_type: apiCollateralType,
        collateral_value: collateralValue || 0
    });

    if (!result || result.error) {
        // Fallback calculation
        return {
            rwa: exposure * riskWeight / 100,
            capital: exposure * riskWeight / 100 * 0.08
        };
    }

    return {
        rwa: result.rwa,
        capital: result.capital_required
    };
}

// ============================================================================
// PORTFOLIO FUNCTIONS
// ============================================================================

/**
 * Calculate portfolio summary via Flask API
 * @param {array} loans - Array of loan objects
 * @returns {Promise<object>} Portfolio summary statistics
 */
async function getPortfolioSummaryFromAPI(loans) {
    // Transform loans to API format
    const apiLoans = loans.map(loan => ({
        exposure: loan.ead,
        rwa: loan.rwa,
        capital_required: loan.capitalRequired,
        calculation_method: loan.calcMode === 'airb' ? 'AIRB' : 'SA',
        pd: loan.pd || undefined,
        risk_weight: loan.riskWeight || undefined
    }));

    const result = await apiCall('/portfolio-summary', {
        loans: apiLoans
    });

    if (!result || result.error) {
        return null;
    }

    return result;
}

// ============================================================================
// REPLACEMENT FOR LOCAL calculateAllParameters
// ============================================================================

/**
 * NEW: Async version of calculateAllParameters that uses Flask APIs
 * This replaces the original local-calculation version
 */
async function calculateAllParametersViaAPI() {
    if (!validateInputs()) {
        alert('Please correct the errors above');
        return;
    }

    // Show loading indicator
    const btn = event.target;
    const originalText = btn.textContent;
    btn.textContent = '⏳ Calculating...';
    btn.disabled = true;

    try {
        const mode = document.querySelector('input[name="calcMode"]:checked').value;
        const borrowerId = document.getElementById('borrowerId').value.trim();
        const borrowerName = document.getElementById('borrowerName').value.trim();
        const sector = document.getElementById('sector').value;
        const exposureAmount = parseFloat(document.getElementById('exposureAmount').value);

        // Financial metrics
        const debtToEquity = parseFloat(document.getElementById('debtToEquity').value);
        const interestCoverage = parseFloat(document.getElementById('interestCoverage').value);
        const profitabilityMargin = parseFloat(document.getElementById('profitabilityMargin').value);
        const liquidityRatio = parseFloat(document.getElementById('liquidityRatio').value);

        // Calculate PD via API
        const pdResult = await calculatePDFromAPI(debtToEquity, interestCoverage, profitabilityMargin, liquidityRatio);

        if (!pdResult) {
            alert('Failed to calculate PD. Check Flask server is running.');
            return;
        }

        // Display results (using existing function)
        displayResults(mode, pdResult, borrowerId, borrowerName, sector, exposureAmount);

    } catch (error) {
        console.error('Calculation error:', error);
        alert('Error during calculation: ' + error.message);
    } finally {
        // Reset button
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

// ============================================================================
// INITIALIZATION
// ============================================================================

// API Integration module loaded - borrower-info.html calls API functions directly
console.log('API Integration module loaded');
