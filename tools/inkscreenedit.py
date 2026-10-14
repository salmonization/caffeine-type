"""Pixel editor for Inkscreen, served to a local browser.

Edits are saved as hand overrides in tools/inkscreen-overrides.txt, then
both fonts and build/inkscreen-chart.png are rebuilt by tools/mkinkscreen.py.
Bold glyphs follow the regular ones automatically until a bold glyph
is edited by hand.

Usage:
    python3 tools/inkscreenedit.py [--port 8765] [--ref screen.r.14.bdf] [--refb screen.b.14.bdf]
"""

import json
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import mkinkscreen as m

CHART = m.ROOT / "build/inkscreen-chart.png"
ROWS = m.TOP - m.BOTTOM + 1


def rows15(g):
    return [g.get(y, 0) for y in range(m.TOP, m.BOTTOM - 1, -1)]


def rows18(g):
    # editor grid spans rows 13..-4 so Unifont's tall originals show whole
    return [g.get(y, 0) for y in range(13, -5, -1)]


def load_data(refs):
    over, overb = m.read_overrides(m.OVERRIDES)
    auto = m.auto_regular([], over)
    regular = {cp: over.get(cp) or auto[cp] for cp in m.CODEPOINTS}
    uni = m.read_bdf(m.UNIFONT, set(m.CODEPOINTS))
    data = {
        "cps": list(m.CODEPOINTS),
        "auto": {cp: rows15(r) for cp, r in auto.items()},
        # bold that follows its bold base, not the regular glyph
        "derived": [cp for cp in m.CODEPOINTS if m.is_derived(cp)],
        "autob": {cp: rows15(r) for cp, r in m.auto_bold(regular, overb).items()},
        "over": {cp: rows15(r) for cp, r in over.items()},
        "overb": {cp: rows15(r) for cp, r in overb.items()},
        "uni": {cp: rows18(r) for cp, r in uni.items()},
    }
    for key, path in zip(("ref", "refb"), refs):
        if path and Path(path).exists():
            data[key] = {cp: rows18(r) for cp, r in m.read_ref(path).items()}
    return data


def parse_glyphs(obj, width):
    """Validate {cp: [15 ints]} from the page; the page is local but still input."""
    out = {}
    for key, rows in obj.items():
        cp = int(key)
        # 14 rows: a page loaded before row 11 existed, starting at row 10
        if cp not in m.CODEPOINTS or len(rows) not in (ROWS, ROWS - 1):
            raise ValueError(f"bad glyph {key}")
        if any(not isinstance(v, int) or not 0 <= v < 1 << width for v in rows):
            raise ValueError(f"bad row in {key}")
        top = m.BOTTOM + len(rows) - 1
        out[cp] = {m.TOP: 0} | {top - i: v for i, v in enumerate(rows)}
    return out


def make_handler(refs):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, code, body, ctype):
            data = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/":
                self.reply(200, PAGE, "text/html; charset=utf-8")
            elif self.path == "/data":
                self.reply(200, json.dumps(load_data(refs)), "application/json")
            else:
                self.reply(404, "not found", "text/plain")

        def do_POST(self):
            if self.path != "/save":
                return self.reply(404, "not found", "text/plain")
            try:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                regular = parse_glyphs(body["regular"], 8)
                bold = parse_glyphs(body["bold"], m.BOLD_W)
            except (ValueError, KeyError, TypeError) as e:
                return self.reply(400, json.dumps({"error": str(e)}), "application/json")
            m.write_overrides(m.OVERRIDES, regular, bold)
            CHART.parent.mkdir(exist_ok=True)
            report = m.rebuild(CHART, [p for p in refs if p and Path(p).exists()])
            msg = {"regular": len(regular), "bold": len(bold), "report": report}
            self.reply(200, json.dumps(msg), "application/json")

        def log_message(self, *args):
            pass

    return Handler


def main(argv):
    def arg(flag, default):
        return argv[argv.index(flag) + 1] if flag in argv else default

    port = int(arg("--port", 8765))
    refs = [arg("--ref", None), arg("--refb", None)]
    # localhost only: the page can overwrite files in the repo
    server = HTTPServer(("127.0.0.1", port), make_handler(refs))
    url = f"http://127.0.0.1:{port}/"
    print(f"Inkscreen editor at {url} (Ctrl-C to stop)")
    webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


