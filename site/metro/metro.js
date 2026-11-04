/*
 * The Apache Projects Underground: a metro-style map of Apache communities,
 * drawn in the browser from the JSON projects.apache.org already publishes.
 *
 * A JavaScript port of the layout in comdev/project-map (scripts/build_map.py):
 *   1. Every committee (and podling) is a station. Its categories, merged by
 *      metro/lines.json, decide which coloured lines it is on. A station on two
 *      or more lines is an interchange ("hub").
 *   2. Hubs are laid out by stress majorization from graph distances, with
 *      several seeded restarts; the layout with the fewest line crossings wins.
 *      Each line visits its hubs in an open-TSP order.
 *   3. Hubs snap to a grid; hub-to-hub segments are routed at 0/45/90 degrees;
 *      a line's private stations are spread along its segments and two tails.
 *   4. Lines are drawn (parallel tracks where lines share a segment), ticks for
 *      stations, rings for interchanges, labels placed greedily.
 *
 * Deterministic for a given input and seed. No external libraries.
 * Data: json/foundation/projects.json, committees.json, podlings.json.
 */
(function () {
  'use strict';

  // ---------- small helpers --------------------------------------------------
  function rng(seed) {                      // mulberry32
    let a = seed >>> 0;
    return function () {
      a = (a + 0x6D2B79F5) >>> 0;
      let t = a;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const getJSON = url => fetch(url + (url.indexOf('?') < 0 ? '?' : '&') + 'd=' + new Date().toISOString().slice(0, 10))
    .then(r => { if (!r.ok) throw new Error(url + ': ' + r.status); return r.json(); });
  const asList = v => v == null ? [] : Array.isArray(v) ? v : String(v).split(',').map(s => s.trim()).filter(Boolean);
  const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  const shortName = n => String(n || '').replace(/^Apache\s+/, '').replace(/\s*\((Incubating|in the Attic)\)$/i, '');

  // ---------- 1. model --------------------------------------------------------
  // One station per committee (podlings: one each). The station takes the name
  // of the committee's main entry and the union of its entries' categories.
  function buildModel(cfg, projects, committees, podlings) {
    const cat2line = {};
    cfg.lines.forEach((l, i) => l.categories.forEach(c => { cat2line[c.toLowerCase()] = i; }));
    const groups = {};
    Object.keys(projects).forEach(id => {
      const p = projects[id];
      if (!p || p.status === 'retired' || p.pmc === 'attic') return;
      const key = p.pmc === 'incubator' ? id : p.pmc;
      if (!key || (p.pmc !== 'incubator' && !committees[key])) return;
      (groups[key] = groups[key] || []).push(id);
    });
    const stations = [];
    Object.keys(groups).sort().forEach(key => {
      const ids = groups[key];
      // main entry: keyed by the committee, else most releases, else shortest id
      let main = ids[0];
      const score = id => [id === key ? 1 : 0, (projects[id].release || []).length, -id.length];
      ids.forEach(id => {
        const a = score(id), b = score(main);
        for (let i = 0; i < 3; i++) { if (a[i] !== b[i]) { if (a[i] > b[i]) main = id; break; } }
      });
      const lines = new Set(), langs = [];
      ids.forEach(id => {
        asList(projects[id].category).forEach(c => {
          const li = cat2line[String(c).toLowerCase()];
          if (li != null) lines.add(li);
        });
        asList(projects[id]['programming-language']).forEach(l => { if (langs.indexOf(l) < 0) langs.push(l); });
      });
      const p = projects[main];
      const isPod = p.pmc === 'incubator';
      const pod = isPod ? (podlings[key.replace(/^incubator-/, '')] || {}) : {};
      const com = committees[key] || {};
      let name = shortName(isPod ? (pod.name || p.name) : (com.name || p.name));
      stations.push({
        key, main, name, podling: isPod,
        lines: [...lines].sort((a, b) => a - b),
        langs,
        count: ids.length,
        desc: ' '.join ? '' : '',
        description: String(p.shortdesc || p.description || pod.description || (isPod ? '' : com.shortdesc) || '').replace(/\s+/g, ' ').trim(),
        homepage: p.homepage || pod.homepage || com.homepage || '',
      });
    });
    const onMap = stations.filter(s => s.lines.length);
    const off = stations.filter(s => !s.lines.length);
    onMap.forEach((s, i) => { s.i = i; });
    const hubs = onMap.filter(s => s.lines.length > 1);
    const lineHubs = cfg.lines.map((_, li) => hubs.filter(h => h.lines.indexOf(li) >= 0));
    const lineUniques = cfg.lines.map((_, li) => onMap.filter(s => s.lines.length === 1 && s.lines[0] === li)
      .sort((a, b) => a.name.localeCompare(b.name)));
    return {cfg, stations: onMap, off, hubs, lineHubs, lineUniques, S: cfg.spacing || 52};
  }

  // ---------- 2. hub layout ---------------------------------------------------
  function floyd(D) {
    const n = D.length;
    for (let k = 0; k < n; k++)
      for (let i = 0; i < n; i++) {
        const dik = D[i][k];
        if (dik >= 1e9) continue;
        for (let j = 0; j < n; j++) {
          const v = dik + D[k][j];
          if (v < D[i][j]) D[i][j] = v;
        }
      }
    return D;
  }
  const matrix = (n, v) => Array.from({length: n}, () => new Array(n).fill(v));

  // SMACOF stress majorization
  function stress(X, D, W, iters) {
    const n = X.length;
    const wsum = W.map(r => r.reduce((a, b) => a + b, 0));
    for (let it = 0; it < iters; it++) {
      const Y = X.map(() => [0, 0]);
      for (let i = 0; i < n; i++) {
        let sx = 0, sy = 0;
        for (let j = 0; j < n; j++) {
          if (i === j || !W[i][j]) continue;
          const dx = X[i][0] - X[j][0], dy = X[i][1] - X[j][1];
          const d = Math.hypot(dx, dy) || 1e-6;
          const f = W[i][j] * D[i][j] / d;
          sx += W[i][j] * X[j][0] + f * dx;
          sy += W[i][j] * X[j][1] + f * dy;
        }
        Y[i] = wsum[i] ? [sx / wsum[i], sy / wsum[i]] : X[i];
      }
      X = Y;
    }
    return X;
  }

  // open TSP through points idx: greedy from every start, then 2-opt
  function tspPath(idx, X) {
    if (idx.length <= 2) return idx.slice();
    let best = null, bestLen = Infinity;
    const len = p => p.slice(1).reduce((s, b, i) => s + dist(X[p[i]], X[b]), 0);
    const starts = idx.length <= 6 ? idx : idx.filter((_, i) => i % Math.ceil(idx.length / 6) === 0);
    starts.forEach(start => {
      const left = new Set(idx); left.delete(start);
      const path = [start];
      while (left.size) {
        const last = path[path.length - 1];
        let nb = null, nd = Infinity;
        left.forEach(c => { const d = dist(X[last], X[c]); if (d < nd) { nd = d; nb = c; } });
        path.push(nb); left.delete(nb);
      }
      let improved = true;
      while (improved) {
        improved = false;
        for (let i = 0; i < path.length - 2; i++)
          for (let j = i + 2; j < path.length; j++) {
            const a = X[path[i]], b = X[path[i + 1]], c = X[path[j]], d = j + 1 < path.length ? X[path[j + 1]] : null;
            const before = dist(a, b) + (d ? dist(c, d) : 0), after = dist(a, c) + (d ? dist(b, d) : 0);
            if (after + 1e-9 < before) { path.splice(i + 1, j - i, ...path.slice(i + 1, j + 1).reverse()); improved = true; }
          }
      }
      const L = len(path);
      if (L < bestLen) { bestLen = L; best = path; }
    });
    return best;
  }

  // how many private stations go on each segment and on the two tails
  function allocate(model, orders) {
    const use = {};
    const k = (a, b) => a < b ? a + ',' + b : b + ',' + a;
    orders.forEach(h => h.slice(1).forEach((b, i) => { use[k(h[i], b)] = (use[k(h[i], b)] || 0) + 1; }));
    return orders.map((hubs, li) => {
      const U = model.lineUniques[li].length;
      const segs = hubs.slice(1).map((b, i) => k(hubs[i], b));
      const priv = segs.map((s, i) => use[s] === 1 ? i : -1).filter(i => i >= 0);
      let tail = Math.min(U, 2 * (model.cfg.tail_max || 4)), rest = U - tail;
      const seg = segs.map(() => 0);
      if (priv.length && rest > 0) {
        const give = Math.min(rest, (model.cfg.seg_max || 5) * priv.length);
        const base = Math.floor(give / priv.length), rem = give % priv.length;
        priv.forEach((i, n) => { seg[i] = base + (n < rem ? 1 : 0); });
        rest -= give;
      }
      tail += rest;
      const before = Math.floor(tail / 2);
      return {before, seg, after: tail - before};
    });
  }

  function targetMatrix(model, orders, alloc) {
    const n = model.hubs.length, S = model.S;
    const E = matrix(n, 1e9), path = matrix(n, false);
    for (let i = 0; i < n; i++) E[i][i] = 0;
    orders.forEach((hubs, li) => hubs.slice(1).forEach((b, i) => {
      const a = hubs[i];
      const L = Math.max((alloc[li].seg[i] + 1) * S, 1.35 * S, E[a][b] < 1e9 ? E[a][b] : 0);
      E[a][b] = E[b][a] = L; path[a][b] = path[b][a] = true;
    }));
    const D = floyd(E);
    let far = 0;
    D.forEach(r => r.forEach(v => { if (v < 1e8 && v > far) far = v; }));
    far = far * 1.2 + S;
    const W = matrix(n, 0);
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
      if (D[i][j] >= 1e8) D[i][j] = far;
      if (i !== j) W[i][j] = (path[i][j] ? 4 : 1) / Math.max(D[i][j], 1) ** 2;
    }
    return {D, W};
  }

  function segsCross(p1, p2, p3, p4) {
    const o = (a, b, c) => Math.sign((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]));
    return o(p1, p2, p3) * o(p1, p2, p4) < 0 && o(p3, p4, p1) * o(p3, p4, p2) < 0;
  }
  function countCrossings(X, orders) {
    const segs = [];
    orders.forEach(h => h.slice(1).forEach((b, i) => segs.push([h[i], b])));
    let c = 0;
    for (let i = 0; i < segs.length; i++) for (let j = i + 1; j < segs.length; j++) {
      const [a, b] = segs[i], [d, e] = segs[j];
      if (a === d || a === e || b === d || b === e) continue;
      if (segsCross(X[a], X[b], X[d], X[e])) c++;
    }
    return c;
  }

  function layoutHubs(model) {
    const n = model.hubs.length, S = model.S;
    const hubIdx = new Map(model.hubs.map((h, i) => [h, i]));
    const lineIds = model.lineHubs.map(hs => hs.map(h => hubIdx.get(h)));
    const hop = matrix(n, 1e9);
    for (let i = 0; i < n; i++) hop[i][i] = 0;
    lineIds.forEach(ids => ids.forEach(a => ids.forEach(b => { if (a !== b) hop[a][b] = 1; })));
    const D0 = floyd(hop);
    let far = 0; D0.forEach(r => r.forEach(v => { if (v < 1e8 && v > far) far = v; }));
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) D0[i][j] = (D0[i][j] >= 1e8 ? far + 1 : D0[i][j]) * S * 1.4;
    const W0 = D0.map((r, i) => r.map((v, j) => i === j ? 0 : 1 / Math.max(v, 1) ** 2));
    const restarts = Math.min(model.cfg.restarts || 8, 8);   // browser budget
    let best = null;
    for (let r = 0; r < restarts; r++) {
      const rand = rng((model.cfg.seed || 7) + r * 101);
      let X = Array.from({length: n}, () => [(rand() - .5) * S * n * .6, (rand() - .5) * S * n * .6]);
      X = stress(X, D0, W0, 50);
      let orders, alloc;
      for (let k = 0; k < 2; k++) {
        orders = lineIds.map(ids => tspPath(ids, X));
        alloc = allocate(model, orders);
        const t = targetMatrix(model, orders, alloc);
        X = stress(X, t.D, t.W, 70);
      }
      orders = lineIds.map(ids => tspPath(ids, X));
      alloc = allocate(model, orders);
      const cross = countCrossings(X, orders);
      // rotate so the long axis is horizontal
      const cx = X.reduce((s, p) => s + p[0], 0) / n, cy = X.reduce((s, p) => s + p[1], 0) / n;
      let sxx = 0, syy = 0, sxy = 0;
      X.forEach(([x, y]) => { sxx += (x - cx) ** 2; syy += (y - cy) ** 2; sxy += (x - cx) * (y - cy); });
      const th = 0.5 * Math.atan2(2 * sxy, sxx - syy), c = Math.cos(-th), s = Math.sin(-th);
      X = X.map(([x, y]) => [(x - cx) * c - (y - cy) * s, (x - cx) * s + (y - cy) * c]);
      const w = Math.max(...X.map(p => p[0])) - Math.min(...X.map(p => p[0]));
      const h = Math.max(...X.map(p => p[1])) - Math.min(...X.map(p => p[1]));
      const score = cross * 1000 + 300 * Math.abs(Math.log(Math.max(w, 1) / Math.max(h, 1) / 1.3));
      if (!best || score < best.score) best = {score, X, orders, alloc, cross};
    }
    return best;
  }

  function snapHubs(X, S) {
    const g = S / 4, gap = 1.15 * S, placed = [], out = new Array(X.length);
    const order = X.map((p, i) => i).sort((a, b) => Math.hypot(...X[b]) - Math.hypot(...X[a]));
    order.forEach(i => {
      const bx = Math.round(X[i][0] / g), by = Math.round(X[i][1] / g);
      let spot = null;
      for (let rad = 0; rad < 10 && !spot; rad++)
        for (let dx = -rad; dx <= rad && !spot; dx++)
          for (let dy = -rad; dy <= rad && !spot; dy++) {
            if (Math.max(Math.abs(dx), Math.abs(dy)) !== rad) continue;
            const p = [(bx + dx) * g, (by + dy) * g];
            if (placed.every(q => dist(p, q) >= gap)) spot = p;
          }
      out[i] = spot || [bx * g, by * g];
      placed.push(out[i]);
    });
    return out;
  }

  // ---------- 3. routing and stations ------------------------------------------
  // p -> q with at most one bend, pieces at 0/45/90 degrees
  function octi(p, q, variant) {
    const dx = q[0] - p[0], dy = q[1] - p[1], ax = Math.abs(dx), ay = Math.abs(dy);
    const sx = dx >= 0 ? 1 : -1, sy = dy >= 0 ? 1 : -1;
    if (ax < 1e-6 || ay < 1e-6 || Math.abs(ax - ay) < 1e-6) return [p, q];
    const d = Math.min(ax, ay);
    const diag = [sx * d, sy * d], str = ax > ay ? [sx * (ax - d), 0] : [0, sy * (ay - d)];
    const m = variant ? [p[0] + str[0], p[1] + str[1]] : [p[0] + diag[0], p[1] + diag[1]];
    return [p, m, q];
  }
  const polyLen = P => P.slice(1).reduce((s, b, i) => s + dist(P[i], b), 0);
  function pointAt(P, t) {           // point and unit tangent at arclength t
    for (let i = 1; i < P.length; i++) {
      const L = dist(P[i - 1], P[i]);
      if (t <= L || i === P.length - 1) {
        const f = L ? Math.min(t / L, 1) : 0;
        const ux = L ? (P[i][0] - P[i - 1][0]) / L : 1, uy = L ? (P[i][1] - P[i - 1][1]) / L : 0;
        return {p: [P[i - 1][0] + f * (P[i][0] - P[i - 1][0]), P[i - 1][1] + f * (P[i][1] - P[i - 1][1])], u: [ux, uy]};
      }
      t -= L;
    }
    return {p: P[P.length - 1], u: [1, 0]};
  }
  // a detour p -> w -> q long enough to hold `need` px
  function detour(p, q, need, variant) {
    const mx = (p[0] + q[0]) / 2, my = (p[1] + q[1]) / 2;
    const dx = q[0] - p[0], dy = q[1] - p[1], L = Math.hypot(dx, dy) || 1;
    const nx = -dy / L, ny = dx / L, side = variant % 2 ? -1 : 1;
    for (let k = 1; k < 30; k++) {
      const off = k * need / 8 * side;
      const w = [mx + nx * off, my + ny * off];
      const P = [...octi(p, w, 0), ...octi(w, q, 1).slice(1)];
      if (polyLen(P) >= need) return P;
    }
    return [p, q];
  }

  const DIRS = [[1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1], [0, -1], [1, -1]]
    .map(([x, y]) => { const l = Math.hypot(x, y); return [x / l, y / l]; });

  function buildGeometry(model, best) {
    const S = model.S;
    const H = snapHubs(best.X, S);
    const hubPos = new Map(model.hubs.map((h, i) => [h, H[i]]));
    const occupied = H.slice();          // points used, for tail direction choice
    const tracks = [];                   // {li, pts}
    const segUse = {};                   // shared-corridor offsets
    const keyOf = (a, b) => a < b ? a + ',' + b : b + ',' + a;
    best.orders.forEach((h, li) => h.slice(1).forEach((b, i) => {
      const k = keyOf(h[i], b); (segUse[k] = segUse[k] || []).push(li);
    }));
    const stationPos = new Map();        // station -> {p, u}
    model.hubs.forEach((h, i) => stationPos.set(h, {p: H[i], u: [1, 0], hub: true}));

    best.orders.forEach((hubs, li) => {
      const a = best.alloc[li], uniq = model.lineUniques[li].slice();
      const pts = [];
      // middle segments
      hubs.slice(1).forEach((b, i) => {
        const p = H[hubs[i]], q = H[b], k = a.seg[i];
        let P = octi(p, q, (li + i) % 2);
        const need = (k + 1) * S * 0.9;
        if (k && polyLen(P) < need) P = detour(p, q, need, li + i);
        // parallel offset where lines share the corridor
        const users = segUse[keyOf(hubs[i], b)], off = (users.indexOf(li) - (users.length - 1) / 2) * 6.5;
        const Po = off ? offsetPoly(P, off) : P;
        if (!pts.length) pts.push(...Po); else pts.push(...Po.slice(1));
        const L = polyLen(P);
        for (let s = 1; s <= k && uniq.length; s++) {
          const st = uniq.shift(), at = pointAt(P, L * s / (k + 1));
          stationPos.set(st, at); occupied.push(at.p);
        }
      });
      // tails
      const tail = (end, n, other) => {
        if (!n || !uniq.length) return [];
        let bestDir = DIRS[0], bestScore = -Infinity;
        DIRS.forEach(d => {
          if (other && (d[0] * (other[0] - end[0]) + d[1] * (other[1] - end[1])) > 0) return;
          let sc = 0;
          for (let s = 1; s <= n; s++) {
            const p = [end[0] + d[0] * S * s, end[1] + d[1] * S * s];
            sc += Math.min(...occupied.map(q => dist(p, q)), 4 * S);
          }
          if (Math.abs(d[0]) < 1e-9 || Math.abs(d[1]) < 1e-9) sc *= 1.05;   // prefer straight-ish
          if (sc > bestScore) { bestScore = sc; bestDir = d; }
        });
        const P = [end];
        for (let s = 1; s <= n && uniq.length; s++) {
          const p = [end[0] + bestDir[0] * S * s, end[1] + bestDir[1] * S * s];
          const st = uniq.shift();
          stationPos.set(st, {p, u: bestDir}); occupied.push(p); P.push(p);
        }
        return P;
      };
      if (!hubs.length) {            // a line with no interchanges: straight run
        const start = [0, (li - model.cfg.lines.length / 2) * S * 2];
        const P = [start];
        uniq.forEach((st, s) => { const p = [start[0] + S * s, start[1]]; stationPos.set(st, {p, u: [1, 0]}); P.push(p); });
        tracks.push({li, pts: P});
        return;
      }
      const first = H[hubs[0]], last = H[hubs[hubs.length - 1]];
      const before = tail(first, a.before, hubs.length > 1 ? H[hubs[1]] : null);
      const after = tail(last, a.after + (uniq.length > a.after ? uniq.length - a.after : 0), hubs.length > 1 ? H[hubs[hubs.length - 2]] : null);
      const all = [...before.reverse(), ...(pts.length ? pts : [first]).slice(before.length ? 1 : 0), ...after.slice(1)];
      tracks.push({li, pts: all});
    });
    return {tracks, stationPos};
  }

  function offsetPoly(P, o) {
    const out = [];
    for (let i = 0; i < P.length; i++) {
      const a = P[Math.max(i - 1, 0)], b = P[i], c = P[Math.min(i + 1, P.length - 1)];
      const n1 = normal(a, b), n2 = normal(b, c);
      const n = i === 0 ? n2 : i === P.length - 1 ? n1 : [(n1[0] + n2[0]) / 2, (n1[1] + n2[1]) / 2];
      const l = Math.hypot(...n) || 1, k = (i === 0 || i === P.length - 1) ? 1 : 1 / Math.max(l, .5);
      out.push([b[0] + n[0] / l * o * k, b[1] + n[1] / l * o * k]);
    }
    return out;
  }
  function normal(a, b) {
    const dx = b[0] - a[0], dy = b[1] - a[1], L = Math.hypot(dx, dy) || 1;
    return [-dy / L, dx / L];
  }

  // ---------- 4. labels and SVG -------------------------------------------------
  function placeLabels(model, geo) {
    const boxes = [];
    // keep labels off the track lines (sampled)
    geo.tracks.forEach(t => {
      const L = polyLen(t.pts);
      for (let s = 0; s <= L; s += 8) { const p = pointAt(t.pts, s).p; boxes.push([p[0] - 3, p[1] - 3, p[0] + 3, p[1] + 3]); }
    });
    const hit = b => boxes.some(o => b[0] < o[2] && b[2] > o[0] && b[1] < o[3] && b[3] > o[1]);
    const labels = new Map();
    const order = model.stations.slice().sort((a, b) => b.lines.length - a.lines.length);
    order.forEach(st => {
      const at = geo.stationPos.get(st);
      if (!at) return;
      const fs = st.lines.length > 1 ? 12 : 10.5;
      const w = st.name.length * fs * 0.56, h = fs * 1.1, gap = st.lines.length > 1 ? 11 : 9;
      const nrm = [-at.u[1], at.u[0]];
      const cands = [
        [nrm[0], nrm[1]], [-nrm[0], -nrm[1]], [1, 0], [-1, 0], [0, -1], [0, 1], [.7, -.7], [-.7, -.7], [.7, .7], [-.7, .7],
      ];
      let chosen = null;
      for (const [cx, cy] of cands) {
        const ax = at.p[0] + cx * gap, ay = at.p[1] + cy * gap;
        const anchor = cx > .3 ? 'start' : cx < -.3 ? 'end' : 'middle';
        const x0 = anchor === 'start' ? ax : anchor === 'end' ? ax - w : ax - w / 2;
        const y0 = cy > .3 ? ay : cy < -.3 ? ay - h : ay - h / 2;
        const b = [x0, y0, x0 + w, y0 + h];
        if (!hit(b)) { chosen = {x: ax, y: y0 + h * .8, anchor, b, fs}; break; }
      }
      if (!chosen) {   // fall back to the first choice anyway
        const ax = at.p[0] + nrm[0] * gap, ay = at.p[1] + nrm[1] * gap;
        chosen = {x: ax, y: ay + fs * .35, anchor: 'start', b: [ax, ay - h / 2, ax + w, ay + h / 2], fs};
      }
      boxes.push(chosen.b);
      labels.set(st, chosen);
    });
    return labels;
  }

  function renderSVG(model, geo, labels) {
    const cfg = model.cfg, S = model.S;
    const xs = [], ys = [];
    geo.tracks.forEach(t => t.pts.forEach(p => { xs.push(p[0]); ys.push(p[1]); }));
    labels.forEach(l => { xs.push(l.b[0], l.b[2]); ys.push(l.b[1], l.b[3]); });
    const pad = S * 1.2, minX = Math.min(...xs) - pad, minY = Math.min(...ys) - pad - 70;
    const W = Math.max(...xs) - minX + pad, Hh = Math.max(...ys) - minY + pad + 40 + 24 * Math.ceil(cfg.lines.length / 3);
    const path = P => 'M' + P.map(p => p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' L');
    let svg = `<svg class="map" xmlns="http://www.w3.org/2000/svg" viewBox="${minX.toFixed(0)} ${minY.toFixed(0)} ${W.toFixed(0)} ${Hh.toFixed(0)}" font-family="'Gill Sans','Helvetica Neue',Helvetica,Arial,sans-serif">`;
    svg += `<rect class="bg" x="${minX}" y="${minY}" width="${W}" height="${Hh}" fill="#fff"/>`;
    svg += `<text class="ttl" x="${minX + pad / 2}" y="${minY + 34}" font-size="26" font-weight="bold" fill="#0019A8">${esc(cfg.title)}</text>`;
    svg += `<text class="sub" x="${minX + pad / 2}" y="${minY + 56}" font-size="13" fill="#5f6670">${esc(cfg.subtitle)}</text>`;
    geo.tracks.forEach(t => {
      svg += `<path class="line" data-l="${t.li}" d="${path(t.pts)}" fill="none" stroke="${cfg.lines[t.li].color}" stroke-width="7" stroke-linejoin="round" stroke-linecap="round"/>`;
    });
    model.stations.forEach(st => {
      const at = geo.stationPos.get(st);
      if (!at) return;
      if (st.lines.length > 1) {
        svg += `<circle class="st hub" data-s="${st.i}" cx="${at.p[0].toFixed(1)}" cy="${at.p[1].toFixed(1)}" r="7.5" fill="#fff" stroke="#1c1c1c" stroke-width="3"/>`;
      } else {
        const n = [-at.u[1], at.u[0]], col = cfg.lines[st.lines[0]].color;
        svg += `<line class="st tick" data-s="${st.i}" x1="${at.p[0].toFixed(1)}" y1="${at.p[1].toFixed(1)}" x2="${(at.p[0] + n[0] * 9).toFixed(1)}" y2="${(at.p[1] + n[1] * 9).toFixed(1)}" stroke="${col}" stroke-width="5" stroke-linecap="butt"/>`;
      }
    });
    labels.forEach((l, st) => {
      svg += `<text class="lbl fg" data-s="${st.i}" x="${l.x.toFixed(1)}" y="${l.y.toFixed(1)}" font-size="${l.fs}" text-anchor="${l.anchor}"${st.lines.length > 1 ? ' font-weight="bold"' : ''} fill="#1c1c1c">${esc(st.name)}</text>`;
    });
    // legend
    const ly = minY + Hh - 24 * Math.ceil(cfg.lines.length / 3) - 10, colW = (W - pad) / 3;
    cfg.lines.forEach((l, i) => {
      const x = minX + pad / 2 + (i % 3) * colW, y = ly + Math.floor(i / 3) * 24;
      const n = model.stations.filter(s => s.lines.indexOf(i) >= 0).length;
      svg += `<g class="leg" data-l="${i}"><rect x="${x}" y="${y - 6}" width="28" height="7" rx="3" fill="${l.color}"/>` +
        `<text class="legtxt" x="${x + 36}" y="${y + 2}" font-size="13" fill="#1c1c1c">${esc(l.name)} <tspan class="n" fill="#5f6670">${n}</tspan></text></g>`;
    });
    return svg + '</svg>';
  }

  // ---------- page: pan/zoom, search, lines, details ----------------------------
  // Behaviour follows project-map's scripts/map_template.html:
  //  - click a line (or legend entry, or a line chip) to show only that line;
  //    click again to toggle it off; several lines can be on at once
  //  - hover a station for a tooltip; click it for the details panel
  //  - drag to pan (also touch), wheel / pinch to zoom
  //  - search dims everything but matches; Enter zooms to the first hit
  //  - Esc resets; '/' focuses search; state is kept in the URL hash
  function interactive(model, stage) {
    const svg = stage.querySelector('svg.map');
    const D = model;
    const panel = document.getElementById('panel'), qIn = document.getElementById('q');
    let tip = document.getElementById('tip');
    if (!tip) { tip = document.createElement('div'); tip.id = 'tip'; tip.setAttribute('role', 'tooltip'); document.body.appendChild(tip); }

    const els = {}, lineEls = {}, legEls = {};
    svg.querySelectorAll('[data-s]').forEach(e => (els[e.dataset.s] = els[e.dataset.s] || []).push(e));
    svg.querySelectorAll('.line').forEach(e => (lineEls[e.dataset.l] = lineEls[e.dataset.l] || []).push(e));
    svg.querySelectorAll('.leg').forEach(e => { legEls[e.dataset.l] = e; });
    const byName = new Map(D.stations.map(s => [s.name.toLowerCase(), s]));
    document.getElementById('names').innerHTML = D.stations.map(s => `<option value="${esc(s.name)}">`).join('');
    const pos = s => { const a = D.geo.stationPos.get(s); return a ? a.p : [0, 0]; };

    const state = {lines: new Set(), sel: null, q: ''};

    function apply() {
      const hl = state.lines.size ? state.lines : state.sel != null ? new Set(D.stations[state.sel].lines) : null;
      const q = state.q.trim().toLowerCase();
      D.stations.forEach(s => {
        const match = !!q && (s.name.toLowerCase().includes(q) || s.langs.some(l => l.toLowerCase() === q));
        const dim = (hl && !s.lines.some(l => hl.has(l))) || (q && !match);
        (els[s.i] || []).forEach(e => {
          e.classList.toggle('dim', !!dim);
          e.classList.toggle('sel', state.sel === s.i);
          e.classList.toggle('match', match);
        });
      });
      D.cfg.lines.forEach((_, i) => {
        (lineEls[i] || []).forEach(e => e.classList.toggle('dim', !!(hl && !hl.has(i))));
        if (legEls[i]) legEls[i].classList.toggle('off', state.lines.size > 0 && !state.lines.has(i));
      });
      renderPanel();
      syncHash();
    }

    const chip = i => `<button class="chip${state.lines.has(i) ? ' active' : ''}" data-chip="${i}" title="Show only this line">` +
      `<i style="background:${D.cfg.lines[i].color}"></i>${esc(D.cfg.lines[i].name)}</button>`;
    function renderPanel() {
      if (state.sel == null) {
        panel.innerHTML = `<p class="help"><b>${D.stations.length}</b> communities on <b>${D.cfg.lines.length}</b> lines, ` +
          `<b>${D.hubs.length}</b> of them interchanges. Click a station for details, or pick a line:</p>` +
          `<div class="chips">${D.cfg.lines.map((_, i) => chip(i)).join('')}</div>` +
          `<p class="help">If your project is missing, edit its metadata (categories) in <a href="https://releases.apache.org/" target="_blank" rel="noopener">Apache Trusted Releases</a>.</p>`;
        return;
      }
      const s = D.stations[state.sel];
      const page = s.podling ? `/project.html?${encodeURIComponent(s.main)}` : `/committee.html?${encodeURIComponent(s.key)}`;
      panel.innerHTML =
        `<button class="x" data-clear aria-label="Close">×</button><h2>${esc(s.name)}</h2>` +
        `<div class="kind">${s.podling ? 'Podling' : 'Committee'} · ${s.lines.length > 1 ? 'Interchange · ' + s.lines.length + ' lines' : 'Station'}` +
        `${s.count > 1 ? ' · ' + s.count + ' projects' : ''}</div>` +
        `<div class="chips">${s.lines.map(chip).join('')}</div>` +
        (s.langs.length ? `<div class="members">Languages: <b>${esc(s.langs.join(', '))}</b></div>` : '') +
        (s.description ? `<p>${esc(s.description)}</p>` : '') +
        `<p><a href="${page}">${s.podling ? 'Project details' : 'Committee details'} &rarr;</a>` +
        (/^https?:\/\//i.test(s.homepage || '') ? ` &nbsp; <a href="${esc(s.homepage)}" target="_blank" rel="noopener">Website ↗</a>` : '') + `</p>`;
    }
    panel.addEventListener('click', e => {
      const c = e.target.closest('[data-chip]');
      if (c) { toggleLine(+c.dataset.chip); return; }
      if (e.target.closest('[data-clear]')) { state.sel = null; apply(); }
    });

    function toggleLine(i) { state.lines.has(i) ? state.lines.delete(i) : state.lines.add(i); apply(); }
    function select(i, zoom) {
      state.sel = i; apply();
      if (zoom != null && i != null) { const p = pos(D.stations[i]); zoomTo(p[0], p[1], zoom); }
    }
    function resetAll() { state.lines.clear(); state.sel = null; state.q = ''; qIn.value = ''; setVB({...full}); apply(); }

    // ---- pan / zoom
    const v0 = svg.viewBox.baseVal;
    const full = {x: v0.x, y: v0.y, w: v0.width, h: v0.height};
    let vb = {...full};
    function setVB(n) { vb = n; svg.setAttribute('viewBox', `${vb.x} ${vb.y} ${vb.w} ${vb.h}`); }
    const toSvg = (cx, cy) => { const p = svg.createSVGPoint(); p.x = cx; p.y = cy; return p.matrixTransform(svg.getScreenCTM().inverse()); };
    function zoomAt(px, py, k) {
      const nw = Math.min(Math.max(vb.w * k, full.w / 14), full.w * 1.4), f = nw / vb.w;
      setVB({x: px - (px - vb.x) * f, y: py - (py - vb.y) * f, w: nw, h: vb.h * f});
    }
    function zoomTo(x, y, frac) { const w = full.w * frac, h = full.h * frac; setVB({x: x - w / 2, y: y - h / 2, w, h}); }
    stage.addEventListener('wheel', e => { e.preventDefault(); const p = toSvg(e.clientX, e.clientY); zoomAt(p.x, p.y, Math.exp(e.deltaY * 0.0015)); }, {passive: false});
    const mid = () => ({x: vb.x + vb.w / 2, y: vb.y + vb.h / 2});
    document.getElementById('zin').onclick = () => { const m = mid(); zoomAt(m.x, m.y, 0.7); };
    document.getElementById('zout').onclick = () => { const m = mid(); zoomAt(m.x, m.y, 1 / 0.7); };
    document.getElementById('reset').onclick = resetAll;

    // pointer: drag to pan; a click (no drag) selects. The target is recorded on
    // pointerdown, because pointer capture during a drag retargets later events.
    const ptrs = new Map();
    let drag = null, pinch = null;
    stage.addEventListener('pointerdown', e => {
      ptrs.set(e.pointerId, {x: e.clientX, y: e.clientY});
      if (ptrs.size === 1) drag = {sx: e.clientX, sy: e.clientY, vb: {...vb}, moved: false, target: e.target};
      else if (ptrs.size === 2) { const [a, b] = [...ptrs.values()]; pinch = {d: Math.hypot(a.x - b.x, a.y - b.y)}; if (drag) drag.moved = true; }
    });
    stage.addEventListener('pointermove', e => {
      if (ptrs.has(e.pointerId)) ptrs.set(e.pointerId, {x: e.clientX, y: e.clientY});
      if (pinch && ptrs.size === 2) {
        const [a, b] = [...ptrs.values()], d = Math.hypot(a.x - b.x, a.y - b.y);
        const p = toSvg((a.x + b.x) / 2, (a.y + b.y) / 2);
        zoomAt(p.x, p.y, pinch.d / d); pinch.d = d; return;
      }
      if (drag && ptrs.size === 1) {
        const dx = e.clientX - drag.sx, dy = e.clientY - drag.sy;
        if (!drag.moved && Math.hypot(dx, dy) > 5) {
          drag.moved = true; stage.classList.add('dragging');
          try { stage.setPointerCapture(e.pointerId); } catch (_) {}
          hideTip();
        }
        if (drag.moved) {
          const r = svg.getBoundingClientRect(), k = Math.max(drag.vb.w / r.width, drag.vb.h / r.height);
          setVB({x: drag.vb.x - dx * k, y: drag.vb.y - dy * k, w: vb.w, h: vb.h});
        }
      } else if (!drag || !drag.moved) hover(e);
    });
    const end = e => {
      ptrs.delete(e.pointerId);
      if (ptrs.size < 2) pinch = null;
      if (drag && ptrs.size === 0) {
        if (!drag.moved && e.type === 'pointerup') click(drag.target);
        drag = null; stage.classList.remove('dragging');
      }
    };
    stage.addEventListener('pointerup', end);
    stage.addEventListener('pointercancel', end);
    stage.addEventListener('pointerleave', hideTip);

    function click(t) {
      const st = t.closest && t.closest('[data-s]');
      if (st) { select(state.sel === +st.dataset.s ? null : +st.dataset.s); return; }
      const lg = t.closest && (t.closest('.leg') || t.closest('.line'));
      if (lg) { toggleLine(+lg.dataset.l); return; }
      if (state.sel != null) { state.sel = null; apply(); }
    }

    // ---- tooltip
    function hideTip() { tip.classList.remove('on'); }
    function hover(e) {
      const el = e.target.closest && e.target.closest('[data-s]');
      if (!el) { hideTip(); return; }
      const s = D.stations[+el.dataset.s];
      const d = s.description ? (s.description.length > 220 ? s.description.slice(0, 220) + '…' : s.description) : '';
      tip.innerHTML = `<b>${esc(s.name)}</b>` +
        `<div class="chips">${s.lines.map(i => `<span class="chip"><i style="background:${D.cfg.lines[i].color}"></i>${esc(D.cfg.lines[i].name)}</span>`).join('')}</div>` +
        (s.langs.length ? `<div class="d">${esc(s.langs.join(', '))}</div>` : '') +
        (d ? `<div class="d">${esc(d)}</div>` : '');
      tip.classList.add('on');
      const w = tip.offsetWidth, h = tip.offsetHeight;
      tip.style.left = Math.min(e.clientX + 14, innerWidth - w - 8) + 'px';
      tip.style.top = Math.min(e.clientY + 16, innerHeight - h - 8) + 'px';
    }

    // ---- search, keyboard, URL hash
    qIn.addEventListener('input', () => { state.q = qIn.value; apply(); });
    qIn.addEventListener('keydown', e => {
      if (e.key !== 'Enter') return;
      const q = qIn.value.trim().toLowerCase();
      const hit = byName.get(q) || D.stations.find(s => s.name.toLowerCase().includes(q));
      if (hit) { state.q = ''; qIn.value = hit.name; select(hit.i, 0.28); }
    });
    addEventListener('keydown', e => {
      const typing = /^(INPUT|TEXTAREA)$/.test((document.activeElement || {}).tagName || '');
      if (e.key === '/' && !typing) { e.preventDefault(); qIn.focus(); }
      else if (e.key === 'Escape') { resetAll(); qIn.blur(); }
    });
    function syncHash() {
      try {
        const parts = [];
        if (state.sel != null) parts.push('s=' + encodeURIComponent(D.stations[state.sel].name));
        if (state.lines.size) parts.push('l=' + [...state.lines].sort((a, b) => a - b).join(','));
        history.replaceState(null, '', parts.length ? '#' + parts.join('&') : location.pathname + location.search);
      } catch (_) {}
    }
    const h = new URLSearchParams(location.hash.slice(1));
    (h.get('l') || '').split(',').filter(Boolean).forEach(n => { if (D.cfg.lines[+n]) state.lines.add(+n); });
    const s0 = h.get('s') && byName.get(h.get('s').toLowerCase());
    if (s0) { state.sel = s0.i; apply(); const p = pos(s0); zoomTo(p[0], p[1], 0.35); } else apply();
  }

  // ---------- main -------------------------------------------------------------
  const status = document.getElementById('status');
  Promise.all([
    getJSON('/metro/lines.json'),
    getJSON('/json/foundation/projects.json'),
    getJSON('/json/foundation/committees.json'),
    getJSON('/json/foundation/podlings.json'),
  ]).then(([cfg, projects, committeeList, podlings]) => {
    const committees = {};
    (committeeList || []).forEach(c => { committees[c.id] = c; });
    status.textContent = 'Laying out the map…';
    setTimeout(() => {                 // let the status paint first
      const t0 = performance.now();
      const model = buildModel(cfg, projects, committees, podlings || {});
      const best = layoutHubs(model);
      const geo = buildGeometry(model, best);
      const labels = placeLabels(model, geo);
      const stage = document.getElementById('stage');
      stage.innerHTML = renderSVG(model, geo, labels);
      model.geo = geo;
      interactive(model, stage);
      status.textContent = `${model.stations.length} communities · ${model.hubs.length} interchanges`;
    }, 20);
  }).catch(e => { status.textContent = 'Could not build the map: ' + e.message; });
})();
