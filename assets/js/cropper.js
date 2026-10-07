const MIN_PX = 24;

const clamp = (v, lo, hi) => Math.min(Math.max(v, lo), hi);

function el(tag, cls) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  return node;
}

function place(node, x, y, w, h) {
  const s = node.style;
  s.transform = `translate(${x}px, ${y}px)`;
  s.width = `${Math.max(0, w)}px`;
  s.height = `${Math.max(0, h)}px`;
}

export default function ({ data, parentElement, setStateValue }) {
  const root = parentElement.querySelector(".zhp-cropper");
  const ratio = data.ratio || null; 
  const frame = data.frame;      
  const BASE = data.base || 1200;  

  const S = parentElement.__zhp || (parentElement.__zhp = {});
  if (S.src === data.src && S.ratio === ratio) return;
  if (S.ro) S.ro.disconnect();
  S.src = data.src;
  S.ratio = ratio;

  root.innerHTML = "";
  const stage = el("div", "stage");
  const img = el("img");
  img.alt = "";
  img.draggable = false;

  const dimT = el("div", "dim");
  const dimB = el("div", "dim");
  const dimL = el("div", "dim");
  const dimR = el("div", "dim");
  const boxEl = el("div", "box");
  for (const h of ["nw", "ne", "sw", "se"]) {
    const handle = el("i", `handle ${h}`);
    handle.dataset.h = h;
    boxEl.appendChild(handle);
  }
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", "frame");
  svg.setAttribute("preserveAspectRatio", "none");
  const poly = document.createElementNS(NS, "polyline");
  poly.setAttribute("fill", "none");
  poly.setAttribute("stroke", "#fff");
  poly.setAttribute("stroke-width", frame.stroke);
  poly.setAttribute("stroke-linecap", "square");
  svg.appendChild(poly);
  const lr = data.logoRect;
  if (lr) {
    const rect = document.createElementNS(NS, "rect");
    rect.setAttribute("x", lr.x);
    rect.setAttribute("y", lr.y);
    rect.setAttribute("width", lr.w);
    rect.setAttribute("height", lr.h);
    rect.setAttribute("fill", lr.fill);
    svg.appendChild(rect);
  }
  boxEl.prepend(svg);

  stage.append(img, dimT, dimB, dimL, dimR, boxEl);
  root.appendChild(stage);


  let box = null;
  let W = 0;
  let H = 0;
  const measure = () => { W = img.clientWidth; H = img.clientHeight; };

  let fcw = 0;
  let fch = 0;
  function updateFrame() {
    let cw, ch;
    if (data.canvas) {
      [cw, ch] = data.canvas;
    } else {
      const a = (box.w * W) / (box.h * H);
      if (a >= 1) { ch = BASE; cw = BASE * a; }
      else { cw = BASE; ch = BASE / a; }
    }
    if (cw === fcw && ch === fch) return;
    fcw = cw;
    fch = ch;
    const m = frame.margin;
    const yStub = m + frame.stub;
    const yGap = yStub + frame.gap;
    svg.setAttribute("viewBox", `0 0 ${cw} ${ch}`);
    poly.setAttribute(
      "points",
      [[m, yStub], [m, m], [cw - m, m], [cw - m, ch - m], [m, ch - m], [m, yGap]]
        .map((pt) => pt.join(","))
        .join(" ")
    );
  }

  function render() {
    const x = box.x * W, y = box.y * H, w = box.w * W, h = box.h * H;
    place(boxEl, x, y, w, h);
    place(dimT, 0, 0, W, y);
    place(dimB, 0, y + h, W, H - y - h);
    place(dimL, 0, y, x, h);
    place(dimR, x + w, y, W - x - w, h);
    updateFrame();
  }

  function emit() {
    setStateValue("box", { x: box.x, y: box.y, w: box.w, h: box.h });
  }

  function initBox() {
    measure();
    let w = 0.9 * W;
    let h = 0.9 * H;
    if (ratio) {
      if (W / H > ratio) { h = 0.9 * H; w = h * ratio; }
      else { w = 0.9 * W; h = w / ratio; }
    }
    box = { x: (W - w) / 2 / W, y: (H - h) / 2 / H, w: w / W, h: h / H };
    render();
    emit();
  }

  let drag = null;
  let pending = null;
  let raf = 0;

  function apply() {
    raf = 0;
    if (!drag || !pending) return;
    const { cx, cy } = pending;
    const { b, handle } = drag;
    let nx, ny, nw, nh;

    if (!handle) {
      nw = b.w;
      nh = b.h;
      nx = clamp(b.x + cx - drag.startX, 0, W - nw);
      ny = clamp(b.y + cy - drag.startY, 0, H - nh);
    } else {

      const sx = handle.includes("e") ? 1 : -1;
      const sy = handle.includes("s") ? 1 : -1;
      const ax = sx > 0 ? b.x : b.x + b.w;
      const ay = sy > 0 ? b.y : b.y + b.h;
      const px = clamp(cx - drag.left, 0, W);
      const py = clamp(cy - drag.top, 0, H);
      const maxW = sx > 0 ? W - ax : ax;
      const maxH = sy > 0 ? H - ay : ay;

      if (ratio) {
        let w = Math.max(sx * (px - ax), sy * (py - ay) * ratio);
        w = Math.min(Math.max(w, MIN_PX), maxW, maxH * ratio);
        nw = w;
        nh = w / ratio;
      } else {
        nw = Math.min(Math.max(sx * (px - ax), MIN_PX), maxW);
        nh = Math.min(Math.max(sy * (py - ay), MIN_PX), maxH);
      }
      nx = sx > 0 ? ax : ax - nw;
      ny = sy > 0 ? ay : ay - nh;
    }

    box = { x: nx / W, y: ny / H, w: nw / W, h: nh / H };
    render();
  }

  boxEl.addEventListener("pointerdown", (e) => {
    measure();
    const rect = stage.getBoundingClientRect();
    drag = {
      handle: e.target.dataset.h || null,
      startX: e.clientX,
      startY: e.clientY,
      left: rect.left,
      top: rect.top,
      b: { x: box.x * W, y: box.y * H, w: box.w * W, h: box.h * H },
    };
    boxEl.setPointerCapture(e.pointerId);
    e.preventDefault();
  });


  boxEl.addEventListener("pointermove", (e) => {
    if (!drag) return;
    pending = { cx: e.clientX, cy: e.clientY };
    if (!raf) raf = requestAnimationFrame(apply);
  });

  const end = () => {
    if (!drag) return;
    if (raf) { cancelAnimationFrame(raf); apply(); }
    drag = null;
    pending = null;
    emit();
  };
  boxEl.addEventListener("pointerup", end);
  boxEl.addEventListener("pointercancel", end);

  img.addEventListener("load", () => {
    initBox();
    S.ro = new ResizeObserver(() => {
      if (!box || drag) return;
      measure();
      render();
    });
    S.ro.observe(img);
  });
  img.src = data.src;
}