/**
 * ============================================================================
 *  Pokémon Portfolio — Google Apps Script formatter
 * ============================================================================
 *  Paste this whole file into  Extensions ▸ Apps Script  (the script bound to
 *  the Pokémon sheet), press Save, then RELOAD the spreadsheet tab.
 *
 *  A "📊 Portfolio" menu appears. Run  🎨 Format everything  once and the
 *  spreadsheet becomes a styled, colour-coded dashboard:
 *
 *    • dark header rows, frozen, zebra banding, readable number formats
 *    • CONDITIONAL FORMATTING that switches cells RED / GREEN automatically:
 *          green = up / above reference / in the green
 *          red   = down / below reference / in the red
 *          amber = flat, missing price, or needs attention
 *    • a colour-scale heat map on the percentage / "mover" columns
 *
 *  Re-run  🎨 Format everything  any time data is refreshed — it is
 *  idempotent (it clears its own conditional-format rules first, so rules
 *  never stack).  Nothing here touches your data: it only styles ranges.
 *
 *  Everything is driven by the HEADER NAMES in row 1, so the script keeps
 *  working even if columns are added or reordered.
 * ============================================================================
 */

// ---------------------------------------------------------------------------
// Theme + number formats (edit freely)
// ---------------------------------------------------------------------------
const THEME = {
  header:  { bg: '#111827', fg: '#ffffff' },   // slate-900 header
  section: { bg: '#eef2ff', fg: '#3730a3' },   // indigo section band
  good:    { bg: '#d1fae5', fg: '#065f46' },   // green  (up / in the green)
  bad:     { bg: '#fee2e2', fg: '#991b1b' },   // red    (down / in the red)
  warn:    { bg: '#fef3c7', fg: '#92400e' },   // amber  (flat / missing)
  neutral: { bg: '#f3f4f6', fg: '#6b7280' },   // gray   (no data)
  accent:  '#7c3aed',
};

// Classic Sheets 3-colour scale endpoints (red → yellow → green)
const GRAD = { lo: '#f8696b', mid: '#ffeb84', hi: '#63be7b' };

const NF = {
  int: '#,##0',
  nok: '#,##0.00" kr"',
  usd: '"$"#,##0.00',
  eur: '"€"#,##0.00',
  dec: '#,##0.00',
  pct: '0.00"%"',   // note: our percent values are already ×100, so the "%" is literal
};

const DATA_TABS = [
  'Collection', 'PriceSnapshots', 'Sets', 'Movers',
  'Coverage', 'CoverageMissing', 'Config', 'RateLog', 'FINN',
];

// ---------------------------------------------------------------------------
// Menu
// ---------------------------------------------------------------------------
function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('📊 Portfolio')
    .addItem('🎨 Format everything', 'formatEverything')
    .addItem('🚦 Re-apply colours only', 'applyColoursOnly')
    .addItem('📐 Auto-fit columns', 'autoFitAll')
    .addItem('🧮 Repair #ERROR cells', 'repairErrors')
    .addSeparator()
    .addItem('⏰ Install daily auto-format trigger', 'installDailyTrigger')
    .addToUi();
}

// ---------------------------------------------------------------------------
// Entry points
// ---------------------------------------------------------------------------
/** Style every tab: headers, banding, number formats + conditional colours. */
function formatEverything() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const done = [];
  DATA_TABS.forEach(function (name) {
    const sh = ss.getSheetByName(name);
    if (sh) { styleDataSheet(sh); done.push(name); }
  });
  const dash = ss.getSheetByName('Dashboard');
  if (dash) { styleDashboard(dash); done.push('Dashboard'); }

  Logger.log('formatEverything → ' + done.join(', '));
  ss.toast('Formatted: ' + done.join(', '), '📊 Portfolio', 6);
  return done;
}

