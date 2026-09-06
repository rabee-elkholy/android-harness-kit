"""Generative UI & Visual Artifact Renderer for Android Agent Harness.

Supports high-fidelity interactive Tailwind HTML widgets when running under
Google Antigravity (<agent-embed>), with automatic zero-loss Markdown fallback
for OpenAI Codex, Claude Code, Cursor, and headless CLI environments.
"""
from __future__ import annotations

import html
import json
import os
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
from _environment import (  # noqa: E402
    detect_runtime_profile,
    is_antigravity,
    supports_generative_ui,
)


def _get_artifact_dir() -> Path:
    """Find the active artifact directory for Antigravity or local fallback."""
    # 1. Antigravity artifact directory in environment
    env_art = os.environ.get("ANTIGRAVITY_ARTIFACT_DIR")
    if env_art and Path(env_art).is_dir():
        return Path(env_art).resolve()

    # 2. Look for .gemini/antigravity/brain/<conv_id>
    conv_id = os.environ.get("ANTIGRAVITY_CONVERSATION_ID")
    if conv_id:
        user_home = Path.home()
        brain_path = user_home / ".gemini" / "antigravity" / "brain" / conv_id
        if brain_path.is_dir():
            return brain_path

    # 3. Local repo cache fallback
    repo_cache = SCRIPTS_DIR.parent.parent / ".agents" / "cache"
    if not repo_cache.is_dir():
        repo_cache = SCRIPTS_DIR.parent / "cache"
    repo_cache.mkdir(parents=True, exist_ok=True)
    return repo_cache


def build_review_card_html(
    round_num: int,
    pkg_hash: str,
    leaves: dict[str, dict[str, Any]],
    adjudication: dict[str, Any] | None = None,
    preflight_ok: bool | None = None,
) -> str:
    """Generate self-contained Tailwind HTML widget for the 5-leaf review round."""
    rows_html = []
    for leaf_name, leaf_data in sorted(leaves.items()):
        status = str(leaf_data.get("status") or "UNKNOWN").upper()
        is_pass = "PASS" in status
        badge_bg = "bg-emerald-500/10 text-emerald-600 border-emerald-500/20" if is_pass else "bg-amber-500/10 text-amber-600 border-amber-500/20"
        status_text = "PASS" if is_pass else "FINDINGS"
        findings = leaf_data.get("findings", [])
        
        display_name = leaf_name.replace("-agent", "").replace("-", " ").title()
        
        findings_html = ""
        if findings:
            items = "".join(f"<li class='text-xs text-[var(--foreground)] mt-1 font-mono leading-relaxed bg-[var(--background)]/50 p-2 rounded border border-[var(--border)]/50'>{html.escape(str(f)[:300])}</li>" for f in findings[:5])
            findings_html = f"""
            <details class="mt-2 text-xs text-[var(--muted-foreground)] group">
                <summary class="cursor-pointer hover:text-[var(--foreground)] font-medium select-none flex items-center gap-1">
                    <span class="inline-block transition-transform group-open:rotate-90">▸</span> {len(findings)} Finding(s) Reported
                </summary>
                <ul class="list-none space-y-1.5 mt-2 pl-2 border-l-2 border-[var(--border)]">
                    {items}
                </ul>
            </details>
            """
            
        row = f"""
        <div class="flex flex-col p-3 rounded-lg border border-[var(--border)] bg-[var(--card)] hover:border-[var(--border)]/80 transition-colors">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-2">
                    <span class="font-medium text-sm text-[var(--foreground)]">{display_name}</span>
                </div>
                <span class="px-2.5 py-0.5 rounded-full text-xs font-semibold border {badge_bg}">{status_text}</span>
            </div>
            {findings_html}
        </div>
        """
        rows_html.append(row)

    adjudication_html = ""
    if adjudication and adjudication.get("conflicts"):
        conflicts = adjudication.get("conflicts", [])
        conflict_items = "".join(f"<li class='text-xs mt-1'>{html.escape(str(c))}</li>" for c in conflicts)
        adjudication_html = f"""
        <div class="p-3 mt-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-600 text-xs">
            <span class="font-semibold">Reviewer Conflicts Adjudicated:</span>
            <ul class="list-disc list-inside mt-1">{conflict_items}</ul>
        </div>
        """

    preflight_badge = ""
    if preflight_ok is not None:
        pf_bg = "bg-emerald-500/10 text-emerald-600 border-emerald-500/20" if preflight_ok else "bg-amber-500/10 text-amber-600 border-amber-500/20"
        pf_text = "PASSED (0 errors)" if preflight_ok else "PENDING / REQUIRED"
        preflight_badge = f"""
        <div class="flex items-center justify-between text-xs py-2 px-3 mt-3 rounded bg-[var(--background)]/60 border border-[var(--border)]">
            <span class="text-[var(--muted-foreground)]">Preflight Verification Gate:</span>
            <span class="font-semibold px-2 py-0.5 rounded border {pf_bg}">{pf_text}</span>
        </div>
        """

    content = "\n".join(rows_html)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
