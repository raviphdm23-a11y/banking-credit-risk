/**
 * Standardized Approach for Credit Risk - Basel III
 * Core calculation module
 * Version 1.0 - June 2026
 */

// Risk Weight Tables - Basel III Standardized Approach

const riskWeightTables = {
  // Corporate Exposures
  corporate: {
    'AAA': 20,
    'AA+': 20,
    'AA': 20,
    'AA-': 20,
    'A+': 50,
    'A': 50,
    'A-': 50,
    'BBB+': 75,
    'BBB': 75,
    'BBB-': 75,
    'BB+': 100,
    'BB': 100,
    'BB-': 100,
    'B+': 100,
    'B': 100,
    'B-': 100,
    'CCC': 150,
    'CC': 150,
    'C': 150,
    'D': 150,
    'Unrated': 100
  },

  // Sovereign Exposures
  sovereign: {
    'AAA': 0,
    'AA+': 20,
    'AA': 20,
    'AA-': 20,
    'A+': 50,
    'A': 50,
    'A-': 50,
    'BBB+': 50,
    'BBB': 50,
    'BBB-': 50,
    'BB+': 100,
    'BB': 100,
    'BB-': 100,
    'B+': 100,
    'B': 100,
    'B-': 100,
    'CCC': 150,
    'CC': 150,
    'C': 150,
    'D': 150
  },

  // Bank Exposures
  bank: {
    'AAA': 20,
    'AA+': 20,
    'AA': 20,
    'AA-': 20,
    'A+': 50,
    'A': 50,
    'A-': 50,
    'BBB+': 75,
    'BBB': 75,
    'BBB-': 75,
    'BB+': 100,
    'BB': 100,
    'BB-': 100,
    'B+': 100,
    'B': 100,
    'B-': 100,
    'CCC': 150,
    'CC': 150,
    'C': 150,
    'D': 150
  },

  // Financial Institution Exposures
  financial: {
    'AAA': 20,
    'AA+': 20,
    'AA': 20,
    'AA-': 20,
    'A+': 50,
    'A': 50,
    'A-': 50,
    'BBB+': 75,
    'BBB': 75,
    'BBB-': 75,
    'BB+': 100,
    'BB': 100,
    'BB-': 100,
    'B+': 100,
    'B': 100,
    'B-': 100,
    'CCC': 150,
    'CC': 150,
    'C': 150,
    'D': 150
  }
};

// LGD Values - Fixed under Standardized Approach
const lgdValues = {
  unsecured: 0.45,              // 45% for unsecured exposures
  secured_cash: 0.05,            // 5% for cash collateral
  secured_real_estate: 0.25,     // 25% for real estate collateral
  secured_securities: 0.35,      // 35% for securities collateral
  secured_other: 0.40            // 40% for other collateral
};

// Haircuts for Collateral - Standardized Approach
const haircuts = {
  cash: 0.00,                    // No haircut for cash
  government_securities: 0.05,   // 5% for government securities
  corporate_bonds: 0.10,         // 10% for investment grade corporate
  equities: 0.20,                // 20% for equities
  other: 0.25                    // 25% default haircut
};

