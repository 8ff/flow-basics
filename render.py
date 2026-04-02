#!/usr/bin/env python3
"""
Reads a clean .dot file, applies dark theme styling, renders SVG and/or PNG.
Usage: python3 render.py [input.dot] [output_base]

output_base defaults to the input name without extension.
Produces both .svg and .png unless output_base ends with .svg or .png.
"""

import re
import subprocess
import sys
import os

INPUT = sys.argv[1] if len(sys.argv) > 1 else "example.dot"
OUTPUT_ARG = sys.argv[2] if len(sys.argv) > 2 else None

# ── Theme colors ──
BG = "#0d1117"
FG = "#c9d1d9"
MUTED = "#484f58"
BORDER = "#30363d"
NODE_BG = "#161b22"

BLUE = "#58a6ff"
BLUE_DK = "#0d1f3c"
BLUE_BRIGHT = "#1f6feb"
GREEN = "#3fb950"
GREEN_DK = "#0d2818"
YELLOW = "#d29922"
YELLOW_DK = "#2d1d00"
RED = "#f85149"
RED_DK = "#3d1115"
PURPLE = "#a371f7"
PURPLE_DK = "#1c0d36"
GREY = "#58606a"

CYAN = "#39d4e0"
CYAN_DK = "#0a2a2e"
ORANGE = "#e09039"
ORANGE_DK = "#2e1d0a"

FONT = "Helvetica Neue,Helvetica,Arial,sans-serif"

# ── Color palette — clusters auto-pick from this in order ──
COLOR_PALETTE = [
    {"color": BLUE_BRIGHT, "fontcolor": BLUE,   "node_bg": BLUE_DK,   "node_fg": BLUE},
    {"color": YELLOW,      "fontcolor": YELLOW,  "node_bg": YELLOW_DK, "node_fg": YELLOW},
    {"color": GREEN,       "fontcolor": GREEN,   "node_bg": GREEN_DK,  "node_fg": GREEN},
    {"color": RED,         "fontcolor": RED,     "node_bg": RED_DK,    "node_fg": RED},
    {"color": PURPLE,      "fontcolor": PURPLE,  "node_bg": PURPLE_DK, "node_fg": PURPLE},
    {"color": CYAN,        "fontcolor": CYAN,    "node_bg": CYAN_DK,   "node_fg": CYAN},
    {"color": ORANGE,      "fontcolor": ORANGE,  "node_bg": ORANGE_DK, "node_fg": ORANGE},
]

# ── Optional overrides — map specific cluster names to palette entries ──
# If a cluster isn't here, it auto-picks the next color from COLOR_PALETTE.
CLUSTER_OVERRIDES = {}

# Runtime: filled by pre-scan
_cluster_colors = {}  # cluster_name -> palette entry
_palette_idx = 0

# ── Node class → style mapping ──
NODE_CLASSES = {
    "start":    f'fillcolor="{BLUE_BRIGHT}" fontcolor="#ffffff" penwidth=0',
    "decision": f'fillcolor="#1c2028"',
    "drop":     f'fillcolor="{RED_DK}" color="{RED}" fontcolor="{RED}"',
    "fail":     f'fillcolor="{RED}" fontcolor="#ffffff" penwidth=0',
    "success":  f'fillcolor="{GREEN_DK}" color="{GREEN}" fontcolor="{GREEN}"',
    "warn":     f'fillcolor="{YELLOW_DK}" color="{YELLOW}" fontcolor="{YELLOW}"',
    "info":     f'fillcolor="{BLUE_DK}" color="{BLUE}" fontcolor="{BLUE}"',
    "muted":    f'fillcolor="#1c2028" color="{MUTED}" fontcolor="{MUTED}"',
}