</head>
<body class="bg-transparent text-[var(--foreground)] antialiased p-3 font-sans">
    <div class="bg-[var(--card)] text-[var(--foreground)] border border-[var(--border)] rounded-xl p-4 shadow-sm max-w-xl mx-auto">
        <div class="flex items-center justify-between border-b border-[var(--border)] pb-3 mb-3">
            <div>
                <h3 class="font-semibold text-base text-[var(--foreground)] flex items-center gap-2">
                    <span>5-Leaf Review Round {round_num}</span>
                </h3>
                <p class="text-xs text-[var(--muted-foreground)] mt-0.5">Package SHA-256: <code class="font-mono">{pkg_hash[:12]}</code></p>
            </div>
            <span class="text-xs font-mono px-2 py-1 rounded bg-[var(--background)] border border-[var(--border)] text-[var(--muted-foreground)]">Round {round_num}/3</span>
        </div>

        <div class="space-y-2.5">
            {content}
        </div>

        {adjudication_html}
        {preflight_badge}
    </div>
</body>
</html>
"""


def build_review_card_markdown(
    round_num: int,
    pkg_hash: str,
    leaves: dict[str, dict[str, Any]],
    adjudication: dict[str, Any] | None = None,
    preflight_ok: bool | None = None,
) -> str:
    """Generate high-signal Markdown summary card for non-GUI environments."""
    lines = [
        f"### Review Round {round_num} Summary",
        f"**Package:** `{pkg_hash[:12]}` | **Round:** {round_num}/3\n",
        "| Reviewer Leaf | Status | Findings / Notes |",
        "| :--- | :---: | :--- |",
    ]
    for leaf_name, leaf_data in sorted(leaves.items()):
        status = str(leaf_data.get("status") or "UNKNOWN").upper()
        is_pass = "PASS" in status
        icon = "[PASS]" if is_pass else "[FINDINGS]"
        findings = leaf_data.get("findings", [])
        display_name = leaf_name.replace("-agent", "").replace("-", " ").title()
        note = f"{len(findings)} finding(s) reported" if findings else "Clean sign-off"
        lines.append(f"| **{display_name}** | {icon} | {note} |")

    if preflight_ok is not None:
        pf_text = "[OK] Passed (0 errors)" if preflight_ok else "[PENDING] Required before assemble"
        lines.append(f"\n**Preflight Gate:** {pf_text}")

    if adjudication and adjudication.get("conflicts"):
        lines.append(f"\n> **Adjudicated Conflicts:** {len(adjudication['conflicts'])} conflict(s) resolved.")

    return "\n".join(lines)


def render_review_summary(
    round_num: int,
    pkg_hash: str,
    leaves: dict[str, dict[str, Any]],
    adjudication: dict[str, Any] | None = None,
    preflight_ok: bool | None = None,
) -> str:
    """Render review summary either as Antigravity <agent-embed> or Markdown."""
    if supports_generative_ui():
        art_dir = _get_artifact_dir()
        file_name = f"review_round_{round_num}_{pkg_hash[:8]}.html"
        html_path = art_dir / file_name
        try:
            html_content = build_review_card_html(
                round_num, pkg_hash, leaves, adjudication, preflight_ok
            )
            html_path.write_text(html_content, encoding="utf-8")
            uri = html_path.resolve().as_uri()
            return f'<agent-embed src="{uri}"></agent-embed>'
        except Exception:
            pass  # Fallback to markdown if write fails

    return build_review_card_markdown(round_num, pkg_hash, leaves, adjudication, preflight_ok)


def build_graph_viewer_html(graph_data: dict, title: str, stats: dict | None = None) -> str:
    """Builds a self-contained interactive HTML graph viewer using Tailwind and Canvas."""
    graph_json = json.dumps(graph_data, ensure_ascii=False)
    
    total_nodes = stats.get("total_nodes", len(graph_data.get("nodes", []))) if stats else len(graph_data.get("nodes", []))
    total_edges = stats.get("total_edges", len(graph_data.get("edges", []))) if stats else len(graph_data.get("edges", []))
    
    html_str = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
    <style>
        :root {{
            --background: #0f172a;
            --foreground: #f8fafc;
            --card: #1e293b;
            --muted-foreground: #94a3b8;
            --border: #334155;
            --primary: #3b82f6;
            --accent: #8b5cf6;
        }}
        @media (prefers-color-scheme: light) {{
            :root {{
                --background: #ffffff;
                --foreground: #0f172a;
                --card: #f8fafc;
                --muted-foreground: #64748b;
                --border: #e2e8f0;
            }}
        }}
        body {{ margin: 0; overflow: hidden; }}
        #canvas-container {{ position: relative; width: 100vw; height: 100vh; cursor: grab; }}
        #canvas-container:active {{ cursor: grabbing; }}
        canvas {{ display: block; }}
        #tooltip {{
            position: absolute;
            display: none;
            pointer-events: none;
            background: var(--card);
            color: var(--foreground);
            border: 1px solid var(--border);
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 12px;
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
            z-index: 50;
            max-width: 300px;
            word-wrap: break-word;
        }}
    </style>
</head>
<body class="bg-[var(--background)] text-[var(--foreground)] antialiased">
    <div class="absolute top-0 left-0 w-full p-4 pointer-events-none z-10 flex justify-between items-start">
        <div class="pointer-events-auto bg-[var(--card)]/90 backdrop-blur border border-[var(--border)] rounded-lg p-4 shadow-lg w-80">
            <h1 class="font-bold text-lg mb-1">{html.escape(title)}</h1>
            <p class="text-xs text-[var(--muted-foreground)] mb-4">{total_nodes} nodes, {total_edges} edges</p>
            
            <div class="mb-4">
                <input type="text" id="search-input" placeholder="Search nodes..." class="w-full bg-[var(--background)] border border-[var(--border)] rounded px-3 py-1.5 text-sm outline-none focus:border-[var(--primary)] text-[var(--foreground)]">
            </div>
            
            <div class="text-sm font-semibold mb-2">Layers</div>
            <div id="layer-filters" class="space-y-1.5 max-h-60 overflow-y-auto text-xs">
                <!-- checkboxes injected via JS -->
            </div>
            
            <div class="mt-4 text-xs text-[var(--muted-foreground)] border-t border-[var(--border)] pt-3">
                <p>Scroll to zoom &bull; Drag to pan &bull; Click node to select</p>
            </div>
        </div>
    </div>
    
    <div id="canvas-container">
        <canvas id="graph-canvas"></canvas>
        <div id="tooltip"></div>
    </div>

    <script>
        const GRAPH_DATA = {graph_json};
        
        // Colors mapping
        const COLORS = {{
            MODULE: '#0288D1',
            SCREEN: '#388E3C',
            VIEW_MODEL: '#F57C00',
            USE_CASE: '#512DA8',
            REPOSITORY: '#C2185B',
            DATA_SOURCE: '#5D4037',
            TEST: '#7B1FA2',
            XML_LAYOUT: '#AFB42B',
            NAV_GRAPH: '#00796B',
            COMPONENT: '#607D8B',
            HARNESS_TOOL: '#455A64',
            UNKNOWN: '#9E9E9E'
        }};
        
        const canvas = document.getElementById('graph-canvas');
        const ctx = canvas.getContext('2d');
        const container = document.getElementById('canvas-container');
        const tooltip = document.getElementById('tooltip');
        const searchInput = document.getElementById('search-input');
        const layerFilters = document.getElementById('layer-filters');
        
        // State
        let nodes = [];
        let edges = [];
        let nodeMap = new Map();
        let adjList = new Map();
        
        let transform = {{ x: 0, y: 0, k: 1 }};
        let isDragging = false;
        let dragStart = {{ x: 0, y: 0 }};
        let draggedNode = null;
        let hoveredNode = null;
        let selectedNode = null;
        let searchQuery = '';
        let visibleTypes = new Set();
        
        // Large graph optimization
        const isLargeGraph = (GRAPH_DATA.nodes && GRAPH_DATA.nodes.length > 500) || (GRAPH_DATA.graph && GRAPH_DATA.graph.nodes && GRAPH_DATA.graph.nodes.length > 500);
        const defaultVisibleTypes = new Set(['SCREEN', 'VIEW_MODEL', 'USE_CASE', 'REPOSITORY', 'DATA_SOURCE', 'NAV_GRAPH', 'MODULE']);
        
        function resize() {{
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            draw();
        }}
        window.addEventListener('resize', resize);
        
        function initGraph() {{
            // Handle both {{"nodes": [], "edges": []}} and {{"graph": {{"nodes": [], "edges": []}}}}
            const dataNodes = GRAPH_DATA.nodes || (GRAPH_DATA.graph && GRAPH_DATA.graph.nodes) || [];
            const dataEdges = GRAPH_DATA.edges || (GRAPH_DATA.graph && GRAPH_DATA.graph.edges) || [];
            
            // Collect types
            const types = new Set();
            dataNodes.forEach(n => {{
                types.add(n.type || 'UNKNOWN');
            }});
            
            // Initialize filters
            Array.from(types).sort().forEach(type => {{
                if (isLargeGraph && !defaultVisibleTypes.has(type)) {{
                    // Skip initially if large
                }} else {{
                    visibleTypes.add(type);
                }}
                
                const div = document.createElement('div');
                div.className = 'flex items-center gap-2';
                
                const color = COLORS[type] || COLORS.UNKNOWN;
                
                div.innerHTML = `
                    <input type="checkbox" id="filter-${{type}}" value="${{type}}" ${{visibleTypes.has(type) ? 'checked' : ''}} class="rounded bg-transparent border-[var(--border)]">
                    <span class="w-3 h-3 rounded-full inline-block" style="background-color: ${{color}}"></span>
                    <label for="filter-${{type}}" class="cursor-pointer flex-1 truncate">${{type}}</label>
                `;
                
                div.querySelector('input').addEventListener('change', (e) => {{
                    if (e.target.checked) visibleTypes.add(type);
                    else visibleTypes.delete(type);
                    draw();
                }});
                
                layerFilters.appendChild(div);
            }});
            
            // Init nodes
            const width = window.innerWidth;
            const height = window.innerHeight;
            
            dataNodes.forEach(n => {{
                // Group by type roughly for initial position
                const angle = Math.random() * Math.PI * 2;
                const radius = Math.random() * (Math.min(width, height) / 2 - 50);
                
                const node = {{
                    ...n,
                    x: width / 2 + Math.cos(angle) * radius,
                    y: height / 2 + Math.sin(angle) * radius,
                    vx: 0,
                    vy: 0,
                    radius: n.type === 'MODULE' ? 12 : 8
                }};
                nodes.push(node);
                nodeMap.set(n.id, node);
                adjList.set(n.id, []);
            }});
            
            dataEdges.forEach(e => {{
                if (nodeMap.has(e.source) && nodeMap.has(e.target)) {{
                    edges.push({{
                        source: nodeMap.get(e.source),
                        target: nodeMap.get(e.target),
                        kind: e.kind
                    }});
                    adjList.get(e.source).push(e.target);
                    adjList.get(e.target).push(e.source);
                }}
            }});
            
            // Start simulation
            requestAnimationFrame(simulate);
            
            // Center
            transform.x = 0;
            transform.y = 0;
            if (nodes.length > 0) {{
                // Zoom out slightly for large graphs
                transform.k = Math.min(1, Math.max(0.1, 100 / Math.sqrt(nodes.length)));
                transform.x = width/2 * (1 - transform.k);
                transform.y = height/2 * (1 - transform.k);
            }}
        }}
        
        let alpha = 1;
        function simulate() {{
            if (alpha < 0.01) return;
            alpha *= 0.95; // decay
            
            const k = 0.5 * alpha;
            const repulsion = 100 * alpha;
            
            // Edges (springs)
            edges.forEach(e => {{
                // Only apply force if both visible
                if (!visibleTypes.has(e.source.type) || !visibleTypes.has(e.target.type)) return;
                
                const dx = e.target.x - e.source.x;
                const dy = e.target.y - e.source.y;
                const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                
                // Ideal distance
                const ideal = 50;
                const force = (dist - ideal) * k;
                
                const fx = (dx / dist) * force;
                const fy = (dy / dist) * force;
                
                if (e.source !== draggedNode) {{
                    e.source.vx += fx;
                    e.source.vy += fy;
                }}
                if (e.target !== draggedNode) {{
                    e.target.vx -= fx;
                    e.target.vy -= fy;
                }}
            }});
            
            // Repulsion
            for (let i = 0; i < nodes.length; i++) {{
                const n1 = nodes[i];
                if (!visibleTypes.has(n1.type)) continue;
                
                for (let j = i + 1; j < nodes.length; j++) {{
                    const n2 = nodes[j];
                    if (!visibleTypes.has(n2.type)) continue;
                    
                    const dx = n2.x - n1.x;
                    const dy = n2.y - n1.y;
                    const distSq = dx*dx + dy*dy;
                    
                    if (distSq < 10000) {{
                        const dist = Math.sqrt(distSq) || 1;
                        const force = repulsion / distSq;
                        
                        const fx = (dx / dist) * force;
                        const fy = (dy / dist) * force;
                        
                        if (n1 !== draggedNode) {{
                            n1.vx -= fx;
                            n1.vy -= fy;
                        }}
                        if (n2 !== draggedNode) {{
                            n2.vx += fx;
                            n2.vy += fy;
                        }}
                    }}
                }}
            }}
            
            // Gravity to center
            const cx = window.innerWidth / 2;
            const cy = window.innerHeight / 2;
            const gravity = 0.01 * alpha;
            
            nodes.forEach(n => {{
                if (!visibleTypes.has(n.type)) return;
                
                if (n !== draggedNode) {{
                    n.vx += (cx - n.x) * gravity;
                    n.vy += (cy - n.y) * gravity;
                    
                    n.x += n.vx;
                    n.y += n.vy;
                    
                    // Friction
                    n.vx *= 0.8;
                    n.vy *= 0.8;
                }}
            }});
            
            draw();
            if (alpha > 0.01) {{
                requestAnimationFrame(simulate);
            }}
        }}
        
        function toWorld(scrX, scrY) {{
            return {{
                x: (scrX - transform.x) / transform.k,
                y: (scrY - transform.y) / transform.k
            }};
        }}
        
        function toScreen(worldX, worldY) {{
            return {{
                x: worldX * transform.k + transform.x,
                y: worldY * transform.k + transform.y
            }};
        }}
        
        function draw() {{
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            
            ctx.save();
            ctx.translate(transform.x, transform.y);
            ctx.scale(transform.k, transform.k);
            
            // Filter nodes and edges
            const vNodes = nodes.filter(n => visibleTypes.has(n.type));
            const vEdges = edges.filter(e => visibleTypes.has(e.source.type) && visibleTypes.has(e.target.type));
            
            // Culling for performance
            const screenW = canvas.width / transform.k;
            const screenH = canvas.height / transform.k;
            const minX = -transform.x / transform.k;
            const minY = -transform.y / transform.k;
            const maxX = minX + screenW;
            const maxY = minY + screenH;
            
            const margin = 100;
            
            // Find selected neighbors
            let highlightIds = new Set();
            if (selectedNode) {{
                highlightIds.add(selectedNode.id);
                (adjList.get(selectedNode.id) || []).forEach(id => highlightIds.add(id));
            }} else if (hoveredNode) {{
                highlightIds.add(hoveredNode.id);
                (adjList.get(hoveredNode.id) || []).forEach(id => highlightIds.add(id));
            }}
            
            const isHighlightMode = highlightIds.size > 0;
            
            // Draw Edges
            ctx.lineWidth = 1 / transform.k;
            vEdges.forEach(e => {{
                // Frustum culling roughly
                const inView = (
                    (e.source.x > minX-margin && e.source.x < maxX+margin && e.source.y > minY-margin && e.source.y < maxY+margin) ||
                    (e.target.x > minX-margin && e.target.x < maxX+margin && e.target.y > minY-margin && e.target.y < maxY+margin)
                );
                
                if (!inView) return;
                
                const isHighlighted = isHighlightMode && highlightIds.has(e.source.id) && highlightIds.has(e.target.id);
                const isDimmed = isHighlightMode && !isHighlighted;
                
                ctx.beginPath();
                ctx.moveTo(e.source.x, e.source.y);
                ctx.lineTo(e.target.x, e.target.y);
                
                if (isHighlighted) {{
                    ctx.strokeStyle = getComputedStyle(document.body).getPropertyValue('--foreground').trim();
                    ctx.globalAlpha = 0.8;
                    ctx.lineWidth = 2 / transform.k;
                }} else if (isDimmed) {{
                    ctx.strokeStyle = getComputedStyle(document.body).getPropertyValue('--muted-foreground').trim();
                    ctx.globalAlpha = 0.1;
                    ctx.lineWidth = 1 / transform.k;
                }} else {{
                    ctx.strokeStyle = getComputedStyle(document.body).getPropertyValue('--border').trim();
                    ctx.globalAlpha = 0.5;
                    ctx.lineWidth = 1 / transform.k;
                }}
                ctx.stroke();
            }});
            
            // Draw Nodes
            vNodes.forEach(n => {{
                const inView = (n.x > minX-margin && n.x < maxX+margin && n.y > minY-margin && n.y < maxY+margin);
                if (!inView) return;
                
                const isHighlighted = isHighlightMode && highlightIds.has(n.id);
                const isDimmed = isHighlightMode && !isHighlighted;
                const isMatch = searchQuery && n.name.toLowerCase().includes(searchQuery);
                
                ctx.beginPath();
                ctx.arc(n.x, n.y, n.radius, 0, 2 * Math.PI);
                
                ctx.fillStyle = COLORS[n.type] || COLORS.UNKNOWN;
                ctx.globalAlpha = isDimmed && !isMatch ? 0.2 : (isHighlightMode && !isHighlighted ? 0.4 : 1.0);
                
                if (isMatch) {{
                    ctx.lineWidth = 4 / transform.k;
                    ctx.strokeStyle = '#FFFF00';
                    ctx.stroke();
                }}
                
                if (n === hoveredNode || n === selectedNode) {{
                    ctx.lineWidth = 3 / transform.k;
                    ctx.strokeStyle = getComputedStyle(document.body).getPropertyValue('--foreground').trim();
                    ctx.stroke();
                }}
                
                ctx.fill();
                
                // Labels (draw if close enough or highlighted/matched)
                if (transform.k > 0.8 || isHighlighted || isMatch) {{
                    ctx.fillStyle = getComputedStyle(document.body).getPropertyValue('--foreground').trim();
                    ctx.font = `${{12 / transform.k}}px sans-serif`;
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'top';
                    ctx.fillText(n.name, n.x, n.y + n.radius + 2/transform.k);
                }}
            }});
            
            ctx.restore();
        }}
        
        // Interactions
        container.addEventListener('mousedown', e => {{
            const w = toWorld(e.clientX, e.clientY);
            
            // Find clicked node
            let clicked = null;
            for (let n of nodes) {{
                if (!visibleTypes.has(n.type)) continue;
                const dx = n.x - w.x;
                const dy = n.y - w.y;
                if (dx*dx + dy*dy < n.radius * n.radius * 2) {{
                    clicked = n;
                    break;
                }}
            }}
            
            if (clicked) {{
                draggedNode = clicked;
                selectedNode = clicked;
                alpha = 0.3; // reheat
                simulate();
            }} else {{
                selectedNode = null;
                isDragging = true;
                dragStart = {{ x: e.clientX, y: e.clientY }};
            }}
            draw();
        }});
        
        container.addEventListener('mousemove', e => {{
            if (draggedNode) {{
                const w = toWorld(e.clientX, e.clientY);
                draggedNode.x = w.x;
                draggedNode.y = w.y;
                alpha = 0.1;
                simulate();
                draw();
                return;
            }}
            
            if (isDragging) {{
                const dx = e.clientX - dragStart.x;
                const dy = e.clientY - dragStart.y;
                transform.x += dx;
                transform.y += dy;
                dragStart = {{ x: e.clientX, y: e.clientY }};
                draw();
                return;
            }}
            
            // Hover
            const w = toWorld(e.clientX, e.clientY);
            let hovered = null;
            for (let n of nodes) {{
                if (!visibleTypes.has(n.type)) continue;
                const dx = n.x - w.x;
                const dy = n.y - w.y;
                if (dx*dx + dy*dy < n.radius * n.radius * 2) {{
                    hovered = n;
                    break;
                }}
            }}
            
            if (hovered !== hoveredNode) {{
                hoveredNode = hovered;
                draw();
                
                if (hovered) {{
                    tooltip.style.display = 'block';
                    tooltip.style.left = (e.clientX + 15) + 'px';
                    tooltip.style.top = (e.clientY + 15) + 'px';
                    tooltip.innerHTML = `
                        <div class="font-bold">${{hovered.name}}</div>
                        <div class="text-[var(--muted-foreground)]">${{hovered.type}}</div>
                        ${{hovered.module ? `<div class="mt-1">Module: ${{hovered.module}}</div>` : ''}}
                        ${{hovered.package ? `<div>Package: ${{hovered.package}}</div>` : ''}}
                        <div class="mt-1 text-[9px] text-[var(--muted-foreground)] break-all">${{hovered.file_path || ''}}</div>
                    `;
                }} else {{
                    tooltip.style.display = 'none';
                }}
            }} else if (hovered) {{
                tooltip.style.left = (e.clientX + 15) + 'px';
                tooltip.style.top = (e.clientY + 15) + 'px';
            }}
        }});
        
        container.addEventListener('mouseup', () => {{
            isDragging = false;
            draggedNode = null;
        }});
        
        container.addEventListener('wheel', e => {{
            e.preventDefault();
            const w = toWorld(e.clientX, e.clientY);
            
            const zoom = e.deltaY > 0 ? 0.9 : 1.1;
            transform.k *= zoom;
            transform.k = Math.max(0.05, Math.min(5, transform.k));
            
            // Adjust translation to zoom towards mouse
            transform.x = e.clientX - w.x * transform.k;
            transform.y = e.clientY - w.y * transform.k;
            
            draw();
        }});
        
        searchInput.addEventListener('input', e => {{
            searchQuery = e.target.value.toLowerCase();
            draw();
        }});
        
        resize();
        initGraph();
    </script>
</body>
</html>"""
    return html_str