// Standardized Approach Methodology Object
const StandardizedApproach = {
  // Metadata
  id: 'standardized-approach',
  name: 'Standardized Approach for Credit Risk',
  shortName: 'SA',
  version: '1.0',
  description: 'Basel III Standardized Approach using external ratings',
  category: 'credit-risk',
  status: 'active',

  /**
   * Get risk weight for a given rating and exposure category
   * @param {string} rating - Credit rating (e.g., 'AAA', 'BBB+')
   * @param {string} category - Exposure category ('corporate', 'sovereign', 'bank', 'financial')
   * @returns {number} Risk weight as percentage (e.g., 75 for 75%)
   */
  getRiskWeight: function(rating, category) {
    if (!rating || !category) {
      return null;
    }

    const categoryWeights = riskWeightTables[category.toLowerCase()];
    if (!categoryWeights) {
      console.error(`Unknown category: ${category}`);
      return null;
    }

    const weight = categoryWeights[rating.trim()];
    if (weight === undefined) {
      console.error(`Unknown rating: ${rating} for category: ${category}`);
      return null;
    }

    return weight;
  },

  /**
   * Calculate collateral adjustment
   * @param {number} collateralValue - Market value of collateral
   * @param {string} collateralType - Type of collateral
   * @returns {number} Adjusted collateral value after haircut
   */
  calculateCollateralAdjustment: function(collateralValue, collateralType) {
    if (!collateralValue || collateralValue <= 0) {
      return 0;
    }

    const haircut = haircuts[collateralType.toLowerCase()] || haircuts.other;
    const adjustedValue = collateralValue * (1 - haircut);

    return Math.max(adjustedValue, 0);
  },

  /**
   * Calculate adjusted exposure with collateral
   * @param {number} ead - Exposure at Default
   * @param {number} adjustedCollateral - Adjusted collateral value
   * @returns {number} Adjusted exposure
   */
  calculateAdjustedExposure: function(ead, adjustedCollateral) {
    const adjustedExposure = Math.max(ead - adjustedCollateral, 0);
    return adjustedExposure;
  },

  /**
   * Calculate RWA (Risk-Weighted Assets)
   * @param {number} exposure - Exposure amount
   * @param {number} riskWeight - Risk weight as percentage (e.g., 75)
   * @returns {number} RWA
   */
  calculateRWA: function(exposure, riskWeight) {
    if (!exposure || exposure <= 0 || !riskWeight || riskWeight < 0) {
      return 0;
    }

    // Convert percentage to decimal (e.g., 75% = 0.75)
    const weightDecimal = riskWeight / 100;
    const rwa = exposure * weightDecimal;

    return rwa;
  },

  /**
   * Calculate capital requirement (8% of RWA)
   * @param {number} rwa - Risk-weighted assets
   * @returns {number} Capital requirement (8% of RWA)
   */
  calculateCapitalRequirement: function(rwa) {
    if (!rwa || rwa <= 0) {
      return 0;
    }

    // Basel III minimum: 8%
    const capitalRequired = rwa * 0.08;
    return capitalRequired;
  },

  /**
   * Calculate complete exposure analysis
   * @param {Object} loanData - Loan data object
   * @returns {Object} Complete calculation results
   */
  calculateExposure: function(loanData) {
    try {
      // Extract and validate inputs
      const exposure = parseFloat(loanData.exposureAmount) || 0;
      const rating = loanData.externalRating;
      const category = loanData.exposureCategory;
      const hasCollateral = loanData.hasCollateral || false;

      let adjustedExposure = exposure;
      let collateralAdjustment = 0;
      let collateralLgd = 0;

      // Get risk weight
      const riskWeight = this.getRiskWeight(rating, category);
      if (riskWeight === null) {
        throw new Error(`Invalid rating (${rating}) or category (${category})`);
      }

      // Apply collateral if provided
      if (hasCollateral && loanData.collateralValue) {
        const collateralValue = parseFloat(loanData.collateralValue) || 0;
        const collateralType = loanData.collateralType || 'other';

        collateralAdjustment = this.calculateCollateralAdjustment(collateralValue, collateralType);
        adjustedExposure = this.calculateAdjustedExposure(exposure, collateralAdjustment);
      }

      // Calculate RWA
      const rwa = this.calculateRWA(adjustedExposure, riskWeight);

      // Calculate capital requirement
      const capitalRequired = this.calculateCapitalRequirement(rwa);

      // Calculate capital ratio
      const capitalRatio = exposure > 0 ? (capitalRequired / exposure) * 100 : 0;

      // Calculate risk density
      const riskDensity = exposure > 0 ? (rwa / exposure) * 100 : 0;

      return {
        // Input summary
        exposureAmount: exposure,
        externalRating: rating,
        exposureCategory: category,
        hasCollateral: hasCollateral,
        collateralValue: hasCollateral ? parseFloat(loanData.collateralValue) || 0 : 0,
        collateralType: hasCollateral ? loanData.collateralType : null,

        // Calculations
        riskWeight: riskWeight,
        collateralAdjustment: collateralAdjustment,
        adjustedExposure: adjustedExposure,
        rwa: rwa,
        capitalRequired: capitalRequired,
        capitalRatio: capitalRatio,
        riskDensity: riskDensity,

        // Regulatory minimums
        cet1Required: rwa * 0.045,           // 4.5% CET1
        tier1Required: rwa * 0.06,           // 6.0% Tier 1
        totalCapitalRequired: rwa * 0.08,    // 8.0% Total Capital

        // Status
        success: true,
        error: null
      };
    } catch (error) {
      console.error('Calculation error:', error);
      return {
        success: false,
        error: error.message,
        rwa: 0,
        capitalRequired: 0,
        capitalRatio: 0
      };
    }
  }
};