/** Only (re)build the conditional-format rules — cheap to run often. */
function applyColoursOnly() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  DATA_TABS.forEach(function (name) {
    const sh = ss.getSheetByName(name);
    if (!sh) return;
    const maxRow = Math.max(sh.getLastRow(), 500);
    sh.clearConditionalFormatRules();
    const rules = buildRules(sh, maxRow);
    if (rules.length) sh.setConditionalFormatRules(rules);
  });
  const dash = ss.getSheetByName('Dashboard');
  if (dash) styleDashboard(dash);
  ss.toast('Colours re-applied.', '📊 Portfolio', 4);
}

function autoFitAll() {
  SpreadsheetApp.getActiveSpreadsheet().getSheets().forEach(function (sh) {
    const lastCol = sh.getLastColumn();
    if (lastCol > 0) sh.autoResizeColumns(1, lastCol);
  });
}

function installDailyTrigger() {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === 'formatEverything') ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger('formatEverything').timeBased().everyDays(1).atHour(6).create();
  SpreadsheetApp.getActiveSpreadsheet().toast('Daily 06:00 trigger installed.', '📊 Portfolio', 5);
}

/** Clear any cell that currently shows the "#ERROR!" formula error. */
function repairErrors() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let cleared = 0;
  ss.getSheets().forEach(function (sh) {
    const lastRow = sh.getLastRow(), lastCol = sh.getLastColumn();
    if (lastRow < 1 || lastCol < 1) return;
    const displayed = sh.getRange(1, 1, lastRow, lastCol).getDisplayValues();
    for (let r = 0; r < displayed.length; r++) {
      for (let c = 0; c < displayed[r].length; c++) {
        const v = displayed[r][c];
        if (v === '#ERROR!' || v === '#NAME?' || v === '#REF!') {
          sh.getRange(r + 1, c + 1).clearContent();
          cleared++;
        }
      }
    }
  });
  ss.toast('Cleared ' + cleared + ' broken cell(s).', '📊 Portfolio', 6);
  Logger.log('repairErrors cleared ' + cleared);
}

// ---------------------------------------------------------------------------
// Data-tab styling
// ---------------------------------------------------------------------------
function styleDataSheet(sh) {
  const lastRow = Math.max(sh.getLastRow(), 1);
  const lastCol = Math.max(sh.getLastColumn(), 1);
  const maxRow = Math.max(lastRow, 500);   // headroom so rules cover future rows

  // Header row
  if (lastCol >= 1) {
    sh.getRange(1, 1, 1, lastCol)
      .setBackground(THEME.header.bg)
      .setFontColor(THEME.header.fg)
      .setFontWeight('bold')
      .setVerticalAlignment('middle');
  }
  sh.setFrozenRows(1);

  // Zebra banding on the body
  if (lastRow >= 2) {
    sh.getRange(2, 1, lastRow - 1, lastCol)
      .applyRowBanding(SpreadsheetApp.BandingTheme.LIGHT_GREY, false, false);
  }

  applyNumberFormats(sh);
  applyColumnWidths(sh);

  // Conditional formatting (clear first → idempotent)
  sh.clearConditionalFormatRules();
  const rules = buildRules(sh, maxRow);
  if (rules.length) sh.setConditionalFormatRules(rules);
}

function headerIndex(sheet) {
  const lastCol = sheet.getLastColumn();
  if (lastCol < 1) return {};
  const names = sheet.getRange(1, 1, 1, lastCol).getDisplayValues()[0];
  const map = {};
  names.forEach(function (n, i) { map[String(n).trim()] = i + 1; });
  return map;
}

function applyNumberFormats(sh) {
  const name = sh.getName();
  const m = headerIndex(sh);
  const n = Math.max(sh.getLastRow() - 1, 1);
  const set = function (colName, fmt) {
    if (m[colName]) sh.getRange(2, m[colName], n, 1).setNumberFormat(fmt);
  };

  if (name === 'Collection') {
    set('Qty', NF.int);
    ['Avg Cost (NOK)', 'Collectr Market (NOK)', 'Collectr Value (NOK)',
     'API Value (NOK)', 'Cost Basis (NOK)', 'P&L vs Cost (NOK)'].forEach(function (c) {
      set(c, NF.nok);
    });
    set('TCG Market (USD)', NF.usd);
    set('CMK Trend (EUR)', NF.eur);
    set('vs Collectr %', NF.pct);
    set('Move % (vs first seen)', NF.pct);
  } else if (name === 'Movers') {
    ['First', 'Latest', 'Delta'].forEach(function (c) { set(c, NF.dec); });
    set('Delta %', NF.pct);
  } else if (name === 'FINN') {
    ['Price (NOK)', 'Market price', 'Delta'].forEach(function (c) { set(c, NF.nok); });
  } else if (name === 'Sets') {
    ['card_count', 'number_count'].forEach(function (c) { set(c, NF.int); });
  }
}

