/* bn_engine.js — 瀏覽器端離散貝氏網路精確推論（variable elimination），給北士科街廓風險互動地圖用。
 *
 * 與 pgmpy 1.1.2 VariableElimination 的語意一致：
 *   - 每個節點一個 CPT 因子，值為 C-order 攤平，變數順序＝[子節點]+父節點（pgmpy TabularCPD.values 的軸順序）。
 *   - 硬證據：把每個含該變數的因子切到該狀態。
 *   - 查詢只保留「目標 ∪ 證據 ∪ 額外因子變數」的祖先閉包（其餘節點是 barren，邊際化後恆為 1）。
 *   - 消去順序：貪婪，每步選「乘積因子最小」的變數。
 *   - 錨定（virtual evidence）照 run_inference_taipei.anchored_query：
 *       lik = p_shp / max(P(OFP|e), 1e-12)，正規化；P(t|e, 錨定) = Σ_k P(t, OFP=k|e)·lik_k ／ Σ_k P(OFP=k|e)·lik_k。
 *     pgmpy 的做法是加一個二元子節點、其 P(=0|OFP)=lik 再觀測為 0，數學上就是把 lik 乘進聯合分布，兩者相同。
 *   - 同一組證據下，P(t, OFP | e) 只算一次並快取；不同街廓只差 p_shp，加權即可（街廓越多越省）。
 */