// Validation Functions
const StandardizedApproachValidation = {
  /**
   * Validate a complete loan entry
   * @param {Object} loanData - Loan data object
   * @returns {Object} Validation result with errors array
   */
  validateLoan: function(loanData) {
    const errors = [];

    // Loan ID validation
    if (!loanData.loanId || !loanData.loanId.trim()) {
      errors.push('Loan ID is required');
    }

    // Borrower name validation
    if (!loanData.borrowerName || !loanData.borrowerName.trim()) {
      errors.push('Borrower name is required');
    }

    // Exposure amount validation
    if (!loanData.exposureAmount) {
      errors.push('Exposure amount is required');
    } else {
      const exposure = parseFloat(loanData.exposureAmount);
      if (isNaN(exposure) || exposure <= 0) {
        errors.push('Exposure amount must be greater than 0');
      }
      if (exposure < 1000) {
        errors.push('Exposure amount should typically be at least $1,000');
      }
    }

    // External rating validation
    if (!loanData.externalRating) {
      errors.push('External rating is required');
    } else {
      const validRatings = Object.keys(riskWeightTables.corporate);
      if (!validRatings.includes(loanData.externalRating.trim())) {
        errors.push(`Invalid rating. Valid ratings are: ${validRatings.join(', ')}`);
      }
    }

    // Exposure category validation
    if (!loanData.exposureCategory) {
      errors.push('Exposure category is required');
    } else {
      const validCategories = Object.keys(riskWeightTables);
      if (!validCategories.includes(loanData.exposureCategory.toLowerCase())) {
        errors.push(`Invalid category. Valid categories are: ${validCategories.join(', ')}`);
      }
    }

    // Collateral validation (if applicable)
    if (loanData.hasCollateral) {
      if (!loanData.collateralValue) {
        errors.push('Collateral value is required when collateral is indicated');
      } else {
        const collateralValue = parseFloat(loanData.collateralValue);
        if (isNaN(collateralValue) || collateralValue < 0) {
          errors.push('Collateral value must be a non-negative number');
        }
      }

      if (!loanData.collateralType) {
        errors.push('Collateral type is required when collateral is indicated');
      }
    }

    return {
      isValid: errors.length === 0,
      errors: errors
    };
  },

  /**
   * Validate a single field
   * @param {string} fieldName - Name of the field
   * @param {any} value - Value to validate
   * @returns {string|null} Error message or null if valid
   */
  validateField: function(fieldName, value) {
    switch (fieldName) {
      case 'exposureAmount':
        if (!value || parseFloat(value) <= 0) {
          return 'Exposure amount must be greater than 0';
        }
        return null;

      case 'externalRating':
        if (!value) {
          return 'Rating is required';
        }
        const validRatings = Object.keys(riskWeightTables.corporate);
        if (!validRatings.includes(value.trim())) {
          return 'Invalid rating';
        }
        return null;

      case 'exposureCategory':
        if (!value) {
          return 'Category is required';
        }
        const validCategories = Object.keys(riskWeightTables);
        if (!validCategories.includes(value.toLowerCase())) {
          return 'Invalid category';
        }
        return null;

      default:
        return null;
    }
  }
};

// Comparison with AIRB
const StandardizedApproachComparison = {
  /**
   * Compare Standardized Approach with AIRB results
   * @param {Object} saResult - Standardized Approach calculation result
   * @param {Object} airbResult - AIRB calculation result
   * @returns {Object} Comparison analysis
   */
  compareWithAirb: function(saResult, airbResult) {
    if (!saResult || !airbResult) {
      return null;
    }

    const rwaDifference = saResult.rwa - airbResult.rwa;
    const rwaDifferencePercent = airbResult.rwa > 0
      ? (rwaDifference / airbResult.rwa) * 100
      : 0;

    const capitalDifference = saResult.capitalRequired - airbResult.capitalRequired;

    return {
      saRwa: saResult.rwa,
      airbRwa: airbResult.rwa,
      rwaDifference: rwaDifference,
      rwaDifferencePercent: rwaDifferencePercent,
      saCapital: saResult.capitalRequired,
      airbCapital: airbResult.capitalRequired,
      capitalDifference: capitalDifference,
      capDifferencePercent: airbResult.capitalRequired > 0
        ? (capitalDifference / airbResult.capitalRequired) * 100
        : 0,
      whichIsHigher: rwaDifference > 0 ? 'SA' : 'AIRB',
      recommendation: this.getRecommendation(rwaDifferencePercent)
    };
  },

  /**
   * Get recommendation based on comparison
   * @param {number} difference - Percentage difference
   * @returns {string} Recommendation
   */
  getRecommendation: function(difference) {
    if (Math.abs(difference) < 5) {
      return 'Results are very similar - either approach acceptable';
    } else if (difference > 0) {
      return 'SA produces higher capital requirement - AIRB preferred if available';
    } else {
      return 'AIRB produces higher capital requirement - review assumptions';
    }
  }
};

// Export for use in HTML
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    StandardizedApproach,
    StandardizedApproachValidation,
    StandardizedApproachComparison,
    riskWeightTables,
    lgdValues,
    haircuts
  };
}