function applyColumnWidths(sh) {
  const name = sh.getName();
  const widths = {
    Collection: { 1: 56, 2: 150, 3: 280, 4: 90, 9: 50 },
    PriceSnapshots: { 1: 130, 6: 220 },
    Movers: { 1: 150, 2: 240 },
    Sets: { 1: 220 },
    FINN: { 1: 110, 2: 260 },
    RateLog: { 1: 130, 7: 150 },
  }[name];
  if (widths) {
    Object.keys(widths).forEach(function (k) { sh.setColumnWidth(Number(k), widths[k]); });
  }
}

// ---------------------------------------------------------------------------
// Conditional-format rule builders
// ---------------------------------------------------------------------------
function buildRules(sh, maxRow) {
  switch (sh.getName()) {
    case 'Collection':      return collectionRules(sh, maxRow);
    case 'Movers':          return moversRules(sh, maxRow);
    case 'FINN':            return finnRules(sh, maxRow);
    case 'RateLog':         return rateLogRules(sh, maxRow);
    case 'Coverage':        return coverageRules(sh, maxRow);
    default:                return [];
  }
}

function collectionRules(sh, maxRow) {
  const m = headerIndex(sh);
  const rules = [];
  const col = function (name) {
    return m[name] ? sh.getRange(2, m[name], maxRow - 1, 1) : null;
  };

  const pnl = col('P&L vs Cost (NOK)');
  if (pnl) {
    rules.push(numRule(pnl, { gt: 0, bg: THEME.good.bg, fg: THEME.good.fg, bold: true }));
    rules.push(numRule(pnl, { lt: 0, bg: THEME.bad.bg,  fg: THEME.bad.fg,  bold: true }));
  }
  const vs = col('vs Collectr %');
  if (vs) rules.push(scaleRule(vs, -25, 0, 25));
  const mv = col('Move % (vs first seen)');
  if (mv) rules.push(scaleRule(mv, -20, 0, 20));

  const vd = col('Verdict');
  if (vd) {
    rules.push(textRule(vd, '🟢', THEME.good.bg, THEME.good.fg, true));
    rules.push(textRule(vd, '🔴', THEME.bad.bg,  THEME.bad.fg,  true));
    rules.push(textRule(vd, '🟡', THEME.warn.bg, THEME.warn.fg, false));
    rules.push(textRule(vd, '⚪', THEME.neutral.bg, THEME.neutral.fg, false));
  }

  // Whole-row amber tint when a card still has no API price.
  const cName = m['Product Name'], cApi = m['API Value (NOK)'];
  if (cName && cApi) {
    const wide = sh.getRange(2, 1, maxRow - 1, Math.max(sh.getLastColumn(), 1));
    const f = '=AND($' + a1(cName) + '2<>"", $' + a1(cApi) + '2="")';
    rules.push(formulaRule(wide, f, THEME.warn.bg));
  }
  return rules;
}

function moversRules(sh, maxRow) {
  const m = headerIndex(sh);
  const rules = [];
  if (m['Delta']) {
    const r = sh.getRange(2, m['Delta'], maxRow - 1, 1);
    rules.push(numRule(r, { gt: 0, bg: THEME.good.bg, fg: THEME.good.fg, bold: true }));
    rules.push(numRule(r, { lt: 0, bg: THEME.bad.bg,  fg: THEME.bad.fg,  bold: true }));
  }
  if (m['Delta %']) rules.push(scaleRule(sh.getRange(2, m['Delta %'], maxRow - 1, 1), -20, 0, 20));
  return rules;
}

