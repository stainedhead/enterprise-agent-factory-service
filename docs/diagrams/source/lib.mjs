// Tiny diagram DSL that writes hand-placed, consistently styled SVG.
// Each diagram is a module in this folder that exports `default (d) => { ... }`.
// Render every diagram with: node docs/diagrams/source/render.mjs  (see ../README.md)

export const TONES = {
  client:  { fill: '#f1f7fe', stroke: '#0972d3', ink: '#033160' },
  api:     { fill: '#fff6e8', stroke: '#ec7211', ink: '#5c2c00' },
  data:    { fill: '#eef8ee', stroke: '#1d8102', ink: '#0b3d00' },
  aws:     { fill: '#f6f0ff', stroke: '#7d3cff', ink: '#3b1580' },
  k8s:     { fill: '#edf2fe', stroke: '#326ce5', ink: '#102a6b' },
  neutral: { fill: '#f6f7f8', stroke: '#5f6b7a', ink: '#232f3e' },
  danger:  { fill: '#fdeeec', stroke: '#d13212', ink: '#6b1104' },
  dark:    { fill: '#232f3e', stroke: '#232f3e', ink: '#ffffff' },
};
const FONT = "-apple-system, 'Segoe UI', 'Helvetica Neue', Helvetica, Arial, sans-serif";
const MONO = "ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace";
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
export const textWidth = (s, size, bold = false) => String(s).length * size * (bold ? 0.6 : 0.55);