# ── Edge class → style mapping ──
EDGE_CLASSES = {
    "yes":        f'color="{GREEN}" fontcolor="{GREEN}"',
    "no":         f'color="{RED}" fontcolor="{RED}"',
    "major":      f'penwidth=2.5 color="{GREEN}"',
    "major_yes":  f'penwidth=2.5 color="{GREEN}" fontcolor="{GREEN}"',
    "major_no":   f'penwidth=2.5 color="{RED}" fontcolor="{RED}"',
    "loop":       f'style=dashed color="{GREY}" constraint=false arrowsize=0.5 fontsize=9 fontcolor="{GREY}"',
    "timeout":    f'penwidth=2.5 color="{RED}" fontcolor="{RED}"',
    "retry":      f'style=dashed color="{YELLOW}" fontcolor="{YELLOW}" penwidth=1.8 arrowsize=0.6',
    "retry_back": f'style=dashed color="{YELLOW}" fontcolor="{YELLOW}"',
    "yes_loop":   f'color="{GREEN}" fontcolor="{GREEN}" style=dashed',
    "fail_loop":  f'style=dashed color="{RED}" fontcolor="{RED}" penwidth=1.8 arrowsize=0.6',
    "skip":       f'style=dotted color="{MUTED}" fontcolor="{MUTED}"',
    "async":      f'style=dashed color="{PURPLE}" fontcolor="{PURPLE}"',
    "optional":   f'style=dotted color="{YELLOW}" fontcolor="{YELLOW}"',
}

def detect_cluster(line):
    """Detect which cluster context we're in based on subgraph lines."""
    m = re.match(r'\s*subgraph\s+(cluster_\w+)', line)
    return m.group(1) if m else None


def assign_cluster_colors(src):
    """Pre-scan the dot source and assign palette colors to each cluster."""
    global _palette_idx
    for line in src.split('\n'):
        m = re.match(r'\s*subgraph\s+(cluster_\w+)', line)
        if m:
            name = m.group(1)
            if name not in _cluster_colors:
                if name in CLUSTER_OVERRIDES:
                    _cluster_colors[name] = CLUSTER_OVERRIDES[name]
                else:
                    _cluster_colors[name] = COLOR_PALETTE[_palette_idx % len(COLOR_PALETTE)]
                    _palette_idx += 1


def get_cluster_theme(cluster):
    """Get the color theme for a cluster."""
    return _cluster_colors.get(cluster, COLOR_PALETTE[0])


def get_default_node_style(cluster):
    """Return default node fill/color based on cluster context."""
    theme = get_cluster_theme(cluster)
    return f'fillcolor="{theme["node_bg"]}" color="{theme["node_fg"]}"'

def apply_class(line, class_map):
    """Replace class=xyz with actual style attributes."""
    m = re.search(r'class=(\w+)', line)
    if m and m.group(1) in class_map:
        replacement = class_map[m.group(1)]
        line = re.sub(r'class=\w+', replacement, line)
    elif m:
        line = re.sub(r'\s*class=\w+', '', line)
    return line


def offset_edge_label(line):
    """Convert edge label to taillabel with distance offset so text floats
    beside the line instead of sitting on it."""
    if '->' not in line:
        return line
    m = re.search(r'label="([^"]*)"', line)
    if not m:
        return line
    text = m.group(1)
    line = re.sub(r'label="[^"]*"', f'taillabel="  {text}  " labeldistance=3.5 labelangle=30', line)
    return line

def style_cluster_line(line, cluster_name, depth=0):
    """Add styling to cluster label/attributes."""
    theme = get_cluster_theme(cluster_name)
    color = theme.get("color", BORDER)
    fc = theme.get("fontcolor", FG)
    is_sub = depth > 1  # nested clusters get subtler styling

    # Bold the label
    m = re.match(r'(\s*)label="(.+)"', line)
    if m:
        indent = m.group(1)
        text = m.group(2)
        margin = "16" if is_sub else "36"
        return f'{indent}label=<<B>{text}</B>>\n{indent}fontsize={"11" if is_sub else "14"}\n{indent}fontcolor="{fc}"\n{indent}style="rounded{"" if is_sub else ",dashed"}"\n{indent}color="{color}"\n{indent}bgcolor="{BG + "99" if is_sub else BG}"\n{indent}penwidth={"1.5" if is_sub else "2"}\n{indent}margin="{margin}"'
    return line

