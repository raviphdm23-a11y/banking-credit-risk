/**
 * report-charts.js — Pure SVG chart rendering for the Credit Assessment Report.
 * No external libraries. All functions take a container element + data object.
 */

const ReportCharts = (() => {

  const COLORS = {
    green:  '#16a34a', greenLt: '#dcfce7',
    amber:  '#d97706', amberLt: '#fef3c7',
    red:    '#dc2626', redLt:   '#fee2e2',
    blue:   '#2563eb', blueLt:  '#eff6ff',
    navy:   '#1a2e4a',
    grey:   '#94a3b8', greyLt: '#f1f5f9',
    border: '#e2e8f0',
  };

  const GRADE_COLOR = {
    AAA: COLORS.green, AA: COLORS.green, A: COLORS.green, BBB: COLORS.green,
    BB: COLORS.amber,  B: COLORS.amber,
    CCC: COLORS.red, CC: COLORS.red, C: COLORS.red, D: COLORS.red,
  };

  // ── Helper: create SVG element ─────────────────────────────────────────
  function svg(tag, attrs = {}) {
    const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
    return el;
  }

  function svgText(el, x, y, text, attrs = {}) {
    const t = svg('text', { x, y, ...attrs });
    t.textContent = text;
    el.appendChild(t);
    return t;
  }

  // ── Risk Gauge (semicircle) ────────────────────────────────────────────
  /**
   * drawGauge(container, { pd, pdLow, pdHigh, grade })
   * Draws a 5-band semicircular gauge with a needle at pd and shaded
   * uncertainty arc between pdLow and pdHigh.
   */
  function drawGauge(container, { pd, pdLow, pdHigh, grade }) {
    container.innerHTML = '';

    const W = 280, H = 170, CX = 140, CY = 145, R = 115, r = 68;

    const root = svg('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img',
      'aria-label': `Risk gauge showing PD ${(pd*100).toFixed(1)}%` });

    // Band definitions: [startPD, endPD, color, label]
    const bands = [
      [0,    0.02, '#16a34a', 'Low'],
      [0.02, 0.07, '#65a30d', 'Moderate-Low'],
      [0.07, 0.15, '#eab308', 'Moderate'],
      [0.15, 0.35, '#f97316', 'Elevated'],
      [0.35, 1.00, '#dc2626', 'High'],
    ];

    // Semicircle: left = PI (180°), right = 0° (0°)
    // PD = 0 → leftmost (180°), PD = 1 → rightmost (0°)
    const pdToAngle = (p) => Math.PI - p * Math.PI;  // radians, 0=right axis

    function arcPath(pLow, pHigh, rOuter, rInner) {
      const a1 = pdToAngle(pLow), a2 = pdToAngle(pHigh);
      const ox1 = CX + rOuter * Math.cos(a1), oy1 = CY - rOuter * Math.sin(a1);
      const ox2 = CX + rOuter * Math.cos(a2), oy2 = CY - rOuter * Math.sin(a2);
      const ix1 = CX + rInner * Math.cos(a1), iy1 = CY - rInner * Math.sin(a1);
      const ix2 = CX + rInner * Math.cos(a2), iy2 = CY - rInner * Math.sin(a2);
      return `M ${ox1} ${oy1} A ${rOuter} ${rOuter} 0 0 0 ${ox2} ${oy2} L ${ix2} ${iy2} A ${rInner} ${rInner} 0 0 1 ${ix1} ${iy1} Z`;
    }

    // Draw bands
    for (const [lo, hi, color] of bands) {
      const p = svg('path', { d: arcPath(lo, hi, R, r), fill: color, opacity: '0.85' });
      root.appendChild(p);
    }

    // Uncertainty arc (between pdLow and pdHigh)
    if (pdHigh > pdLow) {
      const uncPath = arcPath(pdLow, pdHigh, R + 7, R);
      const uArc = svg('path', { d: uncPath, fill: COLORS.navy, opacity: '0.18' });
      root.appendChild(uArc);
    }

    // Needle
    const needleAngle = pdToAngle(pd);
    const nLen = R - 4;
    const nx = CX + nLen * Math.cos(needleAngle);
    const ny = CY - nLen * Math.sin(needleAngle);
    root.appendChild(svg('line', {
      x1: CX, y1: CY, x2: nx, y2: ny,
      stroke: COLORS.navy, 'stroke-width': '3', 'stroke-linecap': 'round',
    }));
    root.appendChild(svg('circle', {
      cx: CX, cy: CY, r: '6',
      fill: COLORS.navy,
    }));

    // Scale ticks
    for (const p of [0, 0.25, 0.50, 0.75, 1.0]) {
      const a = pdToAngle(p);
      const tx = CX + (R + 12) * Math.cos(a);
      const ty = CY - (R + 12) * Math.sin(a);
      svgText(root, tx, ty, `${(p * 100).toFixed(0)}%`, {
        'text-anchor': 'middle', 'dominant-baseline': 'middle',
        'font-size': '10', fill: COLORS.navy, 'font-family': 'system-ui',
      });
    }

    // Central PD readout
    svgText(root, CX, CY - 20, `${(pd * 100).toFixed(1)}%`, {
      'text-anchor': 'middle', 'font-size': '22', 'font-weight': '700',
      fill: GRADE_COLOR[grade] || COLORS.navy, 'font-family': 'system-ui',
    });
    svgText(root, CX, CY - 4, grade, {
      'text-anchor': 'middle', 'font-size': '13', 'font-weight': '600',
      fill: GRADE_COLOR[grade] || COLORS.navy, 'font-family': 'system-ui',
    });
    svgText(root, CX, CY + 12, `Band: ${(pdLow*100).toFixed(1)}-${(pdHigh*100).toFixed(1)}%`, {
      'text-anchor': 'middle', 'font-size': '10', fill: COLORS.grey,
      'font-family': 'system-ui',
    });

    container.appendChild(root);
  }

  // ── Attribution Tornado ────────────────────────────────────────────────
  /**
   * drawTornado(container, attribution)
   * attribution: [{display_name, contribution, direction, reason_code}, ...]
   */
  function drawTornado(container, attribution) {
    container.innerHTML = '';
    if (!attribution || attribution.length === 0) return;

    const items = attribution.filter(a => Math.abs(a.contribution) > 0.001);
    if (items.length === 0) return;

    const W = 380, ROW = 32, PAD_LEFT = 145, PAD_RIGHT = 20, BAR_H = 16;
    const H = items.length * ROW + 40;
    const maxContrib = Math.max(...items.map(a => Math.abs(a.contribution)));
    const barWidth = W - PAD_LEFT - PAD_RIGHT;

    const root = svg('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img',
      'aria-label': 'Feature attribution tornado chart' });

    // Header
    svgText(root, PAD_LEFT + barWidth / 2, 14, 'PD Contribution (pp)', {
      'text-anchor': 'middle', 'font-size': '10', fill: COLORS.grey,
      'font-family': 'system-ui', 'font-weight': '600',
    });

    items.forEach((attr, i) => {
      const y = 28 + i * ROW;
      const contrib = attr.contribution;
      const absContrib = Math.abs(contrib);
      const isUp = contrib > 0;
      const barLen = (absContrib / (maxContrib || 1)) * (barWidth * 0.85);
      const color = isUp ? COLORS.red : COLORS.green;
      const barX = isUp ? PAD_LEFT : PAD_LEFT - barLen;

      // Label
      const label = (attr.display_name || attr.feature).replace('(%)', '').trim();
      const shortLabel = label.length > 20 ? label.substring(0, 19) + '.' : label;
      svgText(root, PAD_LEFT - 8, y + BAR_H / 2 + 1, shortLabel, {
        'text-anchor': 'end', 'dominant-baseline': 'middle',
        'font-size': '11.5', fill: COLORS.navy, 'font-family': 'system-ui',
      });

      // Background stripe
      root.appendChild(svg('rect', {
        x: 0, y: y, width: W, height: ROW - 2, fill: i % 2 === 0 ? '#fafafa' : '#fff', rx: 3,
      }));

      // Bar
      root.appendChild(svg('rect', {
        x: barX, y: y + (ROW - BAR_H) / 2 - 1,
        width: Math.max(barLen, 2), height: BAR_H,
        fill: color, rx: '3', opacity: '0.85',
      }));

      // Zero line
      root.appendChild(svg('line', {
        x1: PAD_LEFT, y1: y, x2: PAD_LEFT, y2: y + ROW - 2,
        stroke: COLORS.border, 'stroke-width': '1',
      }));

      // Value label
      const valX = isUp ? PAD_LEFT + barLen + 6 : PAD_LEFT - barLen - 6;
      const anchor = isUp ? 'start' : 'end';
      svgText(root, valX, y + BAR_H / 2 + (ROW - BAR_H) / 2, `${isUp ? '+' : '-'}${(absContrib * 100).toFixed(2)}pp`, {
        'text-anchor': anchor, 'dominant-baseline': 'middle',
        'font-size': '10', fill: color, 'font-weight': '600', 'font-family': 'system-ui',
      });
    });

    container.appendChild(root);
  }

  // ── Feature Health Bar Chart ───────────────────────────────────────────
  /**
   * drawFeatureHealth(container, peerHealth)
   * peerHealth: { feature: { value, peer_median, status, display_name, unit }, ... }
   */
  function drawFeatureHealth(container, peerHealth) {
    container.innerHTML = '';
    const features = Object.keys(peerHealth);
    if (features.length === 0) return;

    const W = 420, ROW = 48, PAD_LEFT = 160, PAD_RIGHT = 20;
    const H = features.length * ROW + 50;
    const root = svg('svg', { viewBox: `0 0 ${W} ${H}`, role: 'img',
      'aria-label': 'Feature health comparison chart' });

    // Header
    svgText(root, PAD_LEFT + 10, 16, 'Yours', {
      'text-anchor': 'middle', 'font-size': '10', fill: COLORS.grey,
      'font-weight': '600', 'font-family': 'system-ui',
    });
    svgText(root, PAD_LEFT + 80, 16, 'Peer Median', {
      'text-anchor': 'middle', 'font-size': '10', fill: COLORS.grey,
      'font-weight': '600', 'font-family': 'system-ui',
    });
    svgText(root, PAD_LEFT + 160, 16, 'Peer Range', {
      'text-anchor': 'middle', 'font-size': '10', fill: COLORS.grey,
      'font-weight': '600', 'font-family': 'system-ui',
    });

    features.forEach((feat, i) => {
      const h   = peerHealth[feat];
      const y   = 28 + i * ROW;
      const status = h.status;
      const color  = status === 'STRONG' ? COLORS.green : status === 'OK' ? COLORS.amber : COLORS.red;

      // Row stripe
      root.appendChild(svg('rect', {
        x: 0, y, width: W, height: ROW - 2, fill: i % 2 === 0 ? '#fafafa' : '#fff',
      }));

      // Feature name
      const shortName = (h.display_name || feat).replace('(%)', '').trim();
      svgText(root, PAD_LEFT - 10, y + ROW / 2, shortName, {
        'text-anchor': 'end', 'dominant-baseline': 'middle',
        'font-size': '11.5', fill: COLORS.navy, 'font-family': 'system-ui',
      });

      // Format value
      const fmt = (v) => h.unit === 'percent' ? `${(+v).toFixed(1)}%` : `${(+v).toFixed(2)}x`;

      // Applicant value dot + label
      root.appendChild(svg('circle', {
        cx: PAD_LEFT + 10, cy: y + ROW / 2, r: 7, fill: color, opacity: '0.9',
      }));
      svgText(root, PAD_LEFT + 10, y + ROW / 2 + 1, '', {});
      svgText(root, PAD_LEFT + 22, y + ROW / 2 + 1, fmt(h.value), {
        'dominant-baseline': 'middle', 'font-size': '11', fill: COLORS.navy,
        'font-weight': '700', 'font-family': 'system-ui',
      });

      // Peer median dot + label
      root.appendChild(svg('circle', {
        cx: PAD_LEFT + 80, cy: y + ROW / 2, r: 6, fill: COLORS.grey, opacity: '0.6',
      }));
      svgText(root, PAD_LEFT + 92, y + ROW / 2 + 1, fmt(h.peer_median), {
        'dominant-baseline': 'middle', 'font-size': '11', fill: COLORS.grey,
        'font-family': 'system-ui',
      });

      // P25-P75 range bar
      const rangeX = PAD_LEFT + 140;
      const rangeW = 90;
      root.appendChild(svg('rect', {
        x: rangeX, y: y + ROW / 2 - 3, width: rangeW, height: 6,
        fill: COLORS.greyLt, rx: 3,
      }));

      // Marker for peer_median within range
      const lo = h.peer_p25, hi = h.peer_p75;
      const range = hi - lo || 1;
      const medPos = rangeX + ((h.peer_median - lo) / range) * rangeW;
      root.appendChild(svg('rect', {
        x: Math.max(rangeX, medPos - 2), y: y + ROW / 2 - 6, width: 4, height: 12,
        fill: COLORS.grey, rx: 1,
      }));

      // Applicant marker within range
      const appPos = rangeX + Math.min(1, Math.max(0, (h.value - lo) / range)) * rangeW;
      root.appendChild(svg('circle', {
        cx: appPos, cy: y + ROW / 2, r: 5, fill: color, opacity: '0.9',
      }));

      // Status badge text
      const badgeText = status;
      const bx = W - PAD_RIGHT - 40;
      root.appendChild(svg('rect', {
        x: bx, y: y + (ROW - 20) / 2, width: 42, height: 20, rx: 10,
        fill: status === 'STRONG' ? COLORS.greenLt : status === 'OK' ? COLORS.amberLt : COLORS.redLt,
      }));
      svgText(root, bx + 21, y + ROW / 2 + 1, badgeText, {
        'text-anchor': 'middle', 'dominant-baseline': 'middle',
        'font-size': '9.5', fill: color, 'font-weight': '700', 'font-family': 'system-ui',
      });
    });

    container.appendChild(root);
  }

  // ── Public API ─────────────────────────────────────────────────────────
  return { drawGauge, drawTornado, drawFeatureHealth };

})();