(function (global) {
  "use strict";

  function strides(cards) {
    const s = new Array(cards.length);
    let acc = 1;
    for (let i = cards.length - 1; i >= 0; i--) { s[i] = acc; acc *= cards[i]; }
    return s;
  }
  function prod(cards) { let t = 1; for (const c of cards) t *= c; return t; }

  function Factor(vars, cards, values) { this.vars = vars; this.cards = cards; this.values = values; }

  function product(a, b) {
    const vars = a.vars.slice(), cards = a.cards.slice();
    const posB = new Array(b.vars.length);
    for (let j = 0; j < b.vars.length; j++) {
      let k = vars.indexOf(b.vars[j]);
      if (k < 0) { k = vars.length; vars.push(b.vars[j]); cards.push(b.cards[j]); }
      posB[j] = k;
    }
    const n = vars.length, total = prod(cards);
    const sa = strides(a.cards), sb = strides(b.cards);
    const incA = new Array(n).fill(0), incB = new Array(n).fill(0);
    for (let i = 0; i < a.vars.length; i++) incA[i] = sa[i];
    for (let j = 0; j < b.vars.length; j++) incB[posB[j]] = sb[j];
    const out = new Float64Array(total), idx = new Array(n).fill(0);
    let ia = 0, ib = 0;
    for (let t = 0; t < total; t++) {
      out[t] = a.values[ia] * b.values[ib];
      for (let d = n - 1; d >= 0; d--) {
        idx[d]++; ia += incA[d]; ib += incB[d];
        if (idx[d] < cards[d]) break;
        ia -= incA[d] * cards[d]; ib -= incB[d] * cards[d]; idx[d] = 0;
      }
    }
    return new Factor(vars, cards, out);
  }

  function marginalize(f, v) {
    const i = f.vars.indexOf(v);
    if (i < 0) return f;
    const vars = [], cards = [];
    for (let k = 0; k < f.vars.length; k++) if (k !== i) { vars.push(f.vars[k]); cards.push(f.cards[k]); }
    const so = strides(cards), n = f.vars.length, incO = new Array(n).fill(0);
    for (let k = 0, m = 0; k < n; k++) if (k !== i) incO[k] = so[m++];
    const out = new Float64Array(prod(cards)), idx = new Array(n).fill(0);
    let io = 0;
    for (let t = 0; t < f.values.length; t++) {
      out[io] += f.values[t];
      for (let d = n - 1; d >= 0; d--) {
        idx[d]++; io += incO[d];
        if (idx[d] < f.cards[d]) break;
        io -= incO[d] * f.cards[d]; idx[d] = 0;
      }
    }
    return new Factor(vars, cards, out);
  }

  function reduce(f, v, state) {
    const i = f.vars.indexOf(v);
    if (i < 0) return f;
    const vars = [], cards = [];
    for (let k = 0; k < f.vars.length; k++) if (k !== i) { vars.push(f.vars[k]); cards.push(f.cards[k]); }
    const s = strides(f.cards), ci = f.cards[i], si = s[i];
    const out = new Float64Array(f.values.length / ci);
    let m = 0;
    for (let t = 0; t < f.values.length; t++) if (Math.floor(t / si) % ci === state) out[m++] = f.values[t];
    return new Factor(vars, cards, out);
  }

  function reorder(f, order) {
    if (order.length === f.vars.length && order.every((v, k) => f.vars[k] === v)) return f;
    const n = order.length, src = order.map(v => f.vars.indexOf(v));
    if (src.some(k => k < 0) || n !== f.vars.length) throw new Error("reorder: 變數不一致 " + order + " vs " + f.vars);
    const cards = src.map(k => f.cards[k]), sf = strides(f.cards), inc = src.map(k => sf[k]);
    const out = new Float64Array(f.values.length), idx = new Array(n).fill(0);
    let pos = 0;
    for (let t = 0; t < out.length; t++) {
      out[t] = f.values[pos];
      for (let d = n - 1; d >= 0; d--) {
        idx[d]++; pos += inc[d];
        if (idx[d] < cards[d]) break;
        pos -= inc[d] * cards[d]; idx[d] = 0;
      }
    }
    return new Factor(order.slice(), cards, out);
  }

  function Model(spec) {
    this.name = spec.name;
    this.excluded = spec.excluded || [];
    this.reachesO = spec.reaches_O || {};
    this.nodes = new Map();
    const states = new Map();
    for (const nd of spec.nodes) states.set(nd.name, nd.states);
    for (const nd of spec.nodes) {
      const vars = [nd.name].concat(nd.parents);
      const cards = vars.map(v => { const st = states.get(v); if (!st) throw new Error("缺少父節點 " + v + " 的狀態"); return st.length; });
      const vals = Float64Array.from(nd.values);
      if (vals.length !== prod(cards)) throw new Error("CPT 大小不符：" + nd.name);
      this.nodes.set(nd.name, { name: nd.name, states: nd.states, parents: nd.parents, cpd: new Factor(vars, cards, vals) });
    }
    this.cache = new Map();
  }

  Model.prototype.states = function (v) { const nd = this.nodes.get(v); if (!nd) throw new Error("未知節點 " + v); return nd.states; };
  Model.prototype.has = function (v) { return this.nodes.has(v); };
  Model.prototype.stateIndex = function (v, s) {
    const i = this.states(v).indexOf(s);
    if (i < 0) throw new Error("節點 " + v + " 沒有狀態 " + s);
    return i;
  };
  Model.prototype.ancestorsClosure = function (seeds) {
    const seen = new Set(), stack = seeds.slice();
    while (stack.length) {
      const v = stack.pop();
      if (seen.has(v)) continue;
      seen.add(v);
      for (const p of this.nodes.get(v).parents) if (!seen.has(p)) stack.push(p);
    }
    return seen;
  };

  /** 目標節點的聯合後驗（正規化，變數順序＝targets），給硬證據 evidence 與額外似然因子 extra。 */
  Model.prototype.query = function (targets, evidence, extra) {
    evidence = evidence || {};
    const evVars = Object.keys(evidence).filter(v => this.nodes.has(v));
    const seeds = targets.concat(evVars);
    for (const f of (extra || [])) for (const v of f.vars) seeds.push(v);
    const rel = this.ancestorsClosure(seeds);
    let factors = [];
    const addReduced = (f) => {
      for (const e of evVars) if (f.vars.indexOf(e) >= 0) f = reduce(f, e, this.stateIndex(e, evidence[e]));
      if (f.vars.length) factors.push(f);
    };
    for (const v of rel) addReduced(this.nodes.get(v).cpd);
    for (const f of (extra || [])) addReduced(f);
    const keep = new Set(targets);
    const elim = new Set();
    for (const f of factors) for (const v of f.vars) if (!keep.has(v)) elim.add(v);
    while (elim.size) {
      let best = null, bestCost = Infinity;
      for (const v of elim) {
        const u = new Map();
        for (const f of factors) if (f.vars.indexOf(v) >= 0) for (let k = 0; k < f.vars.length; k++) u.set(f.vars[k], f.cards[k]);
        let cost = 1;
        for (const [w, c] of u) if (w !== v) cost *= c;
        if (cost < bestCost) { bestCost = cost; best = v; }
      }
      const inv = factors.filter(f => f.vars.indexOf(best) >= 0);
      factors = factors.filter(f => f.vars.indexOf(best) < 0);
      let p = inv[0];
      for (let k = 1; k < inv.length; k++) p = product(p, inv[k]);
      p = marginalize(p, best);
      if (p.vars.length) factors.push(p);
      elim.delete(best);
    }
    let res = factors.length ? factors[0] : new Factor([], [], new Float64Array([1]));
    for (let k = 1; k < factors.length; k++) res = product(res, factors[k]);
    let s = 0;
    for (const x of res.values) s += x;
    res = new Factor(res.vars, res.cards, res.values.map(x => x / s));
    return reorder(res, targets);
  };

  const OFP = "OriginalFloodPotential";

  /** run_inference_taipei.anchored_query 的瀏覽器版。pshp＝街廓的 P_shp(FD1..5|雨級)；pshp 為 null 時不錯定（全域後驗）。 */
  Model.prototype.anchoredQuery = function (evidence, pshp, targets) {
    const key = JSON.stringify(Object.keys(evidence).sort().map(k => [k, evidence[k]]));
    let c = this.cache.get(key);
    if (!c) { c = { pOFP: null, joints: new Map() }; this.cache.set(key, c); }
    if (!c.pOFP) c.pOFP = Array.from(this.query([OFP], evidence).values);
    let lik = null;
    if (pshp) {
      lik = pshp.map((p, k) => p / Math.max(c.pOFP[k], 1e-12));
      const s = lik.reduce((a, b) => a + b, 0);
      lik = lik.map(x => x / s);
    }
    const out = {};
    for (const t of targets) {
      if (Object.prototype.hasOwnProperty.call(evidence, t) || !this.nodes.has(t)) continue;
      if (t === OFP) {
        const r = c.pOFP.map((p, k) => (lik ? p * lik[k] : p)), s = r.reduce((a, b) => a + b, 0);
        out[t] = r.map(x => x / s);
        continue;
      }
      let J = c.joints.get(t);
      if (!J) { J = this.query([t, OFP], evidence); c.joints.set(t, J); }
      const nt = J.cards[0], no = J.cards[1], r = new Array(nt).fill(0);
      let s = 0;
      for (let j = 0; j < nt; j++) for (let k = 0; k < no; k++) {
        const w = J.values[j * no + k] * (lik ? lik[k] : 1);
        r[j] += w; s += w;
      }
      out[t] = r.map(x => x / s);
    }
    return out;
  };

  Model.prototype.clearCache = function () { this.cache = new Map(); };

  global.BNEngine = { Factor, Model, product, marginalize, reduce, reorder, OFP };
})(typeof window !== "undefined" ? window : globalThis);