export function createDiagram(name) {
  const els = { groups: [], edges: [], nodes: [], over: [] };
  const nodes = {};
  let W = 1200, H = 800, title = '', subtitle = '';
  const d = {
    name,
    size(w, h) { W = w; H = h; },
    title(t, s = '') { title = t; subtitle = s; },
    tone: (t) => TONES[t] || TONES.neutral,

    group({ x, y, w, h, label, tone = 'neutral', dashed = true, sub }) {
      const t = TONES[tone];
      els.groups.push(`<g><rect x="${x}" y="${y}" width="${w}" height="${h}" rx="14" fill="${t.fill}" fill-opacity="0.55" stroke="${t.stroke}" stroke-width="1.4" ${dashed ? 'stroke-dasharray="6 5"' : ''}/>` +
        `<text x="${x + 16}" y="${y + 24}" font-family="${FONT}" font-size="13" font-weight="700" fill="${t.stroke}" letter-spacing="0.6">${esc(label.toUpperCase())}</text>` +
        (sub ? `<text x="${x + 16}" y="${y + 41}" font-family="${FONT}" font-size="11.5" fill="#5f6b7a">${esc(sub)}</text>` : '') + `</g>`);
    },

    node({ id, x, y, w = 180, h, title: t, sub = [], tone = 'neutral', badge, mono = false, shape = 'box', align = 'center' }) {
      const tn = TONES[tone];
      const lines = Array.isArray(sub) ? sub : [sub];
      h = h ?? 26 + 18 + lines.length * 17 + 4;
      nodes[id] = { x, y, w, h };
      const cx = x + w / 2;
      const tx = align === 'left' ? x + 14 : cx;
      const anchor = align === 'left' ? 'start' : 'middle';
      const textTop = y + (h - (18 + lines.length * 17)) / 2 + 14;
      let s = '<g>';
      if (shape === 'db') {
        const e = 9;
        s += `<path d="M${x},${y + e} a${w / 2},${e} 0 0 0 ${w},0 v${h - 2 * e} a${w / 2},${e} 0 0 1 ${-w},0 z" fill="${tn.fill}" stroke="${tn.stroke}" stroke-width="1.6"/>`;
        s += `<ellipse cx="${cx}" cy="${y + e}" rx="${w / 2}" ry="${e}" fill="${tn.fill}" stroke="${tn.stroke}" stroke-width="1.6"/>`;
      } else {
        s += `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="10" fill="${tn.fill}" stroke="${tn.stroke}" stroke-width="1.6"/>`;
        s += `<rect x="${x}" y="${y}" width="5" height="${h}" rx="2" fill="${tn.stroke}" opacity="${tone === 'dark' ? 0 : 0.9}"/>`;
      }
      const off = shape === 'db' ? 6 : 0;
      s += `<text x="${tx}" y="${textTop + off}" text-anchor="${anchor}" font-family="${FONT}" font-size="14.5" font-weight="700" fill="${tn.ink}">${esc(t)}</text>`;
      lines.forEach((l, i) => {
        s += `<text x="${tx}" y="${textTop + off + 19 + i * 17}" text-anchor="${anchor}" font-family="${mono ? MONO : FONT}" font-size="${mono ? 11.5 : 12.5}" fill="${tone === 'dark' ? '#d5dbdb' : '#414d5c'}">${esc(l)}</text>`;
      });
      if (badge) {
        const bw = textWidth(badge, 10.5, true) + 14;
        s += `<rect x="${x + w - bw - 8}" y="${y - 9}" width="${bw}" height="18" rx="9" fill="${tn.stroke}"/>`;
        s += `<text x="${x + w - bw / 2 - 8}" y="${y + 4}" text-anchor="middle" font-family="${FONT}" font-size="10.5" font-weight="700" fill="#fff">${esc(badge)}</text>`;
      }
      els.nodes.push(s + '</g>');
      return nodes[id];
    },

    // Free text (captions, callouts). lines: string | string[]
    text({ x, y, lines, size = 12.5, color = '#414d5c', bold = false, anchor = 'start', mono = false }) {
      const ls = Array.isArray(lines) ? lines : [lines];
      els.over.push(ls.map((l, i) => `<text x="${x}" y="${y + i * (size + 5)}" text-anchor="${anchor}" font-family="${mono ? MONO : FONT}" font-size="${size}" ${bold ? 'font-weight="700"' : ''} fill="${color}">${esc(l)}</text>`).join(''));
    },

    // Numbered step marker
    step({ x, y, n, tone = 'api' }) {
      const t = TONES[tone];
      els.over.push(`<circle cx="${x}" cy="${y}" r="11" fill="${t.stroke}"/><text x="${x}" y="${y + 4.5}" text-anchor="middle" font-family="${FONT}" font-size="12" font-weight="700" fill="#fff">${n}</text>`);
    },

    edge(from, to, o = {}) {
      const a = nodes[from], b = nodes[to];
      if (!a || !b) throw new Error(`${name}: unknown node in edge ${from} -> ${to}`);
      const side = (n, sd, f = 0.5) => ({
        l: [n.x, n.y + n.h * f], r: [n.x + n.w, n.y + n.h * f],
        t: [n.x + n.w * f, n.y], b: [n.x + n.w * f, n.y + n.h],
      })[sd];
      let fs = o.from, ts = o.to;
      if (!fs || !ts) {
        const dx = (b.x + b.w / 2) - (a.x + a.w / 2), dy = (b.y + b.h / 2) - (a.y + a.h / 2);
        const horiz = (a.x + a.w < b.x) || (b.x + b.w < a.x);
        const vert = (a.y + a.h < b.y) || (b.y + b.h < a.y);
        if (horiz && (!vert || Math.abs(dx) > Math.abs(dy))) { fs = fs || (dx > 0 ? 'r' : 'l'); ts = ts || (dx > 0 ? 'l' : 'r'); }
        else { fs = fs || (dy > 0 ? 'b' : 't'); ts = ts || (dy > 0 ? 't' : 'b'); }
      }
      const p0 = side(a, fs, o.ff ?? 0.5), p1 = side(b, ts, o.tf ?? 0.5);
      let pts = [p0];
      if (o.via) pts.push(...o.via);
      else {
        const h0 = fs === 'l' || fs === 'r', h1 = ts === 'l' || ts === 'r';
        if (h0 && h1 && Math.abs(p0[1] - p1[1]) > 0.5) { const mx = o.mid ?? (p0[0] + p1[0]) / 2; pts.push([mx, p0[1]], [mx, p1[1]]); }
        else if (!h0 && !h1 && Math.abs(p0[0] - p1[0]) > 0.5) { const my = o.mid ?? (p0[1] + p1[1]) / 2; pts.push([p0[0], my], [p1[0], my]); }
        else if (h0 && !h1) pts.push([p1[0], p0[1]]);
        else if (!h0 && h1) pts.push([p0[0], p1[1]]);
      }
      pts.push(p1);
      const color = o.tone ? TONES[o.tone].stroke : '#5f6b7a';
      const mk = `arrow-${o.tone || 'neutral'}`;
      let s = `<polyline points="${pts.map((p) => p.join(',')).join(' ')}" fill="none" stroke="${color}" stroke-width="${o.width ?? 1.7}" stroke-linejoin="round" ${o.dashed ? 'stroke-dasharray="6 4"' : ''} marker-end="url(#${mk})" ${o.both ? `marker-start="url(#${mk}-start)"` : ''}/>`;
      if (o.label) {
        let lx, ly;
        if (o.lx !== undefined) { lx = o.lx; ly = o.ly; }
        else {
          let best = 0, bi = 0;
          for (let i = 0; i < pts.length - 1; i++) { const L = Math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]); if (L > best) { best = L; bi = i; } }
          lx = (pts[bi][0] + pts[bi + 1][0]) / 2; ly = (pts[bi][1] + pts[bi + 1][1]) / 2;
        }
        s += label(lx, ly, o.label, color);
      }
      els.edges.push(s);
    },

    // Straight arrow between two points (for group-to-group flows).
    arrow({ x1, y1, x2, y2, tone = 'neutral', label: lb, dashed = false }) {
      const color = TONES[tone].stroke;
      els.edges.push(`<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${color}" stroke-width="1.8" ${dashed ? 'stroke-dasharray="6 4"' : ''} marker-end="url(#arrow-${tone})"/>` + (lb ? label((x1 + x2) / 2, (y1 + y2) / 2, lb, color) : ''));
    },

    // Sequence diagram: participants laid out left to right, steps top to bottom.
    seq({ x0 = 40, y0 = 90, colW = 200, boxW = 170, rowH = 46, participants, steps, bottomPad = 30 }) {
      const col = {};
      participants.forEach((p, i) => { col[p.id] = x0 + i * colW + colW / 2; });
      const headH = 62;
      let y = y0 + headH + 30;
      const rows = [];
      for (const st of steps) {
        if (st.frame) { rows.push({ ...st, y }); y += 26; continue; }
        if (st.note) { const n = (Array.isArray(st.note) ? st.note.length : 1); rows.push({ ...st, y }); y += 18 + n * 16 + 14; continue; }
        if (st.endFrame) { rows.push({ ...st, y }); y += 14; continue; }
        rows.push({ ...st, y }); y += st.from === st.to ? rowH + 14 : rowH;
      }
      const yEnd = y + bottomPad;
      participants.forEach((p) => {
        const cx = col[p.id];
        els.groups.push(`<line x1="${cx}" y1="${y0 + headH}" x2="${cx}" y2="${yEnd}" stroke="#aab7b8" stroke-width="1.4" stroke-dasharray="5 5"/>`);
        d.node({ id: `__p_${p.id}`, x: cx - boxW / 2, y: y0, w: boxW, h: headH, title: p.title, sub: p.sub ? [p.sub] : [], tone: p.tone || 'neutral' });
      });
      let n = 0; const frames = [];
      for (const r of rows) {
        if (r.frame) { frames.push(r); continue; }
        if (r.endFrame) {
          const f = frames.pop();
          const xs = f.over.map((id) => col[id]);
          const fx = Math.min(...xs) - boxW / 2 - 6, fw = Math.max(...xs) - Math.min(...xs) + boxW + 12;
          const t = TONES[f.tone || 'neutral'];
          els.groups.push(`<rect x="${fx}" y="${f.y - 4}" width="${fw}" height="${r.y - f.y + 8}" rx="8" fill="${t.fill}" fill-opacity="0.45" stroke="${t.stroke}" stroke-width="1.2" stroke-dasharray="4 4"/>` +
            `<rect x="${fx}" y="${f.y - 4}" width="${textWidth(f.frame, 11.5, true) + 18}" height="20" rx="6" fill="${t.stroke}"/>` +
            `<text x="${fx + 9}" y="${f.y + 10}" font-family="${FONT}" font-size="11.5" font-weight="700" fill="#fff">${esc(f.frame)}</text>`);
          continue;
        }
        if (r.note) {
          const xs = (r.over || [r.at]).map((id) => col[id]);
          const lines = Array.isArray(r.note) ? r.note : [r.note];
          const nx = Math.min(...xs) - boxW / 2 + 6, nw = Math.max(...xs) - Math.min(...xs) + boxW - 12;
          const t = TONES[r.tone || 'neutral'];
          els.over.push(`<rect x="${nx}" y="${r.y}" width="${nw}" height="${lines.length * 16 + 14}" rx="6" fill="${t.fill}" stroke="${t.stroke}" stroke-width="1.1"/>` +
            lines.map((l, i) => `<text x="${nx + nw / 2}" y="${r.y + 19 + i * 16}" text-anchor="middle" font-family="${FONT}" font-size="12" fill="${t.ink}">${esc(l)}</text>`).join(''));
          continue;
        }
        n += 1;
        const x1 = col[r.from], x2 = col[r.to];
        const color = r.tone ? TONES[r.tone].stroke : '#414d5c';
        const mk = `arrow-${r.tone || 'neutral'}`;
        const yy = r.y + 18;
        if (r.from === r.to) {
          els.edges.push(`<path d="M${x1},${yy} h42 v24 h-40" fill="none" stroke="${color}" stroke-width="1.6" marker-end="url(#${mk})"/>`);
          els.over.push(`<text x="${x1 + 50}" y="${yy + 16}" font-family="${FONT}" font-size="12.5" fill="#232f3e">${esc(r.label)}</text>`);
        } else {
          const dir = x2 > x1 ? 1 : -1;
          els.edges.push(`<line x1="${x1}" y1="${yy}" x2="${x2 - dir * 2}" y2="${yy}" stroke="${color}" stroke-width="1.6" ${r.dashed ? 'stroke-dasharray="6 4"' : ''} marker-end="url(#${mk})"/>`);
          const lx = (x1 + x2) / 2;
          els.over.push(`<text x="${lx}" y="${yy - 7}" text-anchor="middle" font-family="${FONT}" font-size="12.5" fill="#232f3e">${esc(r.label)}</text>`);
        }
        if (!r.nonum) d.step({ x: x2 < x1 ? x1 + 22 : x1 - 22, y: yy, n, tone: r.tone || 'neutral' });
      }
      return yEnd;
    },

    render() {
      const markers = Object.entries(TONES).map(([k, t]) =>
        `<marker id="arrow-${k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="${t.stroke}"/></marker>` +
        `<marker id="arrow-${k}-start" viewBox="0 0 10 10" refX="1" refY="5" markerWidth="8" markerHeight="8" orient="auto"><path d="M10,0 L0,5 L10,10 z" fill="${t.stroke}"/></marker>`).join('');
      const head = title ? `<text x="32" y="44" font-family="${FONT}" font-size="22" font-weight="700" fill="#16191f">${esc(title)}</text>` +
        (subtitle ? `<text x="32" y="68" font-family="${FONT}" font-size="13.5" fill="#5f6b7a">${esc(subtitle)}</text>` : '') : '';
      const foot = `<text x="${W - 24}" y="${H - 14}" text-anchor="end" font-family="${FONT}" font-size="10.5" fill="#8d99a8">Enterprise Agent Factory Service · ${esc(name)}</text>`;
      return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(title)}">` +
        `<title>${esc(title)}</title><defs>${markers}</defs>` +
        `<rect width="${W}" height="${H}" fill="#ffffff"/><rect x="0" y="0" width="${W}" height="6" fill="#ff9900"/>` +
        head + els.groups.join('') + els.edges.join('') + els.nodes.join('') + els.over.join('') + foot + `</svg>\n`;
    },
  };
  function label(x, y, t, color) {
    const lines = Array.isArray(t) ? t : [t];
    const w = Math.max(...lines.map((l) => textWidth(l, 11.5))) + 12, h = lines.length * 15 + 6;
    return `<rect x="${x - w / 2}" y="${y - h / 2}" width="${w}" height="${h}" rx="4" fill="#ffffff" stroke="${color}" stroke-opacity="0.35"/>` +
      lines.map((l, i) => `<text x="${x}" y="${y - h / 2 + 15 + i * 15}" text-anchor="middle" font-family="${FONT}" font-size="11.5" fill="#232f3e">${esc(l)}</text>`).join('');
  }
  return d;
}
