/* OptiFlow Dining · Plano Arquitectónico SVG Dinámico (Dimensiones variables y muros estrictos). */
(() => {
  'use strict';

  const OptiFlow = (window.OptiFlow = window.OptiFlow || {});
  const { $, $$, svg } = OptiFlow;

  const STEP_X = 186;
  const STEP_Y = 113;
  const ORIGIN_X = 97;
  const ORIGIN_Y = 73;

  /** Convierte coordenadas lógicas 'X,Y' a píxeles dentro del lienzo SVG. */
  function xy(node) {
    const [x, y] = String(node).split(',').map(Number);
    return [ORIGIN_X + x * STEP_X, ORIGIN_Y + y * STEP_Y];
  }

  /** Construye los rectángulos de sectores A, B y C ajustados dinámicamente a las columnas activas. */
  function buildZoneRects(layout, cols, svgWidth) {
    const palette = {
      A: { c: '#10b981', t: 'ZONA A', sub: 'Salón Jardín' },
      B: { c: '#3b82f6', t: 'ZONA B', sub: 'Pasillo Central' },
      C: { c: '#ff7b3d', t: 'ZONA C', sub: 'Salón Terraza' },
    };

    const rawZones = Array.isArray(layout.zones) && layout.zones.length
      ? layout.zones
      : [
          { id: 'A', columns: [0, 1] },
          { id: 'B', columns: [2] },
          { id: 'C', columns: [3, 4] },
        ];

    return rawZones
      .map((z) => {
        const id = String(z.id || 'A').toUpperCase();
        const validCols = (z.columns || []).map(Number).filter((c) => c >= 0 && c < cols);
        if (!validCols.length) return null;
        const minCol = Math.min(...validCols);
        const maxCol = Math.max(...validCols);
        const left = minCol === 0 ? 24 : ORIGIN_X + minCol * STEP_X - 88;
        const right = maxCol >= cols - 1 ? svgWidth - 24 : ORIGIN_X + maxCol * STEP_X + 84;
        const meta = palette[id] || palette.C;
        return {
          id,
          x: left,
          width: Math.max(148, right - left),
          c: meta.c,
          t: meta.t,
          sub: meta.sub,
          cols: validCols,
        };
      })
      .filter(Boolean);
  }

  /** Enfoca y resalta la tarjeta operativa de una mesa al seleccionarla en el plano SVG. */
  function selectAndFocusTable(code) {
    const card = $(`#card-${code}`);
    if (card) {
      card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      card.classList.add('flash-highlight');
      setTimeout(() => card.classList.remove('flash-highlight'), 1800);
      const sel = $(`#select-${code}`);
      if (sel) sel.focus();
    }
    $$('.blueprint-table-group').forEach((g) => {
      g.classList.toggle('selected-table', g.dataset.tableId === code);
    });
  }

  /** Renderiza el plano vectorial SVG escalando dinámicamente a (columns x rows) sin desbordes. */
  function floorPlan(layout, path = [], destination = null, congested = [], customStates = null) {
    const canvas = $('#floor-plan');
    if (!canvas || !layout) return;

    const cols = Math.max(3, Number(layout.columns) || 5);
    const rows = Math.max(3, Number(layout.rows) || 5);
    const svgWidth = ORIGIN_X + (cols - 1) * STEP_X + 119;
    const svgHeight = ORIGIN_Y + (rows - 1) * STEP_Y + 85;

    canvas.setAttribute('viewBox', `0 0 ${svgWidth} ${svgHeight}`);
    canvas.classList.toggle('is-expanded-grid', cols > 6 || rows > 6);
    canvas.replaceChildren();

    if (!window.currentTableStates) {
      try {
        window.currentTableStates = JSON.parse($('#tables-state-data')?.textContent || '{}');
      } catch (_) {
        window.currentTableStates = {};
      }
    }
    const states = customStates || window.currentTableStates || {};

    // 1. Marco arquitectónico perimetral adaptado a las dimensiones activas
    canvas.append(
      svg('rect', {
        x: 14,
        y: 12,
        width: svgWidth - 28,
        height: svgHeight - 24,
        rx: 18,
        fill: '#060d19',
        stroke: 'rgba(255, 255, 255, 0.09)',
        'stroke-width': 2,
        class: 'blueprint-outer-frame',
      })
    );

    // 2. Cuadrícula milimétrica CAD de fondo
    for (let gx = 52; gx < svgWidth - 20; gx += 44) {
      canvas.append(
        svg('line', {
          x1: gx,
          y1: 16,
          x2: gx,
          y2: svgHeight - 16,
          stroke: 'rgba(255, 255, 255, 0.025)',
          'stroke-width': 1,
          'stroke-dasharray': '3 6',
        })
      );
    }
    for (let gy = 42; gy < svgHeight - 20; gy += 44) {
      canvas.append(
        svg('line', {
          x1: 18,
          y1: gy,
          x2: svgWidth - 18,
          y2: gy,
          stroke: 'rgba(255, 255, 255, 0.025)',
          'stroke-width': 1,
          'stroke-dasharray': '3 6',
        })
      );
    }

    // 3. Sectores de Zonas A, B y C dinámicos
    const zoneRects = buildZoneRects(layout, cols, svgWidth);
    zoneRects.forEach((z) => {
      canvas.append(
        svg('rect', {
          x: z.x,
          y: 20,
          width: z.width,
          height: svgHeight - 40,
          rx: 12,
          fill: z.c,
          opacity: 0.05,
          stroke: z.c,
          'stroke-width': 1,
          'stroke-opacity': 0.18,
          'stroke-dasharray': '6 6',
        })
      );

      const compactHeader = z.width < 185;
      canvas.append(
        svg('rect', {
          x: z.x + 12,
          y: 26,
          width: compactHeader ? 76 : Math.min(182, z.width - 24),
          height: 22,
          rx: 6,
          fill: '#081324',
          stroke: z.c,
          'stroke-width': 1,
          'stroke-opacity': 0.5,
        })
      );

      canvas.append(
        svg(
          'text',
          {
            x: z.x + 20,
            y: 41,
            class: 'zone-map-label',
            fill: z.c,
            'font-weight': '800',
            'font-size': '11',
            'letter-spacing': '1px',
          },
          z.t
        )
      );

      if (!compactHeader) {
        canvas.append(
          svg(
            'text',
            {
              x: z.x + 74,
              y: 41,
              fill: '#94a3b8',
              'font-size': '10',
              'font-weight': '600',
            },
            `· ${z.sub}`
          )
        );
      }
    });

    // 4. Red de pasillos y nodos transitables (0..cols-1 x 0..rows-1)
    for (let x = 0; x < cols; x++) {
      for (let y = 0; y < rows; y++) {
        const p = xy(`${x},${y}`);
        if (x < cols - 1) {
          canvas.append(
            svg('line', {
              x1: p[0],
              y1: p[1],
              x2: p[0] + STEP_X,
              y2: p[1],
              class: 'floor-walk-line',
            })
          );
        }
        if (y < rows - 1) {
          canvas.append(
            svg('line', {
              x1: p[0],
              y1: p[1],
              x2: p[0],
              y2: p[1] + STEP_Y,
              class: 'floor-walk-line',
            })
          );
        }
        canvas.append(
          svg('circle', {
            cx: p[0],
            cy: p[1],
            r: 4,
            class: 'floor-spot',
          })
        );
      }
    }

    // 5. Puntos de origen (Cocina, Entrada u otros definidos en salon.json)
    (layout.origins || []).forEach((orig) => {
      const [ox, oy] = String(orig.node || '0,0').split(',').map(Number);
      if (ox < 0 || ox >= cols || oy < 0 || oy >= rows) return;
      const [px, py] = xy(orig.node);
      const isKitchen = orig.id === 'cocina';
      const origG = svg('g', {
        class: isKitchen ? 'blueprint-origin-kitchen' : 'blueprint-origin-entrance',
      });
      origG.append(
        svg('rect', {
          x: px - 72,
          y: py - (isKitchen ? 34 : 32),
          width: 144,
          height: isKitchen ? 68 : 64,
          rx: 14,
          class: isKitchen ? 'kitchen-box' : 'entrance-box',
        })
      );
      origG.append(
        svg(
          'text',
          { x: px, y: py - 3, class: isKitchen ? 'kitchen-text' : 'entrance-text' },
          isKitchen ? '♨ COCINA' : `🚪 ${(orig.label || orig.id).toUpperCase()}`
        )
      );
      origG.append(
        svg(
          'text',
          { x: px, y: py + 16, class: isKitchen ? 'kitchen-subtext' : 'entrance-subtext' },
          isKitchen ? 'Despacho y Pase' : 'Recepción / Clientes'
        )
      );
      canvas.append(origG);
    });

    // 6. Mesas interactivas dentro de los límites estrictos del salón
    (layout.tables || []).forEach((t) => {
      const [tx, ty] = String(t.node || '0,0').split(',').map(Number);
      if (tx < 0 || tx >= cols || ty < 0 || ty >= rows) return;

      const [x, y] = xy(t.node);
      const st = states[t.id] || 'disponible';
      const isTarget = t.id === destination;
      const seats = Number(t.seats) || 4;

      const group = svg('g', {
        class: `blueprint-table-group state-${st} ${isTarget ? 'plan-table-active' : ''}`,
        'data-table-id': t.id,
      });

      if (seats === 2) {
        group.append(svg('rect', { x: x - 74, y: y - 12, width: 8, height: 24, rx: 4, class: 'chair-elem' }));
        group.append(svg('rect', { x: x + 66, y: y - 12, width: 8, height: 24, rx: 4, class: 'chair-elem' }));
      } else if (seats >= 8) {
        [-48, -16, 16, 48].forEach((offset) => {
          group.append(svg('rect', { x: x + offset - 10, y: y - 48, width: 20, height: 8, rx: 4, class: 'chair-elem' }));
          group.append(svg('rect', { x: x + offset - 10, y: y + 40, width: 20, height: 8, rx: 4, class: 'chair-elem' }));
        });
      } else if (seats === 6) {
        [-46, 0, 46].forEach((offset) => {
          group.append(svg('rect', { x: x + offset - 12, y: y - 48, width: 24, height: 8, rx: 4, class: 'chair-elem' }));
          group.append(svg('rect', { x: x + offset - 12, y: y + 40, width: 24, height: 8, rx: 4, class: 'chair-elem' }));
        });
      } else {
        [-24, 24].forEach((offset) => {
          group.append(svg('rect', { x: x + offset - 13, y: y - 48, width: 26, height: 8, rx: 4, class: 'chair-elem' }));
          group.append(svg('rect', { x: x + offset - 13, y: y + 40, width: 26, height: 8, rx: 4, class: 'chair-elem' }));
        });
      }

      group.append(
        svg('rect', {
          x: x - 64,
          y: y - 37,
          width: 128,
          height: 74,
          rx: 13,
          class: 'plan-table-surface',
        })
      );
      group.append(svg('text', { x, y: y - 13, class: 'plan-table-title' }, t.label));
      group.append(svg('text', { x, y: y + 5, class: 'plan-table-capacity' }, `👥 ${seats} personas`));
      group.append(
        svg('rect', {
          x: x - 46,
          y: y + 14,
          width: 92,
          height: 18,
          rx: 9,
          class: 'plan-table-pill-bg',
        })
      );
      group.append(svg('text', { x, y: y + 27, class: 'plan-table-status-text' }, `● ${st.toUpperCase()}`));

      group.style.cursor = 'pointer';
      group.addEventListener('click', () => selectAndFocusTable(t.id));
      canvas.append(group);
    });

    // 7. Sello arquitectónico de dimensiones activas en esquina inferior derecha
    canvas.append(
      svg(
        'text',
        {
          x: svgWidth - 32,
          y: svgHeight - 24,
          'text-anchor': 'end',
          fill: 'rgba(148, 163, 184, 0.55)',
          'font-size': '10.5',
          'font-weight': '700',
          'letter-spacing': '0.8px',
        },
        `RED CAD ${cols}×${rows}`
      )
    );

    // 8. Ruta calculada garantizando que ningún tramo salga de la cuadrícula activa
    const boundedPath = (path || []).filter((n) => {
      const [nx, ny] = String(n).split(',').map(Number);
      return nx >= 0 && nx < cols && ny >= 0 && ny < rows;
    });

    if (boundedPath.length) {
      const points = boundedPath.map((n) => xy(n).join(',')).join(' ');
      canvas.append(svg('polyline', { points, class: 'floor-route-shadow' }));
      canvas.append(svg('polyline', { points, class: 'floor-route' }));
      const start = xy(boundedPath[0]);
      const end = xy(boundedPath[boundedPath.length - 1]);
      canvas.append(svg('circle', { cx: start[0], cy: start[1], r: 10, class: 'floor-route-dot' }));
      canvas.append(svg('circle', { cx: end[0], cy: end[1], r: 10, class: 'floor-route-dot' }));
    }

    // 9. Marcadores interactivos de congestión dentro del mapa
    (congested || []).forEach((n) => {
      const [cxGrid, cyGrid] = String(n).split(',').map(Number);
      if (cxGrid < 0 || cxGrid >= cols || cyGrid < 0 || cyGrid >= rows) return;

      const p = xy(n);
      const g = svg('g', {
        class: 'congestion-marker-group',
        'data-node': n,
        style: 'cursor: pointer;',
        role: 'button',
        tabindex: '0',
        'aria-label': `Punto de congestión en nodo ${n}. Clic para detalles.`,
      });
      g.append(
        svg('circle', {
          cx: p[0],
          cy: p[1],
          r: 28,
          fill: 'transparent',
          style: 'pointer-events: all; cursor: pointer;',
        })
      );
      g.append(svg('circle', { cx: p[0], cy: p[1], r: 18, class: 'congestion-pulse-ring' }));
      g.append(svg('circle', { cx: p[0], cy: p[1], r: 14, class: 'congestion-point' }));
      g.append(
        svg(
          'text',
          {
            x: p[0],
            y: p[1] + 5,
            'text-anchor': 'middle',
            fill: 'white',
            'font-size': '15',
            'font-weight': '900',
            'pointer-events': 'none',
          },
          '!'
        )
      );
      g.append(svg('title', {}, `Punto crítico en nodo (${n}). Haz clic para ver detalles.`));

      const handleOpen = (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (typeof OptiFlow.openCongestionModal === 'function') {
          OptiFlow.openCongestionModal(n, destination);
        }
      };
      g.addEventListener('click', handleOpen);
      g.addEventListener('pointerdown', (e) => {
        if (e.pointerType === 'touch') handleOpen(e);
      });
      g.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') handleOpen(e);
      });
      canvas.append(g);
    });
  }

  /** Dibuja inicialmente el plano SVG si existe en la pantalla actual. */
  function initFloorPlan() {
    OptiFlow.layoutData = OptiFlow.getLayout();
    if ($('#floor-plan') && OptiFlow.layoutData) {
      floorPlan(OptiFlow.layoutData, [], null, []);
    }
  }

  Object.assign(OptiFlow, {
    xy,
    buildZoneRects,
    selectAndFocusTable,
    floorPlan,
    initFloorPlan,
  });
})();