def process(src):
    lines = src.split('\n')
    out = []
    cluster_stack = []
    current_cluster = None

    # Inject global defaults after first line
    global_defaults = f"""    bgcolor="{BG}"
    fontname="{FONT}"
    fontsize=14
    fontcolor="{FG}"
    pad=1.0
    nodesep=0.6
    ranksep=0.7
    splines=true
    newrank=true
    forcelabels=true

    node [
        fontname="{FONT}"
        fontsize=11
        fontcolor="{FG}"
        style="filled,rounded"
        shape=box
        penwidth=1.5
        margin="0.18,0.10"
    ]

    edge [
        fontname="{FONT}"
        fontsize=10
        fontcolor="#9198a1"
        color="{MUTED}"
        penwidth=1.3
        arrowsize=0.7
        arrowhead=vee
    ]"""

    for i, line in enumerate(lines):
        # Track cluster context
        cluster_name = detect_cluster(line)
        if cluster_name:
            cluster_stack.append(cluster_name)
            current_cluster = cluster_name
            out.append(line)
            continue

        if line.strip() == '}' and cluster_stack:
            out.append(line)
            cluster_stack.pop()
            current_cluster = cluster_stack[-1] if cluster_stack else None
            continue

        # Style cluster label lines
        if re.match(r'\s*label="', line) and current_cluster:
            out.append(style_cluster_line(line, current_cluster, depth=len(cluster_stack)))
            continue

        # Apply node classes + default cluster style
        if re.search(r'class=\w+', line) and '->' not in line:
            line = apply_class(line, NODE_CLASSES)
            # Add decision diamond color from cluster if it's a decision
            if 'shape=diamond' in line and current_cluster:
                theme = get_cluster_theme(current_cluster)
                dc = theme.get("color", BORDER)
                if f'color="' not in line:
                    line = line.rstrip(']') + f' color="{dc}"]'
            out.append(line)
            continue

        # Apply node default style if no class and it's a node definition
        if re.match(r'\s+\w+\s*\[', line) and '->' not in line and 'class=' not in line:
            if current_cluster and 'fillcolor' not in line:
                default = get_default_node_style(current_cluster)
                line = line.rstrip(']') + f' {default}]'
            out.append(line)
            continue

        # Apply edge classes and label backgrounds
        if '->' in line:
            if 'class=' in line:
                line = apply_class(line, EDGE_CLASSES)
            line = offset_edge_label(line)
            out.append(line)
            continue

        # Skip rankdir/compound (we set our own)
        if re.match(r'\s*(rankdir|compound)\s*=', line):
            continue

        out.append(line)

    # Inject global defaults after the opening { of the digraph
    result = '\n'.join(out)
    result = re.sub(
        r'(digraph\s+\S+\s*\{)\n',
        rf'\1\n{global_defaults}\n\n',
        result,
        count=1,
    )
    return result

def render(styled_dot, fmt, output_path):
    """Render styled dot source to a file. fmt is 'svg' or 'png'."""
    cmd = ['dot', f'-T{fmt}']
    if fmt == 'png':
        cmd += ['-Gdpi=200']
    proc = subprocess.run(cmd, input=styled_dot.encode(), capture_output=True)
    if proc.returncode != 0:
        print(f"dot error ({fmt}):\n{proc.stderr.decode()}", file=sys.stderr)
        with open("styled_debug.dot", 'w') as f:
            f.write(styled_dot)
        print("Wrote styled_debug.dot for inspection", file=sys.stderr)
        sys.exit(1)
    with open(output_path, 'wb') as f:
        f.write(proc.stdout)
    print(f"  {output_path}")


if not os.path.isfile(INPUT):
    print(f"Error: {INPUT} not found", file=sys.stderr)
    sys.exit(1)

with open(INPUT) as f:
    src = f.read()

assign_cluster_colors(src)
styled = process(src)

# Determine output targets
base = OUTPUT_ARG or os.path.splitext(INPUT)[0]
if base.endswith('.svg'):
    targets = [('svg', base)]
elif base.endswith('.png'):
    targets = [('png', base)]
else:
    targets = [('svg', f'{base}.svg'), ('png', f'{base}.png')]

print(f"Rendering {INPUT}:")
for fmt, path in targets:
    render(styled, fmt, path)
