# Credit Risk Calculator - Web Application Files

All HTML and JavaScript files for the Credit Risk Calculator application are located in this folder.

## File Structure

```
public/
├── index.html                              [Main Application]
├── formula-reference.html                  [Formula Reference - AIRB & SA]
├── formula-references.html                 [Formula Hub - Navigation]
├── standardized-approach-reference.html    [Standardized Approach Reference]
├── standardized-approach.js                [SA Calculation Engine]
└── README.md                               [This file]
```

## File Descriptions

### 1. **index.html** (37 KB) - Main Web Application
The main calculator application. This is the entry point for users.

**Features:**
- Unified form for AIRB and Standardized Approach
- Portfolio management (add, delete, clear loans)
- Real-time calculations
- Export to CSV/JSON
- Responsive design for desktop, tablet, mobile

**How to use:**
- Double-click `index.html` to open in browser
- Or right-click and select "Open with" → your preferred browser

### 2. **formula-reference.html** (56 KB) - Complete Formula Reference
Comprehensive guide covering BOTH methodologies with formulas, tables, and examples.

**Sections:**
- **AIRB Approach:**
  - Overview & components
  - PD, LGD, EAD, Maturity Factor
  - Correlation & RWA Calculation
  - Capital Requirements
  - Worked examples
  - Regulatory ratios

- **Standardized Approach:**
  - Overview & components
  - Risk weight tables (4 categories)
  - Exposure categories
  - Collateral treatment & haircuts
  - Calculation formulas
  - 3 worked examples
  - Comparison with AIRB

### 3. **formula-references.html** (27 KB) - Formula Hub
Central navigation hub linking to all methodology references.

**Features:**
- Status dashboard (phases 1-5)
- Methodology cards with key features
- Comparison table
- Implementation timeline
- Quick links to detailed references

### 4. **standardized-approach-reference.html** (37 KB) - SA Reference
Dedicated Standardized Approach reference (supplementary to formula-reference.html).

**Contains:**
- Risk weight tables
- Exposure categories
- Collateral treatment details
- Calculation formulas
- 3 detailed worked examples
- vs AIRB comparison

### 5. **standardized-approach.js** (14 KB) - SA Calculation Engine
JavaScript module for Standardized Approach calculations.

**Provides:**
- Risk weight lookup tables
- Exposure calculations with collateral
- RWA computation
- Validation functions
- Comparison with AIRB results

## Deployment

To deploy this application:

1. **Local Testing:**
   - Double-click `index.html` to open locally (works offline)
   - All files are self-contained

2. **Web Server (Recommended):**
   - Copy entire `public` folder to your web server
   - Files need to be served from same directory
   - Works with any web server (Apache, Nginx, IIS, etc.)

3. **Cloud Deployment:**
   - Upload `public` folder to cloud hosting (AWS S3, Azure, Google Cloud, etc.)
   - Configure to serve `index.html` as default document

## File Dependencies

- **index.html** → requires `standardized-approach.js` (included via `<script>` tag)
- **index.html** → links to other `.html` files for navigation
- All `.html` files are standalone and can be opened independently
- No external dependencies (no npm, no libraries)

## Troubleshooting

### Links not working?
- Ensure all files are in the same folder
- Check browser console (F12) for errors
- Verify file paths in HTML match your folder structure

### Calculations not working?
- Make sure `standardized-approach.js` is in the same folder as `index.html`
- Check browser console for JavaScript errors
- Clear browser cache and reload

### Portfolio data not saving?
- Browser must allow localStorage
- Check browser privacy settings
- Some browsers block localStorage in private mode

## Browser Compatibility

- Chrome/Chromium ✅
- Firefox ✅
- Safari ✅
- Edge ✅
- Opera ✅
- IE 11+ (limited support)

## Notes

- All calculations are performed client-side (no server required)
- Portfolio data stored in browser's localStorage
- Responsive design adapts to screen size
- No internet connection required after initial load

## Support

For issues or questions:
- Check formula reference pages for calculation details
- Review CLAUDE.md for project documentation
- Verify all files are present in public folder

---

**Version:** 2.0  
**Last Updated:** June 3, 2026  
**Status:** Production Ready ✅