def render_graph_viewer(
    graph_data: dict, title: str, stats: dict | None = None, output_path: Path | None = None
) -> str:
    """Render graph viewer as Antigravity <agent-embed> or standalone file."""
    html_content = build_graph_viewer_html(graph_data, title, stats)
    
    if output_path:
        out_file = output_path.resolve()
    else:
        art_dir = _get_artifact_dir()
        out_file = art_dir / "graph_viewer.html"
        
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(html_content, encoding="utf-8")
    
    if supports_generative_ui():
        return out_file.resolve().as_uri()
    
    return str(out_file)


def main() -> None:
    """CLI tool for testing or manual invocations."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if len(sys.argv) > 1 and sys.argv[1] == "--demo":
        sample_leaves = {
            "bug-reviewer-agent": {"status": "BUG_PASS", "findings": []},
            "convention-reviewer-agent": {
                "status": "CONVENTION_PASS",
                "findings": ["CleanArchitecture: ViewModel directly exposes MutableStateFlow"],
            },
            "security-reviewer-agent": {"status": "SECURITY_PASS", "findings": []},
            "perf-anr-guardian-agent": {"status": "PERF_PASS", "findings": []},
            "regression-impact-reviewer-agent": {"status": "REGRESSION_PASS", "findings": []},
        }
        res = render_review_summary(1, "a1b2c3d4e5f6", sample_leaves, preflight_ok=True)
        print(res)
    elif len(sys.argv) > 1 and sys.argv[1] == "--graph":
        repo_cache = SCRIPTS_DIR.parent.parent / ".agents" / "cache"
        if not repo_cache.is_dir():
            repo_cache = SCRIPTS_DIR.parent / "cache"
        graph_json_path = repo_cache / "project_graph.json"
        if graph_json_path.exists():
            data = json.loads(graph_json_path.read_text(encoding="utf-8"))
            print(render_graph_viewer(data, "Project Graph"))
        else:
            print("No project_graph.json found. Run project_graph.py --sync first.")
    else:
        print("Usage: python render_ui.py --demo | --graph")


if __name__ == "__main__":
    main()
