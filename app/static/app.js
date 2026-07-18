(() => {
  const base = document.body.dataset.basePath || '';
  const colors = ['#7170ff', '#52d6ff', '#d0d6e0', '#10b981', '#f59e0b', '#f472b6', '#a78bfa', '#fb7185', '#22d3ee', '#84cc16', '#f97316', '#94a3b8'];
  let currentRange = '1M';
  let currentPayload = null;
  let hiddenSeries = new Set();

  const $ = (id) => document.getElementById(id);
  const pct = (value, digits = 1) => value == null ? '—' : `${value >= 0 ? '+' : ''}${(value * 100).toFixed(digits)}%`;
  const usd = (value) => value == null ? '—' : new Intl.NumberFormat('en-US', {style:'currency', currency:'USD', maximumFractionDigits:value < 10 ? 2 : 0}).format(value);
  const compactUsd = (value) => value ? `$${Intl.NumberFormat('en-US', {notation:'compact', maximumFractionDigits:1}).format(value)}` : '—';
  const sigma = (value) => value == null ? '—' : `${value >= 0 ? '+' : ''}${value.toFixed(2)}σ`;
  const dateLabel = (value) => { if (!value) return 'Awaiting first refresh'; const d = new Date(value); return Number.isNaN(d.valueOf()) ? value : d.toLocaleString([], {dateStyle:'medium', timeStyle:'short'}); };
  const signedClass = (value) => value == null ? '' : value >= 0 ? 'positive' : 'negative';

  async function load(range) {
    currentRange = range;
    document.querySelectorAll('[data-range]').forEach(button => button.classList.toggle('active', button.dataset.range === range));
    try {
      const response = await fetch(`${base}/api/v1/snapshot?range=${encodeURIComponent(range)}`, {headers:{Accept:'application/json'}});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      currentPayload = await response.json();
      render(currentPayload);
    } catch (error) {
      $('chart').innerHTML = `<div class="empty"><strong>Market data could not be loaded</strong><span>${escapeHtml(error.message)}</span></div>`;
      $('freshness').textContent = 'Data connection degraded';
    }
  }

  function render(payload) {
    $('index-level').textContent = Number(payload.index.level || 100).toFixed(2);
    $('index-change').textContent = `${pct(payload.index.period_return)} over ${payload.range}`;
    $('index-change').className = signedClass(payload.index.period_return);
    $('constituent-count').textContent = payload.index.constituent_count;
    const valid = payload.constituents.filter(row => row.group_standard_deviation != null);
    const dispersion = valid.length ? valid[0].group_standard_deviation : null;
    $('dispersion').textContent = dispersion == null ? '—' : `${(dispersion * 100).toFixed(1)}%`;
    const largest = [...payload.constituents].filter(row => row.z_score != null).sort((a,b) => Math.abs(b.z_score)-Math.abs(a.z_score))[0];
    $('largest-outlier').textContent = largest ? largest.ticker : '—';
    $('largest-outlier-note').textContent = largest ? `${sigma(largest.z_score)} · ${largest.outlier_label}` : 'Measured in standard deviations';
    const sync = payload.data_freshness;
    $('freshness').textContent = sync ? `Updated ${dateLabel(sync.finished_at)} · ${sync.status}` : 'Awaiting first market-data refresh';
    renderLegend(payload.series.series || []);
    renderChart(payload.series);
    renderOutliers(payload.constituents);
    renderTable(payload.constituents);
    renderCompanies(payload.constituents);
  }

  function renderLegend(series) {
    const legend = $('chart-legend');
    legend.innerHTML = '';
    series.forEach((row, index) => {
      const button = document.createElement('button');
      button.className = hiddenSeries.has(row.symbol) ? 'off' : '';
      button.innerHTML = `<i style="background:${colors[index % colors.length]}"></i>${escapeHtml(row.symbol)}`;
      button.title = row.name;
      button.addEventListener('click', () => {
        hiddenSeries.has(row.symbol) ? hiddenSeries.delete(row.symbol) : hiddenSeries.add(row.symbol);
        renderLegend(series); renderChart(currentPayload.series);
      });
      legend.appendChild(button);
    });
  }

  function renderChart(data) {
    const host = $('chart');
    const visible = (data.series || []).filter(row => !hiddenSeries.has(row.symbol) && row.values.some(value => value != null));
    if (!data.dates?.length || !visible.length) { host.innerHTML = '<div class="empty"><strong>History is being calculated</strong><span>The dashboard will populate after the first market-data refresh.</span></div>'; return; }
    const width = 1100, height = 380, pad = {l:48,r:20,t:18,b:28};
    const all = visible.flatMap(row => row.values.filter(value => value != null));
    let min = Math.min(...all), max = Math.max(...all); const margin = Math.max((max-min)*.12, 2); min -= margin; max += margin;
    const x = i => pad.l + i * (width-pad.l-pad.r) / Math.max(1, data.dates.length-1);
    const y = value => pad.t + (max-value) * (height-pad.t-pad.b) / Math.max(.0001, max-min);
    const grid = Array.from({length:5}, (_,i) => { const value = max - i*(max-min)/4; const yp=y(value); return `<line class="grid-line" x1="${pad.l}" x2="${width-pad.r}" y1="${yp}" y2="${yp}"/><text class="axis-label" x="${pad.l-8}" y="${yp+3}" text-anchor="end">${value.toFixed(0)}</text>`; }).join('');
    const paths = visible.map((row,index) => {
      let path='', drawing=false;
      row.values.forEach((value,i) => { if(value==null){drawing=false;return;} path += `${drawing?'L':'M'}${x(i).toFixed(2)},${y(value).toFixed(2)} `; drawing=true; });
      return `<path class="series-line" d="${path}" stroke="${colors[(data.series.indexOf(row))%colors.length]}" opacity="${row.symbol==='SHM-EVTOL'?1:.72}" stroke-width="${row.symbol==='SHM-EVTOL'?3:1.7}"/>`;
    }).join('');
    const labels = [0, Math.floor((data.dates.length-1)/2), data.dates.length-1].filter((v,i,a)=>a.indexOf(v)===i).map(i=>`<text class="axis-label" x="${x(i)}" y="${height-5}" text-anchor="${i===0?'start':i===data.dates.length-1?'end':'middle'}">${shortDate(data.dates[i])}</text>`).join('');
    host.innerHTML = `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">${grid}${paths}${labels}</svg>`;
  }

  function renderOutliers(rows) {
    const host = $('outlier-list');
    const ranked = [...rows].filter(row => row.listing_status === 'active' && row.z_score != null).sort((a,b)=>b.z_score-a.z_score);
    if (!ranked.length) { host.innerHTML='<div class="empty">Outlier scores appear after two price observations.</div>'; return; }
    host.innerHTML = ranked.map(row => {
      const position = Math.max(0,Math.min(100,50 + row.z_score*20));
      return `<div class="outlier-row"><span class="ticker">${escapeHtml(row.ticker)}</span><div class="sigma-track"><i class="sigma-point" style="left:${position}%"></i></div><b class="${signedClass(row.period_return)}">${pct(row.period_return)}</b><small>${sigma(row.z_score)}</small></div>`;
    }).join('');
  }

  function renderTable(rows) {
    const host = $('constituent-table');
    const sorted = [...rows].sort((a,b)=>b.weight-a.weight || (b.period_return??-99)-(a.period_return??-99));
    host.innerHTML = sorted.map(row => `<tr><td><div class="company-cell"><span class="company-avatar">${escapeHtml(row.ticker.slice(0,3))}</span><span><strong>${escapeHtml(row.display_name)}</strong><small>${escapeHtml(row.exchange)} · ${escapeHtml(row.category.replaceAll('-',' '))}</small></span></div></td><td>${usd(row.price_usd)}</td><td class="${signedClass(row.period_return)}">${pct(row.period_return)}</td><td class="${signedClass(row.z_score)}">${sigma(row.z_score)}</td><td>${row.annualized_volatility==null?'—':`${(row.annualized_volatility*100).toFixed(0)}%`}</td><td>${row.weight ? `${(row.weight*100).toFixed(1)}%` : '—'}</td><td><span class="status-pill ${row.eligible?'yes':''}" title="${escapeHtml(row.eligibility_reason)}"><i class="dot ${row.eligible?'eligible':'tracked'}"></i>${row.eligible?'Eligible':row.listing_status==='historical'?'Historical':'Tracked only'}</span></td></tr>`).join('');
  }

  function renderCompanies(rows) {
    const host = $('company-grid');
    host.innerHTML = [...rows].sort((a,b)=>a.display_name.localeCompare(b.display_name)).map(row => `<a class="company-card" href="${escapeAttribute(row.investor_relations_url)}" target="_blank" rel="noopener noreferrer"><div class="card-top"><div><span class="exchange">${escapeHtml(row.exchange)}:${escapeHtml(row.ticker)}</span><h3>${escapeHtml(row.display_name)}</h3></div><span class="category">${escapeHtml(row.category.replaceAll('-',' '))}</span></div><p>${escapeHtml(row.materiality_summary)}</p><footer><span>${escapeHtml(row.country)} · listed ${escapeHtml(row.listing_date.slice(0,4))}</span><span>${row.listing_status==='active'?'Active listing':'Historical record'} ↗</span></footer></a>`).join('');
  }

  function escapeHtml(value) { const node=document.createElement('div'); node.textContent=String(value??''); return node.innerHTML; }
  function escapeAttribute(value) { return escapeHtml(value).replaceAll('"','&quot;'); }
  function shortDate(value) { const source=value.includes('T')?value:`${value}T00:00:00Z`; const date=new Date(source); if(currentRange==='1D') return date.toLocaleTimeString([], {hour:'numeric',minute:'2-digit'}); return date.toLocaleDateString([], {month:'short', day:'numeric', year: currentRange==='MAX'?'2-digit':undefined, timeZone:'UTC'}); }

  document.querySelectorAll('[data-range]').forEach(button => button.addEventListener('click', () => load(button.dataset.range)));
  const tooltip = $('tooltip');
  document.querySelectorAll('[data-help]').forEach(button => {
    button.addEventListener('mouseenter', event => { tooltip.textContent=button.dataset.help; tooltip.style.display='block'; const box=event.target.getBoundingClientRect(); tooltip.style.left=`${Math.min(innerWidth-280,box.left)}px`; tooltip.style.top=`${box.bottom+8}px`; });
    button.addEventListener('mouseleave', () => tooltip.style.display='none');
  });
  load(currentRange);
})();
