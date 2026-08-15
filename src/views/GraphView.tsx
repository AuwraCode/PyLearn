import { useEffect, useRef, useState } from "react";
import type { ApiClient } from "../lib/api";
import { ApiError } from "../lib/api";
import type { GraphNode } from "../types/api";

const COLOR = {
  learning: "#e5b95c",
  known: "#85c88a",
  contentNew: "#98a1b0",
  placeholder: "#5c6472",
  edge: "#262d38",
  edgeHover: "rgba(229, 185, 92, 0.5)",
  label: "#98a1b0",
  labelHover: "#e8e6e1",
  ink: "#0e1116",
};

interface SimNode extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
}

interface GraphViewProps {
  api: ApiClient;
  onOpenConcept: (id: number) => void;
  onAsk: (question: string) => void;
}

/** Prosty force-directed na canvasie: odpychanie wszystkich par, sprężyny na
 * krawędziach, grawitacja do środka, chłodzenie. Bez zależności zewnętrznych. */
export function GraphView({ api, onOpenConcept, onAsk }: GraphViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [state, setState] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let disposed = false;
    let raf = 0;
    let cooling = 1;
    const nodes: SimNode[] = [];
    let edges: Array<{ a: SimNode; b: SimNode }> = [];
    const hover = { node: null as SimNode | null };

    api
      .graph()
      .then((graph) => {
        if (disposed) return;
        if (graph.nodes.length === 0) {
          setState("empty");
          return;
        }
        setState("ready");
        const byId = new Map<number, SimNode>();
        graph.nodes.forEach((node, index) => {
          const angle = index * 2.39996; // złoty kąt — równomierny rozrzut startowy
          const radius = 40 + 14 * Math.sqrt(index);
          const sim: SimNode = {
            ...node,
            x: Math.cos(angle) * radius,
            y: Math.sin(angle) * radius,
            vx: 0,
            vy: 0,
            r: 4 + Math.min(7, Math.sqrt(node.degree + 1) * 1.8),
          };
          nodes.push(sim);
          byId.set(node.id, sim);
        });
        edges = graph.edges.flatMap((edge) => {
          const a = byId.get(edge.from_id);
          const b = byId.get(edge.to_id);
          return a && b ? [{ a, b }] : [];
        });
        loop();
      })
      .catch((err: unknown) => {
        if (disposed) return;
        setError(err instanceof ApiError ? err.message : "Nie udało się wczytać grafu");
        setState("error");
      });

    function step() {
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i];
          const b = nodes[j];
          let dx = a.x - b.x;
          let dy = a.y - b.y;
          let d2 = dx * dx + dy * dy;
          if (d2 < 1) {
            dx = Math.random() - 0.5;
            dy = Math.random() - 0.5;
            d2 = 1;
          }
          const d = Math.sqrt(d2);
          const force = Math.min(1400 / d2, 6);
          a.vx += (dx / d) * force;
          a.vy += (dy / d) * force;
          b.vx -= (dx / d) * force;
          b.vy -= (dy / d) * force;
        }
      }
      for (const { a, b } of edges) {
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const d = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
        const force = (d - 95) * 0.02;
        a.vx += (dx / d) * force;
        a.vy += (dy / d) * force;
        b.vx -= (dx / d) * force;
        b.vy -= (dy / d) * force;
      }
      for (const node of nodes) {
        node.vx -= node.x * 0.006;
        node.vy -= node.y * 0.006;
        node.vx *= 0.85;
        node.vy *= 0.85;
        node.x += node.vx * cooling;
        node.y += node.vy * cooling;
      }
      cooling = Math.max(0, cooling - 0.002);
    }

    function draw() {
      const canvas = canvasRef.current;
      const container = containerRef.current;
      if (!canvas || !container) return;
      const width = container.clientWidth;
      const height = container.clientHeight;
      const dpr = window.devicePixelRatio || 1;
      if (canvas.width !== width * dpr || canvas.height !== height * dpr) {
        canvas.width = width * dpr;
        canvas.height = height * dpr;
        canvas.style.width = `${width}px`;
        canvas.style.height = `${height}px`;
      }
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, height);
      ctx.translate(width / 2, height / 2);

      const active = hover.node;
      for (const { a, b } of edges) {
        const highlighted = active !== null && (a === active || b === active);
        ctx.strokeStyle = highlighted ? COLOR.edgeHover : COLOR.edge;
        ctx.lineWidth = highlighted ? 1.5 : 1;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }

      const showAllLabels = nodes.length <= 80;
      for (const node of nodes) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, node.r, 0, Math.PI * 2);
        if (!node.has_content) {
          // biała plama: pusty okrąg
          ctx.fillStyle = COLOR.ink;
          ctx.fill();
          ctx.strokeStyle = COLOR.placeholder;
          ctx.lineWidth = 1.5;
          ctx.stroke();
        } else {
          ctx.fillStyle =
            node.status === "learning"
              ? COLOR.learning
              : node.status === "known"
                ? COLOR.known
                : COLOR.contentNew;
          ctx.fill();
        }
        if (node === active) {
          ctx.beginPath();
          ctx.arc(node.x, node.y, node.r + 3.5, 0, Math.PI * 2);
          ctx.strokeStyle = COLOR.labelHover;
          ctx.lineWidth = 1;
          ctx.stroke();
        }
        if (showAllLabels || node === active) {
          ctx.font = "10px ui-monospace, Menlo, monospace";
          ctx.textAlign = "center";
          ctx.fillStyle = node === active ? COLOR.labelHover : COLOR.label;
          ctx.fillText(node.name, node.x, node.y + node.r + 12);
        }
      }
    }

    function loop() {
      if (disposed) return;
      if (cooling > 0) step();
      draw();
      raf = requestAnimationFrame(loop);
    }

    const canvas = canvasRef.current;

    const hitTest = (event: MouseEvent): SimNode | null => {
      const container = containerRef.current;
      if (!container) return null;
      const rect = container.getBoundingClientRect();
      const x = event.clientX - rect.left - rect.width / 2;
      const y = event.clientY - rect.top - rect.height / 2;
      let best: SimNode | null = null;
      let bestDist = Infinity;
      for (const node of nodes) {
        const dx = node.x - x;
        const dy = node.y - y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < node.r + 6 && dist < bestDist) {
          best = node;
          bestDist = dist;
        }
      }
      return best;
    };

    const onMove = (event: MouseEvent) => {
      hover.node = hitTest(event);
      if (canvas) canvas.style.cursor = hover.node ? "pointer" : "default";
    };
    const onClick = (event: MouseEvent) => {
      const node = hitTest(event);
      if (!node) return;
      if (node.has_content) onOpenConcept(node.id);
      else onAsk(node.name);
    };
    canvas?.addEventListener("mousemove", onMove);
    canvas?.addEventListener("click", onClick);

    return () => {
      disposed = true;
      cancelAnimationFrame(raf);
      canvas?.removeEventListener("mousemove", onMove);
      canvas?.removeEventListener("click", onClick);
    };
  }, [api, onOpenConcept, onAsk]);

  return (
    <div ref={containerRef} className="relative h-full overflow-hidden">
      <canvas ref={canvasRef} className="block h-full w-full" />

      {state === "loading" && (
        <p className="absolute inset-0 flex items-center justify-center text-sm text-muted">
          Buduję graf…
        </p>
      )}
      {state === "empty" && (
        <p className="absolute inset-0 flex items-center justify-center text-sm text-muted">
          Graf jest pusty — zadaj pierwsze pytanie w widoku Pytaj.
        </p>
      )}
      {state === "error" && (
        <p className="absolute inset-0 flex items-center justify-center text-sm text-err">
          {error}
        </p>
      )}

      {state === "ready" && (
        <div className="pointer-events-none absolute bottom-4 left-4 space-y-1 text-xs text-muted">
          <p className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-amber" aria-hidden /> w nauce
          </p>
          <p className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-ok" aria-hidden /> znane
          </p>
          <p className="flex items-center gap-2">
            <span
              className="h-2.5 w-2.5 rounded-full border border-muted bg-transparent"
              aria-hidden
            />
            biała plama — klik zadaje pytanie
          </p>
        </div>
      )}
    </div>
  );
}