function finnRules(sh, maxRow) {
  const m = headerIndex(sh);
  const rules = [];
  // For a *listing*, a price BELOW market is the good (green) outcome.
  if (m['Delta']) {
    const r = sh.getRange(2, m['Delta'], maxRow - 1, 1);
    rules.push(numRule(r, { lt: 0, bg: THEME.good.bg, fg: THEME.good.fg, bold: true }));
    rules.push(numRule(r, { gt: 0, bg: THEME.bad.bg,  fg: THEME.bad.fg,  bold: true }));
  }
  if (m['Status']) {
    const s = sh.getRange(2, m['Status'], maxRow - 1, 1);
    rules.push(textRule(s, 'Solgt', THEME.neutral.bg, THEME.neutral.fg, false));
    rules.push(textRule(s, 'Inaktiv', THEME.warn.bg, THEME.warn.fg, false));
    rules.push(textRule(s, 'Aktiv', THEME.good.bg, THEME.good.fg, false));
  }
  return rules;
}

function rateLogRules(sh, maxRow) {
  const m = headerIndex(sh);
  const rules = [];
  if (m['status']) {
    const r = sh.getRange(2, m['status'], maxRow - 1, 1);
    rules.push(numRule(r, { gte: 400, bg: THEME.bad.bg, fg: THEME.bad.fg, bold: true }));
    rules.push(numRule(r, { lt: 400,  bg: THEME.good.bg, fg: THEME.good.fg }));
  }
  return rules;
}

function coverageRules(sh, maxRow) {
  const m = headerIndex(sh);
  const rules = [];
  if (m['Value']) {
    const r = sh.getRange(2, m['Value'], maxRow - 1, 1);
    rules.push(scaleRule(r, 0, 50, 100));
  }
  return rules;
}

// ---------------------------------------------------------------------------
// Dashboard styling
// ---------------------------------------------------------------------------
function styleDashboard(sh) {
  const lastRow = Math.max(sh.getLastRow(), 1);
  const lastCol = Math.max(sh.getLastColumn(), 6);

  sh.getRange(1, 1).setFontSize(18).setFontWeight('bold').setFontColor(THEME.header.bg);
  sh.getRange(2, 1, 1, 2).setFontColor('#6b7280');

  const INT_LABELS = ['Distinct rows', 'Total card quantity', 'Rows with an API price',
    'Cards up', 'Cards down', 'Sets in catalog', 'Snapshot records captured'];
  const PCT_LABELS = ['Price coverage %', 'API vs Collectr %'];

  for (let r = 1; r <= lastRow; r++) {
    const label = String(sh.getRange(r, 1).getDisplayValue()).trim();
    if (label.indexOf('▸') === 0) {                       // section band
      sh.getRange(r, 1, 1, lastCol)
        .setBackground(THEME.section.bg)
        .setFontColor(THEME.section.fg)
        .setFontWeight('bold');
    } else if (INT_LABELS.indexOf(label) >= 0) {
      sh.getRange(r, 1).setFontWeight('bold');
      sh.getRange(r, 2).setNumberFormat(NF.int);
    } else if (PCT_LABELS.indexOf(label) >= 0) {
      sh.getRange(r, 1).setFontWeight('bold');
      sh.getRange(r, 2).setNumberFormat(NF.pct);
    } else if (label === 'Collectr market total' || label.indexOf('API-priced total') === 0) {
      sh.getRange(r, 1).setFontWeight('bold');
      sh.getRange(r, 2).setNumberFormat(NF.nok);
    } else if (label === 'Biggest gainer' || label === 'Biggest loser') {
      sh.getRange(r, 1).setFontWeight('bold');
      sh.getRange(r, 3).setNumberFormat(NF.pct);
    } else if (label === 'Set') {                          // top-15 table header
      sh.getRange(r, 1, 1, 6)
        .setBackground(THEME.header.bg)
        .setFontColor(THEME.header.fg)
        .setFontWeight('bold');
    }
  }

  // Conditional colours on the key KPI cells + the legend emojis
  sh.clearConditionalFormatRules();
  const rules = [];

  const apiRow = findRow(sh, 'API vs Collectr %');
  if (apiRow) {
    const c = sh.getRange(apiRow, 2);
    rules.push(numRule(c, { gt: 0, bg: THEME.good.bg, fg: THEME.good.fg, bold: true }));
    rules.push(numRule(c, { lt: 0, bg: THEME.bad.bg,  fg: THEME.bad.fg,  bold: true }));
  }
  const gainRow = findRow(sh, 'Biggest gainer');
  if (gainRow) rules.push(numRule(sh.getRange(gainRow, 3), { gt: 0, bg: THEME.good.bg, fg: THEME.good.fg }));
  const loseRow = findRow(sh, 'Biggest loser');
  if (loseRow) rules.push(numRule(sh.getRange(loseRow, 3), { lt: 0, bg: THEME.bad.bg, fg: THEME.bad.fg }));

  const legend = sh.getRange(1, 1, lastRow, 1);
  rules.push(textRule(legend, '🟢', THEME.good.bg,    THEME.good.fg,    false));
  rules.push(textRule(legend, '🔴', THEME.bad.bg,     THEME.bad.fg,     false));
  rules.push(textRule(legend, '🟡', THEME.warn.bg,    THEME.warn.fg,    false));
  rules.push(textRule(legend, '⚪', THEME.neutral.bg, THEME.neutral.fg, false));
  sh.setConditionalFormatRules(rules);

  sh.setColumnWidth(1, 240);
  sh.setColumnWidth(2, 220);
  sh.setColumnWidth(3, 110);
  sh.setFrozenRows(2);
}