PAGE = r"""<!doctype html>
<meta charset="utf-8">
<title>Inkscreen editor</title>
<style>
  body { font: 14px/1.4 -apple-system, sans-serif; margin: 16px; color: #222;
         display: grid; grid-template-columns: 340px auto 1fr; gap: 24px; align-items: start; }
  h2 { font-size: 13px; margin: 14px 0 6px; color: #666; font-weight: 600; }
  #list { display: grid; grid-template-columns: repeat(10, 30px); gap: 3px; }
  #list button { width: 30px; height: 30px; font: 15px ui-monospace, monospace; padding: 0;
                 position: relative; background: #fff; border: 1px solid #ccc; border-radius: 4px; }
  #list button.cur { outline: 2px solid #06f; outline-offset: 1px; }
  #list button.mod::after { content: ""; position: absolute; right: 2px; top: 2px;
                            width: 6px; height: 6px; border-radius: 3px; background: #e60; }
  #grid { display: grid; grid-template-columns: 34px repeat(9, 30px); user-select: none;
          touch-action: none; }
  .c { width: 30px; height: 30px; box-sizing: border-box; border: 1px solid #ddd; position: relative; }
  .c.out { background: repeating-linear-gradient(45deg, #f5f5f5 0 4px, #e6e6e6 4px 8px); }
  .c.off { visibility: hidden; }
  .c.on { background: #000; border-color: #444; }
  .c.base { border-bottom: 3px solid #06f; }
  .c.xh { border-top: 2px dashed #9bf; }
  .g { position: absolute; border-radius: 50%; pointer-events: none; }
  .g.ref { inset: 10px; background: #e33; opacity: .75; }
  .g.uni { inset: 3px; border: 2px solid #2a2; }
  .lbl { font: 11px ui-monospace, monospace; color: #999; text-align: right;
         padding-right: 6px; line-height: 30px; }
  .row { display: flex; gap: 6px; flex-wrap: wrap; margin: 6px 0; }
  button.t { padding: 4px 10px; }
  canvas { image-rendering: pixelated; border: 1px solid #ddd; display: block; margin-bottom: 10px; }
  #status { margin-top: 10px; white-space: pre-wrap; font: 12px ui-monospace, monospace; }
  .key span { display: inline-block; width: 10px; height: 10px; margin: 0 4px 0 10px; vertical-align: -1px; }
</style>

<div>
  <div class="row">
    <label><input type="radio" name="mode" value="reg" checked> Regular</label>
    <label><input type="radio" name="mode" value="bold"> Bold</label>
  </div>
  <div id="list"></div>
  <h2>Keys</h2>
  <div>[ / ] previous / next glyph · type a character to jump · ⌘S save</div>
</div>

<div>
  <div id="title" style="font-weight:600;margin-bottom:6px"></div>
  <div id="grid"></div>
  <div class="row">
    <button class="t" data-shift="up">↑</button><button class="t" data-shift="down">↓</button>
    <button class="t" data-shift="left">←</button><button class="t" data-shift="right">→</button>
    <button class="t" id="clear">Clear</button><button class="t" id="revert">Revert</button>
  </div>
  <div class="row">
    <label><input type="checkbox" id="showref" checked> screen ref</label>
    <label><input type="checkbox" id="showuni"> Unifont</label>
  </div>
  <div class="key"><span style="background:#e33;border-radius:5px"></span>screen.r/b.14
    <span style="border:2px solid #2a2;border-radius:5px;box-sizing:border-box"></span>Unifont
    <span style="background:#06f"></span>baseline</div>
  <div class="row"><button class="t" id="save"><b>Save</b> (rebuild fonts + chart)</button></div>
  <div id="status"></div>
</div>

<div>
  <h2>Preview, 1 logical px = 3 screen px</h2>
  <canvas id="pv"></canvas>
</div>

<script>
const TOP = 11, BOT = -3, GTOP = 13, GBOT = -4, SCALE = 3;
/* "\u0001" marks where the glyph being edited goes */
const SAMPLES = ["nn\u0001nn oo\u0001oo HH\u0001HH", "Hamburgefonstiv","The quick brown fox jumps over the lazy dog",
                 "THE QUICK BROWN FOX JUMPS OVER THE LAZY DOG", "0123456789 ()[]{}<> @#$%&*+-=",
                 "sun3% ls -l /usr/bin | grep cc; echo $HOME"];
let D, cp = 0x61, mode = "reg", reg = {}, boldOver = {}, dirty = false, painting = false, paintOn = true;
const $ = (q) => document.querySelector(q);
const eq = (a, b) => a.length === b.length && a.every((v, i) => v === b[i]);

/* same rule as mkinkscreen.embolden: 8-px regular -> 9-px bold, bit 8 = x 0 */
function emb(r) {
  return r.map((v) => (v << 1) | v);
}
/* derived (accented, spliced) bold follows the bold base; the server
   recomputes it, so it refreshes after a save */
const autoBold = (c) => (D.derivedSet.has(c) ? D.autob[c] : emb(reg[c]));
const boldOf = (c) => boldOver[c] || autoBold(c);
const cur = () => (mode === "reg" ? reg[cp] : boldOf(cp));
const width = () => (mode === "reg" ? 8 : 9);
const modified = (c) => !eq(reg[c], D.auto[c]) || (!!boldOver[c] && !eq(boldOver[c], autoBold(c)));

function setCur(rows) {
  if (mode === "reg") reg[cp] = rows; else boldOver[cp] = rows;
  dirty = true;
  refresh();
}

function buildList() {
  const list = $("#list");
  for (const c of D.cps) {
    const b = document.createElement("button");
    b.textContent = { 0x20: "␠", 0xA0: "NB", 0xAD: "SHY" }[c] || String.fromCodePoint(c);
    b.dataset.cp = c;
    b.onclick = () => select(c);
    list.append(b);
  }
}

function buildGrid() {
  const g = $("#grid");
  for (let y = GTOP; y >= GBOT; y--) {
    const l = document.createElement("div");
    l.className = "lbl";
    l.textContent = y;
    g.append(l);
    for (let x = 0; x < 9; x++) {
      const c = document.createElement("div");
      c.className = "c" + (y > TOP || y < BOT ? " out" : "") + (y === 0 ? " base" : "") + (y === 6 ? " xh" : "");
      c.dataset.x = x;
      c.dataset.y = y;
      g.append(c);
    }
  }
  g.addEventListener("pointerdown", (e) => {
    const t = e.target.closest(".c");
    if (!t || t.classList.contains("out")) return;
    painting = true;
    g.setPointerCapture(e.pointerId);
    paintOn = !t.classList.contains("on");
    paint(t);
  });
  g.addEventListener("pointermove", (e) => {
    if (!painting) return;
    const t = document.elementFromPoint(e.clientX, e.clientY)?.closest(".c");
    if (t && !t.classList.contains("out")) paint(t);
  });
  addEventListener("pointerup", () => (painting = false));
}

function paint(t) {
  if (+t.dataset.x >= width()) return;
  const i = TOP - +t.dataset.y, m = (1 << (width() - 1)) >> +t.dataset.x, rows = cur().slice();
  const v = paintOn ? rows[i] | m : rows[i] & ~m;
  if (v === rows[i]) return;
  rows[i] = v;
  setCur(rows);
}

function shift(dir) {
  const r = cur().slice();
  const out = { up: [...r.slice(1), 0], down: [0, ...r.slice(0, -1)],
                left: r.map((v) => (v << 1) & ((1 << width()) - 1)), right: r.map((v) => v >> 1) }[dir];
  setCur(out);
}

function select(c) {
  cp = c;
  refresh();
}

function refresh() {
  const rows = cur(), ref = D[mode === "reg" ? "ref" : "refb"], showRef = $("#showref").checked,
        showUni = $("#showuni").checked;
  const ch = cp === 32 ? "space" : String.fromCodePoint(cp);
  $("#title").textContent = `U+${cp.toString(16).toUpperCase().padStart(4, "0")} ${ch} · ` +
    (mode === "reg" ? (eq(reg[cp], D.auto[cp]) ? "auto" : "edited")
                    : (boldOver[cp] ? "bold edited" : D.derivedSet.has(cp) ? "bold auto (from bold base)" : "bold auto (from regular)"));
  for (const c of document.querySelectorAll(".c")) {
    const x = +c.dataset.x, y = +c.dataset.y, m = (1 << (width() - 1)) >> x, gi = GTOP - y;
    c.classList.toggle("off", x >= width());
    c.classList.toggle("on", y <= TOP && y >= BOT && !!(rows[TOP - y] & m));
    c.replaceChildren();
    if (showUni && D.uni[cp][gi] & (0x8000 >> x)) c.append(Object.assign(document.createElement("i"), { className: "g uni" }));
    if (showRef && ref && ref[cp] && ref[cp][gi] & (0x8000 >> x)) c.append(Object.assign(document.createElement("i"), { className: "g ref" }));
  }
  for (const b of document.querySelectorAll("#list button")) {
    b.classList.toggle("cur", +b.dataset.cp === cp);
    b.classList.toggle("mod", modified(+b.dataset.cp));
  }
  preview();
}

function drawText(ctx, str, x0, y0, bold) {
  [...str].forEach((s, k) => {
    const c = s.codePointAt(0), rows = reg[c] && (bold ? boldOf(c) : reg[c]), w = bold ? 9 : 8;
    if (!rows) return;
    rows.forEach((v, i) => {
      for (let x = 0; x < w; x++)
        if (v & ((1 << (w - 1)) >> x)) ctx.fillRect(x0 + (k * w + x) * SCALE, y0 + (11 - (TOP - i)) * SCALE, SCALE, SCALE);
    });
  });
}

function preview() {
  const cv = $("#pv"), lines = SAMPLES.map((s) => s.replaceAll("\u0001", String.fromCodePoint(cp)));
  const w = Math.max(...lines.map((l) => l.length)) * 9 * SCALE + 16;
  cv.width = w;
  cv.height = lines.length * 2 * 18 * SCALE + 24;
  const ctx = cv.getContext("2d");
  ctx.fillStyle = "#fff";
  ctx.fillRect(0, 0, cv.width, cv.height);
  ctx.fillStyle = "#000";
  lines.forEach((l, n) => {
    drawText(ctx, l, 8, 8 + n * 2 * 18 * SCALE, false);
    drawText(ctx, l, 8, 8 + (n * 2 + 1) * 18 * SCALE, true);
  });
}

async function save() {
  const regular = {}, bold = {};
  for (const c of D.cps) {
    if (!eq(reg[c], D.auto[c])) regular[c] = reg[c];
    if (boldOver[c] && !eq(boldOver[c], autoBold(c))) bold[c] = boldOver[c];
  }
  $("#status").textContent = "saving…";
  let r, j;
  try {
    r = await fetch("/save", { method: "POST", headers: { "Content-Type": "application/json" },
                               body: JSON.stringify({ regular, bold }) });
    j = await r.json();
  } catch (e) {
    /* edits stay in this page; restart the server and save again */
    $("#status").textContent = "server unreachable, edits kept in this page: " + e;
    return;
  }
  if (!r.ok) { $("#status").textContent = "error: " + j.error; return; }
  dirty = false;
  await load();
  $("#status").textContent = `saved ${j.regular} regular, ${j.bold} bold overrides\n` +
    "rebuilt fonts/inkscreen14*.bdf and build/inkscreen-chart.png" + (j.report.length ? "\n" + j.report.join("\n") : "");
}

addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "s") { e.preventDefault(); save(); return; }
  if (e.metaKey || e.ctrlKey || e.altKey || e.target.tagName === "INPUT") return;
  const i = D.cps.indexOf(cp);
  if (e.key === "[") select(D.cps[Math.max(0, i - 1)]);
  else if (e.key === "]") select(D.cps[Math.min(D.cps.length - 1, i + 1)]);
  else if (e.key.length === 1 && D.cps.includes(e.key.codePointAt(0))) select(e.key.codePointAt(0));
});
addEventListener("beforeunload", (e) => { if (dirty) e.preventDefault(); });
document.querySelectorAll("[data-shift]").forEach((b) => (b.onclick = () => shift(b.dataset.shift)));
$("#clear").onclick = () => setCur(new Array(TOP - BOT + 1).fill(0));
$("#revert").onclick = () => {
  if (mode === "reg") reg[cp] = D.auto[cp].slice(); else delete boldOver[cp];
  dirty = true;
  refresh();
};
$("#save").onclick = save;
$("#showref").onchange = $("#showuni").onchange = refresh;
document.querySelectorAll("[name=mode]").forEach((r) => (r.onchange = () => { mode = r.value; refresh(); }));

/* (re)load after start and every save: derived glyphs follow new bases */
async function load() {
  D = await (await fetch("/data")).json();
  D.derivedSet = new Set(D.derived);
  reg = {}, boldOver = {};
  for (const c of D.cps) {
    reg[c] = (D.over[c] || D.auto[c]).slice();
    if (D.overb[c]) boldOver[c] = D.overb[c].slice();
  }
  if (!$("#list").childElementCount) {
    buildList();
    buildGrid();
  }
  select(cp);
}
load();
</script>
"""

if __name__ == "__main__":
    main(sys.argv[1:])