function findRow(sh, label) {
  const last = sh.getLastRow();
  for (let r = 1; r <= last; r++) {
    if (String(sh.getRange(r, 1).getDisplayValue()).trim() === label) return r;
  }
  return 0;
}

// ---------------------------------------------------------------------------
// Low-level rule constructors
// ---------------------------------------------------------------------------
function numRule(range, opt) {
  const b = SpreadsheetApp.newConditionalFormatRule();
  if (opt.gt !== undefined)       b.whenNumberGreaterThan(opt.gt);
  else if (opt.gte !== undefined) b.whenNumberGreaterThanOrEqualTo(opt.gte);
  else if (opt.lt !== undefined)  b.whenNumberLessThan(opt.lt);
  else if (opt.lte !== undefined) b.whenNumberLessThanOrEqualTo(opt.lte);
  b.setBackground(opt.bg);
  if (opt.fg) b.setFontColor(opt.fg);
  if (opt.bold) b.setBold(true);
  b.setRanges([range]);
  return b.build();
}

function textRule(range, text, bg, fg, bold) {
  const b = SpreadsheetApp.newConditionalFormatRule()
    .whenTextContains(text)
    .setBackground(bg);
  if (fg) b.setFontColor(fg);
  if (bold) b.setBold(true);
  b.setRanges([range]);
  return b.build();
}

function formulaRule(range, formula, bg, fg) {
  const b = SpreadsheetApp.newConditionalFormatRule()
    .whenFormulaSatisfied(formula)
    .setBackground(bg);
  if (fg) b.setFontColor(fg);
  b.setRanges([range]);
  return b.build();
}

function scaleRule(range, lo, mid, hi) {
  return SpreadsheetApp.newConditionalFormatRule()
    .setGradientMinpointWithValue(GRAD.lo,  SpreadsheetApp.InterpolationType.NUMBER, String(lo))
    .setGradientMidpointWithValue(GRAD.mid, SpreadsheetApp.InterpolationType.NUMBER, String(mid))
    .setGradientMaxpointWithValue(GRAD.hi,  SpreadsheetApp.InterpolationType.NUMBER, String(hi))
    .setRanges([range])
    .build();
}

function a1(colNumber) {
  let s = '';
  let n = colNumber;
  while (n > 0) {
    const rem = (n - 1) % 26;
    s = String.fromCharCode(65 + rem) + s;
    n = Math.floor((n - 1) / 26);
  }
  return s;
}
