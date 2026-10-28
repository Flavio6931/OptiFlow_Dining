/* OptiFlow Dining: interacción accesible y APIs Django con CSRF. */
(() => {
  'use strict';

  // --- Selectores y Constantes Utilitarias ---
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const SVGNS = 'http://www.w3.org/2000/svg';

  /**
   * Obtiene el token CSRF desde la etiqueta meta o la cookie csrftoken.
   */
  const csrf = () => {
    return (
      document.querySelector('meta[name="csrf-token"]')?.content ||
      (document.cookie.match(/(?:^|; )csrftoken=([^;]*)/) || [])[1] ||
      ''
    );
  };

  let toastTimer;

  /**
   * Muestra un mensaje flotante tipo toast en la interfaz.
   */
  function toast(message, kind = '') {
    const el = $('#toast');
    if (!el) {
      alert(message);
      return;
    }
    el.textContent = message;
    el.className = `toast visible ${kind}`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      el.className = 'toast';
    }, 4000);
  }

  /**
   * Realiza una petición POST enviando un cuerpo JSON con credenciales y CSRF.
   */
  async function postJSON(url, obj) {
    const r = await fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf(),
      },
      body: JSON.stringify(obj),
    });

    let data;
    try {
      data = await r.json();
    } catch (_) {
      throw new Error('La respuesta del servidor no es válida.');
    }

    if (!r.ok) {
      throw new Error(data.error || data.detail || `Error ${r.status}`);
    }
    return data;
  }

  /**
   * Crea un elemento SVG con atributos y texto opcional.
   */
  function svg(tag, attributes = {}, textContent = '') {
    const el = document.createElementNS(SVGNS, tag);
    Object.entries(attributes).forEach(([k, v]) => el.setAttribute(k, String(v)));
    if (textContent) {
      el.textContent = textContent;
    }
    return el;
  }

  /**
   * Convierte coordenadas de nodo 'x,y' en píxeles del plano SVG.
   */
  const xy = (node) => {
    const [x, y] = node.split(',').map(Number);
    return [97 + x * 186, 73 + y * 113];
  };

  /**
   * Lee la configuración del plano embebida en el DOM.
   */
  function getLayout() {
    try {
      return JSON.parse($('#floor-layout').textContent);
    } catch (_) {
      return null;
    }
  }

  /**
   * Dibuja el plano esquemático del restaurante y el camino óptimo.
  /**
   * Dibuja el plano esquemático y arquitectónico del restaurante y el camino óptimo.
   */
  function floorPlan(layout, path = [], destination = null, congested = [], customStates = null) {
    const canvas = $('#floor-plan');
    if (!canvas || !layout) return;

    canvas.replaceChildren();

    // Obtener estados actuales de mesas (de script embebido o memoria)
    if (!window.currentTableStates) {
      try {
        window.currentTableStates = JSON.parse($('#tables-state-data')?.textContent || '{}');
      } catch (_) {
        window.currentTableStates = {};
      }
    }
    const states = customStates || window.currentTableStates || {};

    // 1. Marco perimetral y fondo oscuro arquitectónico
    canvas.append(
      svg('rect', {
        x: 14,
        y: 12,
        width: 932,
        height: 586,
        rx: 18,
        fill: '#060d19',
        stroke: 'rgba(255, 255, 255, 0.09)',
        'stroke-width': 2,
        class: 'blueprint-outer-frame',
      })
    );

    // 2. Líneas de cuadrícula milimétrica CAD tenue
    for (let gx = 52; gx < 940; gx += 44) {
      canvas.append(
        svg('line', {
          x1: gx,
          y1: 16,
          x2: gx,
          y2: 594,
          stroke: 'rgba(255, 255, 255, 0.025)',
          'stroke-width': 1,
          'stroke-dasharray': '3 6',
        })
      );
    }
    for (let gy = 42; gy < 590; gy += 44) {
      canvas.append(
        svg('line', {
          x1: 18,
          y1: gy,
          x2: 942,
          y2: gy,
          stroke: 'rgba(255, 255, 255, 0.025)',
          'stroke-width': 1,
          'stroke-dasharray': '3 6',
        })
      );
    }

    // 3. Definición y pintado de zonas A, B, C con badges arquitectónicos
    const zoneDefs = [
      { x: 26, width: 326, c: '#10b981', t: 'ZONA A', sub: 'Salón Jardín' },
      { x: 358, width: 196, c: '#3b82f6', t: 'ZONA B', sub: 'Pasillo Central' },
      { x: 560, width: 376, c: '#ff7b3d', t: 'ZONA C', sub: 'Salón Terraza' },
    ];

    zoneDefs.forEach((z) => {
      // Área de zona con borde sutil
      canvas.append(
        svg('rect', {
          x: z.x,
          y: 20,
          width: z.width,
          height: 570,
          rx: 12,
          fill: z.c,
          opacity: 0.05,
          stroke: z.c,
          'stroke-width': 1,
          'stroke-opacity': 0.18,
          'stroke-dasharray': '6 6',
        })
      );

      // Píldora de cabecera de la zona
      canvas.append(
        svg('rect', {
          x: z.x + 14,
          y: 26,
          width: 130,
          height: 22,
          rx: 6,
          fill: '#081324',
          stroke: z.c,
          'stroke-width': 1,
          'stroke-opacity': 0.5,
        })
      );

      // Texto de zona
      canvas.append(
        svg(
          'text',
          {
            x: z.x + 22,
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
      canvas.append(
        svg(
          'text',
          {
            x: z.x + 76,
            y: 41,
            fill: '#94a3b8',
            'font-size': '10',
            'font-weight': '600',
          },
          `· ${z.sub}`
        )
      );
    });

    // 4. Cuadrícula y pasillos de tránsito principales (5x5)
    for (let x = 0; x < 5; x++) {
      for (let y = 0; y < 5; y++) {
        const p = xy(`${x},${y}`);
        if (x < 4) {
          canvas.append(
            svg('line', {
              x1: p[0],
              y1: p[1],
              x2: p[0] + 186,
              y2: p[1],
              class: 'floor-walk-line',
            })
          );
        }
        if (y < 4) {
          canvas.append(
            svg('line', {
              x1: p[0],
              y1: p[1],
              x2: p[0],
              y2: p[1] + 113,
              class: 'floor-walk-line',
            })
          );
        }
        canvas.append(svg('circle', { cx: p[0], cy: p[1], r: 4, class: 'floor-spot' }));
      }
    }

    // 5. Origen: Zona de Cocina (node '0,2')
    const [kx, ky] = xy('0,2');
    const kitchenG = svg('g', { class: 'blueprint-origin-kitchen' });
    kitchenG.append(
      svg('rect', {
        x: kx - 72,
        y: ky - 34,
        width: 144,
        height: 68,
        rx: 14,
        class: 'kitchen-box',
      })
    );
    kitchenG.append(
      svg(
        'text',
        {
          x: kx,
          y: ky - 4,
          class: 'kitchen-text',
        },
        '♨ COCINA'
      )
    );
    kitchenG.append(
      svg(
        'text',
        {
          x: kx,
          y: ky + 16,
          class: 'kitchen-subtext',
        },
        'Despacho y Pase'
      )
    );
    canvas.append(kitchenG);

    // 6. Origen: Acceso Principal / Entrada (node '0,4')
    const [ex, ey] = xy('0,4');
    const entranceG = svg('g', { class: 'blueprint-origin-entrance' });
    entranceG.append(
      svg('rect', {
        x: ex - 72,
        y: ey - 32,
        width: 144,
        height: 64,
        rx: 14,
        class: 'entrance-box',
      })
    );
    entranceG.append(
      svg(
        'text',
        {
          x: ex,
          y: ey - 3,
          class: 'entrance-text',
        },
        '🚪 ACCESO PRINCIPAL'
      )
    );
    entranceG.append(
      svg(
        'text',
        {
          x: ex,
          y: ey + 16,
          class: 'entrance-subtext',
        },
        'Recepción / Clientes'
      )
    );
    canvas.append(entranceG);

    // 7. Renderizado detallado de Mesas y Sillas
    layout.tables.forEach((t) => {
      const [x, y] = xy(t.node);
      const st = states[t.id] || 'disponible';
      const isTarget = t.id === destination;
      const seats = Number(t.seats) || 4;

      const group = svg('g', {
        class: `blueprint-table-group state-${st} ${isTarget ? 'plan-table-active' : ''}`,
        'data-table-id': t.id,
      });

      // Sillas según la capacidad de comensales
      if (seats === 2) {
        // 1 a la izquierda, 1 a la derecha
        group.append(svg('rect', { x: x - 74, y: y - 12, width: 8, height: 24, rx: 4, class: 'chair-elem' }));
        group.append(svg('rect', { x: x + 66, y: y - 12, width: 8, height: 24, rx: 4, class: 'chair-elem' }));
      } else if (seats === 6) {
        // 3 arriba, 3 abajo
        [-46, 0, 46].forEach((offset) => {
          group.append(svg('rect', { x: x + offset - 12, y: y - 48, width: 24, height: 8, rx: 4, class: 'chair-elem' }));
          group.append(svg('rect', { x: x + offset - 12, y: y + 40, width: 24, height: 8, rx: 4, class: 'chair-elem' }));
        });
      } else {
        // 4 sillas estándar (2 arriba, 2 abajo)
        [-24, 24].forEach((offset) => {
          group.append(svg('rect', { x: x + offset - 13, y: y - 48, width: 26, height: 8, rx: 4, class: 'chair-elem' }));
          group.append(svg('rect', { x: x + offset - 13, y: y + 40, width: 26, height: 8, rx: 4, class: 'chair-elem' }));
        });
      }

      // Superficie de la mesa
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

      // Nombre de mesa
      group.append(svg('text', { x, y: y - 13, class: 'plan-table-title' }, t.label));

      // Capacidad de comensales
      group.append(svg('text', { x, y: y + 5, class: 'plan-table-capacity' }, `👥 ${seats} personas`));

      // Píldora de estado en vivo
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
      group.append(
        svg(
          'text',
          { x, y: y + 27, class: 'plan-table-status-text' },
          `● ${st.toUpperCase()}`
        )
      );

      // Sincronización al hacer clic en la mesa del plano
      group.style.cursor = 'pointer';
      group.addEventListener('click', () => {
        selectAndFocusTable(t.id);
      });

      canvas.append(group);
    });

    // 8. Trazado de ruta óptima calculada (si aplica)
    if (path.length) {
      const points = path.map((n) => xy(n).join(',')).join(' ');
      canvas.append(svg('polyline', { points, class: 'floor-route-shadow' }));
      canvas.append(svg('polyline', { points, class: 'floor-route' }));
      const start = xy(path[0]);
      const end = xy(path[path.length - 1]);
      canvas.append(svg('circle', { cx: start[0], cy: start[1], r: 10, class: 'floor-route-dot' }));
      canvas.append(svg('circle', { cx: end[0], cy: end[1], r: 10, class: 'floor-route-dot' }));
    }

    // 9. Puntos de congestión detectados (Interactivos con explicación al pulsar)
    congested.forEach((n) => {
      const p = xy(n);
      const g = svg('g', {
        class: 'congestion-marker-group',
        'data-node': n,
        style: 'cursor: pointer;',
        role: 'button',
        'aria-label': `Punto de congestión en nodo ${n}. Clic para detalles.`
      });
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
      g.append(svg('title', {}, `Punto crítico en nodo (${n}). Haz clic para ver detalles y recomendaciones.`));
      g.addEventListener('click', (e) => {
        e.stopPropagation();
        openCongestionModal(n, destination);
      });
      canvas.append(g);
    });
  }

  /**
   * Enfoca y resalta la tarjeta de una mesa cuando se hace clic en el plano.
   */
  function selectAndFocusTable(code) {
    const card = $(`#card-${code}`);
    if (card) {
      card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      card.classList.add('flash-highlight');
      setTimeout(() => card.classList.remove('flash-highlight'), 1800);
      const sel = $(`#select-${code}`);
      if (sel) sel.focus();
    }
    // Resaltar mesa en el plano
    $$('.blueprint-table-group').forEach((g) => {
      g.classList.toggle('selected-table', g.dataset.tableId === code);
    });
  }

  // --- Navegación Mobile ---
  $('#menu-trigger')?.addEventListener('click', () => $('#sidebar')?.classList.toggle('open'));
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.sidebar') && !e.target.closest('#menu-trigger')) {
      $('#sidebar')?.classList.remove('open');
    }
  });

  // --- Planificador de Rutas (FastAPI vía Django DRF) ---
  const layout = getLayout();
  if ($('#floor-plan')) {
    floorPlan(layout, [], null, []);
  }

  let lastRouteId = null;
  const routeFeedback = $('#route-feedback');

  // --- Modal Explicativo de Congestión (Nodos Rojos !) con Evidencia OpenCV ---
  function openCongestionModal(node, destination) {
    const modal = $('#congestion-modal');
    const modalBody = $('#congestion-modal-body');
    const modalTitle = $('#congestion-modal-title');
    const modalSub = $('#congestion-modal-subtitle');
    if (!modal || !modalBody) return;

    const [x, y] = node.split(',').map(Number);
    let zoneCode = 'B';
    let zoneName = 'Zona B · Pasillo Central';
    let zoneDesc = 'Pasillo de conexión neurálgico entre la Cocina y los salones del restaurante.';
    if (x <= 1) {
      zoneCode = 'A';
      zoneName = 'Zona A · Salón Jardín';
      zoneDesc = 'Sector occidental de mesas bajas y acceso principal.';
    } else if (x >= 3) {
      zoneCode = 'C';
      zoneName = 'Zona C · Salón Terraza';
      zoneDesc = 'Sector oriental de mesas de alta capacidad y ventanales.';
    }

    if (modalTitle) modalTitle.textContent = `Alerta de Congestión: Nodo (${node})`;
    if (modalSub) modalSub.textContent = `${zoneName} · Estado Crítico Operativo`;

    let visionData = null;
    try {
      const vEl = $('#latest-vision-data');
      if (vEl) visionData = JSON.parse(vEl.textContent);
    } catch (_) {}

    const peopleInZone = visionData?.zone_counts?.[zoneCode] ?? 1;
    const totalPeople = visionData?.people_count ?? 1;
    const visionImgUrl = visionData?.image_url || '/static/img/latest_vision_capture.jpg';

    modalBody.innerHTML = `
      <div class="congestion-alert-banner-status">
        <div class="alert-status-badge">🔴 ESTADO CRÍTICO DETECTADO</div>
        <p class="alert-status-text">
          <strong>Motivo de la Alerta:</strong> Se detectó saturación operativa y alta afluencia peatonal en este pasillo, superando el límite seguro de tránsito para meseros.
        </p>
      </div>

      <div class="congestion-evidence-card">
        <div class="evidence-header">
          <div class="evidence-title">
            <span class="evidence-icon">📷</span>
            <strong>Evidencia Visual · Análisis OpenCV HOG</strong>
          </div>
          <span class="evidence-tag">Afluencia: ${peopleInZone} en Sector ${zoneCode}</span>
        </div>
        <div class="evidence-image-frame">
          <img src="${visionImgUrl}" alt="Captura analizada por OpenCV mostrando aglomeración en la zona" class="evidence-img">
          <div class="evidence-zone-overlay">
            <span>Sector analizado: <strong>${zoneName}</strong></span>
            <small>Detección computacional de siluetas activas (${totalPeople} total)</small>
          </div>
        </div>
      </div>

      <div class="congestion-info-card">
        <div class="congestion-detail-row">
          <span class="detail-label">Sector Afectado:</span>
          <strong>${zoneName}</strong>
        </div>
        <div class="congestion-detail-row">
          <span class="detail-label">Ubicación en Red:</span>
          <code>Columna ${x}, Fila ${y} (${y === 2 ? 'Pasillo Central' : 'Pasillo Secundario'})</code>
        </div>
        <p class="congestion-desc">
          ${zoneDesc} Cruzar por este nodo con charolas o pedidos implica riesgo de demoras y posibles choques de bandejas.
        </p>
      </div>

      <div class="congestion-recommendation-box">
        <strong>💡 Recomendación del Sistema:</strong>
        <p>Haz clic en el botón de abajo para <strong>Recalcular ruta</strong>. El algoritmo Dijkstra trazará de inmediato un desvío inteligente por un pasillo libre.</p>
      </div>
    `;

    modal.classList.remove('is-hidden');
  }

  function closeCongestionModal() {
    const modal = $('#congestion-modal');
    if (modal) modal.classList.add('is-hidden');
  }

  $('#congestion-modal-close')?.addEventListener('click', closeCongestionModal);
  $('#congestion-modal-btn-ok')?.addEventListener('click', closeCongestionModal);
  $('#congestion-modal-close-backdrop')?.addEventListener('click', closeCongestionModal);
  $('#congestion-modal-recalc-btn')?.addEventListener('click', () => {
    closeCongestionModal();
    requestRoute(true);
  });
  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeCongestionModal();
  });

  // --- Sistema de Mensajería Asistida en 3 Partes ---
  function feedback(title, message, type = 'success', actionHint = '') {
    if (!routeFeedback) return;
    routeFeedback.hidden = false;
    routeFeedback.className = `route-feedback ${type}`;
    routeFeedback.innerHTML = `
      <div class="feedback-badge-row">
        <span class="feedback-icon">${type === 'success' ? '✔' : type === 'warning' ? '⚠' : '✖'}</span>
        <strong>${title}</strong>
      </div>
      <p class="feedback-body">${message}</p>
      ${actionHint ? `<div class="feedback-action-hint">💡 <span>${actionHint}</span></div>` : ''}
    `;
  }

  async function requestRoute(avoid = false) {
    const btn = avoid ? $('#route-recalculate') : $('#route-submit');
    if (btn) btn.disabled = true;

    try {
      const assignedWaiterEl = $('#assigned-waiter');
      const assignedWaiterId = assignedWaiterEl && assignedWaiterEl.value ? Number(assignedWaiterEl.value) : null;

      const data = await postJSON('/api/rutas/', {
        origin: $('#origin').value,
        destination: $('#destination').value,
        task_type: $('#task-type').value,
        avoid_congestion: avoid,
        assigned_waiter: assignedWaiterId,
      });

      lastRouteId = data.route_id;
      floorPlan(layout, data.path, data.destination, data.congested_nodes);

      // Mensajería asistida según condición del recorrido
      if (data.congested && !avoid) {
        feedback(
          'Se detectó congestión en el trayecto directo',
          `El recorrido cruza por nodos de alta afluencia (marcados con <strong>!</strong> en rojo). Distancia estimada: ${data.distance} tramos.`,
          'warning',
          'Haz clic en los puntos rojos del mapa para ver los motivos, o pulsa "↻ Recalcular ruta" para tomar un desvío despejado.'
        );
      } else if (avoid) {
        feedback(
          'Ruta alternativa optimizada con Dijkstra',
          `El trayecto fue recalculado evitando los pasillos saturados. Recorrido seguro: ${data.distance} tramos.`,
          'success',
          'Ruta libre de cuellos de botella. Puedes dirigirte a la mesa de forma fluida.'
        );
      } else {
        feedback(
          'Ruta directa recomendada sin congestión',
          `Pasillos despejados entre ${data.origin.toUpperCase()} y ${data.destination.toUpperCase()}. Distancia: ${data.distance} tramos.`,
          'success',
          'Camino óptimo verificado para entrega o retiro de servicio.'
        );
      }

      // Inserción asíncrona inmediata en el historial (Cero recargas F5)
      const tbody = $('#recent-routes-tbody');
      if (tbody) {
        const emptyRow = $('#empty-routes-row');
        if (emptyRow) emptyRow.remove();

        const tr = document.createElement('tr');
        tr.id = `route-row-${data.route_id}`;
        tr.className = 'newly-added-row';
        const assignedBadge = data.assigned_waiter_name
          ? `<span class="badge-role-tag badge-assigned">Asignado: ${data.assigned_waiter_name}</span>`
          : `<span class="badge-role-tag badge-self">Auto-atención</span>`;

        tr.innerHTML = `
          <td><strong>${(data.destination_label || data.destination).toUpperCase()}</strong></td>
          <td>${data.task_type_display || (data.task_type === 'entrega' ? 'Entrega de comida' : 'Retiro de vajilla')}</td>
          <td>${assignedBadge}</td>
          <td>${data.created_at || 'Hace un momento'}</td>
          <td>
            <span id="status-pill-${data.route_id}" class="status-pill moderada">Consultada</span>
          </td>
        `;
        tbody.prepend(tr);
      }

      $('#route-actions').hidden = false;
      $('#route-complete').hidden = false;
      $('#route-recalculate').hidden = avoid || !data.congested;
      toast(avoid ? 'Ruta alternativa calculada sin demoras.' : 'Ruta calculada con éxito.', 'success');
    } catch (error) {
      feedback(
        'No se pudo completar el trazado de la ruta',
        error.message || 'El motor de ruteo no pudo calcular una trayectoria válida.',
        'error',
        'Verifica que el destino no se encuentre en un sector bloqueado o pulsa "Recalcular ruta".'
      );
      $('#route-actions').hidden = false;
      $('#route-recalculate').hidden = false;
      $('#route-complete').hidden = true;
      toast(error.message, 'error');
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  $('#route-form')?.addEventListener('submit', (e) => {
    e.preventDefault();
    requestRoute(false);
  });

  $('#route-recalculate')?.addEventListener('click', () => requestRoute(true));

  $('#route-complete')?.addEventListener('click', async () => {
    if (!lastRouteId) return toast('Primero calcula una ruta.', 'error');
    try {
      const data = await postJSON(`/api/rutas/${lastRouteId}/finalizar/`, {});
      feedback('Tarea de servicio finalizada', data.message, 'success', 'La mesa y el recorrido han sido marcados como atendidos.');
      toast(data.message, 'success');
      $('#route-actions').hidden = true;

      // Actualizar estado en la tabla en tiempo real
      const pill = $(`#status-pill-${lastRouteId}`);
      if (pill) {
        pill.className = 'status-pill normal';
        pill.textContent = 'Finalizada';
      }
    } catch (err) {
      toast(err.message, 'error');
    }
  });

  // --- Actualización Reactiva de Zonas de Saturación (Sin F5) ---
  function updateZoneUI(code, level, dwell, alert) {
    const pill = $(`#zone-pill-${code}`);
    if (pill) {
      pill.className = `status-pill ${level}`;
      pill.textContent = level === 'normal' ? 'Normal' : level === 'moderada' ? 'Moderada' : 'Crítica';
    }

    const heatCard = $(`#heat-zone-${code}`);
    if (heatCard) {
      heatCard.className = `heat-zone heat-${level}`;
    }
    const heatLevel = $(`#heat-level-${code}`);
    if (heatLevel) {
      heatLevel.textContent = level === 'normal' ? 'Normal' : level === 'moderada' ? 'Moderada' : 'Crítica';
    }
    const heatDwell = $(`#heat-dwell-${code}`);
    if (heatDwell) {
      heatDwell.textContent = `${Number(dwell).toFixed(1)} min de permanencia`;
    }

    const alertsContainer = $('#critical-zones-alerts');
    let banner = $(`#alert-banner-${code}`);
    if (alert) {
      if (!banner && alertsContainer) {
        banner = document.createElement('div');
        banner.className = 'alert-banner';
        banner.id = `alert-banner-${code}`;
        banner.innerHTML = `
          <svg class="ic"><use href="#i-alert"/></svg>
          <div>
            <strong>Congestión crítica · Nodo de la zona ${code}</strong>
            <span>Permanencia registrada: ${Number(dwell).toFixed(1)} minutos. Supera el umbral de 4 minutos.</span>
          </div>
        `;
        alertsContainer.prepend(banner);
      } else if (banner) {
        const span = banner.querySelector('span');
        if (span) span.textContent = `Permanencia registrada: ${Number(dwell).toFixed(1)} minutos. Supera el umbral de 4 minutos.`;
      }
    } else {
      if (banner) banner.remove();
    }
  }

  $$('.zone-save').forEach((btn) =>
    btn.addEventListener('click', async () => {
      const code = btn.dataset.zone;
      const levelVal = $(`#level-${code}`).value;
      const dwellVal = Number($(`#dwell-${code}`).value);
      try {
        const res = await postJSON(`/api/zonas/${code}/`, {
          level: levelVal,
          dwell_minutes: dwellVal,
        });
        toast(`Zona ${code} actualizada correctamente.`, 'success');
        updateZoneUI(code, levelVal, dwellVal, res.alert);
      } catch (err) {
        toast(err.message, 'error');
      }
    })
  );

  // Sugerencia automática de nivel al cambiar minutos de permanencia
  $$('input[id^="dwell-"]').forEach((input) => {
    input.addEventListener('input', () => {
      const val = parseFloat(input.value);
      const code = input.id.replace('dwell-', '');
      const select = $(`#level-${code}`);
      if (!isNaN(val) && select) {
        if (val <= 2.0) select.value = 'normal';
        else if (val <= 4.0) select.value = 'moderada';
        else select.value = 'critica';
      }
    });
  });

  // --- Actualización de Estado de Mesas con Sincronización en Tiempo Real ---
  function updateLayoutKPIs() {
    if (!window.currentTableStates) return;
    const vals = Object.values(window.currentTableStates);
    const avail = vals.filter((v) => v === 'disponible').length;
    const active = vals.filter((v) => v === 'activa').length;
    const occupied = vals.filter((v) => v === 'ocupada').length;
    const total = vals.length || 8;
    const pct = Math.round(((active + occupied) / total) * 100);

    const elAvail = $('#kpi-available-tables');
    const elActive = $('#kpi-active-tables');
    const elOcc = $('#kpi-occupied-tables');
    const elPct = $('#kpi-occupancy-sub');

    if (elAvail) elAvail.textContent = String(avail);
    if (elActive) elActive.textContent = String(active);
    if (elOcc) elOcc.textContent = String(occupied);
    if (elPct) elPct.textContent = `${pct}% de ocupación`;

    const fAll = $('#count-filter-all');
    const fAvail = $('#count-filter-disponible');
    const fAct = $('#count-filter-activa');
    const fOcc = $('#count-filter-ocupada');

    if (fAll) fAll.textContent = String(total);
    if (fAvail) fAvail.textContent = String(avail);
    if (fAct) fAct.textContent = String(active);
    if (fOcc) fOcc.textContent = String(occupied);
  }

  $$('.table-status-select').forEach((select) =>
    select.addEventListener('change', async () => {
      const code = select.dataset.code;
      const newState = select.value;
      const prevClass = select.className;

      try {
        await postJSON(`/api/mesas/${code}/`, {
          state: newState,
        });

        // Actualizar estado en memoria
        if (!window.currentTableStates) window.currentTableStates = {};
        window.currentTableStates[code] = newState;

        // Re-renderizar plano SVG con los nuevos estados
        floorPlan(layout, [], null, [], window.currentTableStates);

        // Actualizar tarjeta visual en la lista
        const card = $(`#card-${code}`);
        if (card) {
          card.className = `table-control table-state-card state-${newState}`;
          card.dataset.state = newState;
        }

        const pill = $(`#pill-${code}`);
        if (pill) {
          pill.className = `table-state-status-pill pill-${newState}`;
          const labelText = pill.querySelector('.status-label-text');
          if (labelText) {
            labelText.textContent = newState.charAt(0).toUpperCase() + newState.slice(1);
          }
        }

        select.className = `table-status-select select-${newState}`;

        // Actualizar contadores KPI
        updateLayoutKPIs();

        toast(`${code.toUpperCase()} actualizada a ${newState.toUpperCase()}.`, 'success');
      } catch (err) {
        select.className = prevClass;
        toast(err.message, 'error');
      }
    })
  );

  // --- Filtros Rápidos de Visualización de Mesas ---
  $$('#table-filter-group .table-filter-btn').forEach((btn) => {
    btn.addEventListener('click', () => {
      $$('#table-filter-group .table-filter-btn').forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');
      const filter = btn.dataset.filter;
      $$('.table-state-card').forEach((card) => {
        if (filter === 'all' || card.dataset.state === filter) {
          card.style.display = '';
        } else {
          card.style.display = 'none';
        }
      });
    });
  });

  // --- Resaltado Bidireccional: Hover en Tarjeta resalta en el Plano ---
  $$('.table-state-card').forEach((card) => {
    card.addEventListener('mouseenter', () => {
      const code = card.dataset.code;
      $$('.blueprint-table-group').forEach((g) => {
        g.classList.toggle('card-hovered-table', g.dataset.tableId === code);
      });
    });
    card.addEventListener('mouseleave', () => {
      $$('.blueprint-table-group').forEach((g) => {
        g.classList.remove('card-hovered-table');
      });
    });
  });

  // --- Módulo de Visión Computacional OpenCV (Cámara del Chef & Archivo) ---
  window.switchVisionTab = function (mode) {
    const isCam = mode === 'camera';
    const tabCam = $('#tab-camera');
    const tabUp = $('#tab-upload');
    const viewCam = $('#mode-camera-view');
    const viewUp = $('#mode-upload-view');

    if (tabCam && tabUp && viewCam && viewUp) {
      tabCam.classList.toggle('active', isCam);
      tabUp.classList.toggle('active', !isCam);
      viewCam.hidden = !isCam;
      viewUp.hidden = isCam;
      if (!isCam && window.chefCameraStream) {
        stopChefCamera();
      }
    }
  };

  let chefCameraStream = null;

  function stopChefCamera() {
    if (chefCameraStream) {
      chefCameraStream.getTracks().forEach((track) => track.stop());
      chefCameraStream = null;
    }
    const video = $('#camera-video');
    if (video) {
      video.srcObject = null;
      video.hidden = true;
      video.style.display = 'none';
    }
    const standby = $('#camera-standby-box');
    const hud = $('#camera-hud-box');
    const actions = $('#camera-actions-panel');
    if (standby) {
      standby.hidden = false;
      standby.style.display = 'flex';
    }
    if (hud) {
      hud.hidden = true;
      hud.style.display = 'none';
    }
    if (actions) {
      actions.hidden = true;
      actions.style.display = 'none';
    }
  }

  async function startChefCamera() {
    const video = $('#camera-video');
    const standby = $('#camera-standby-box');
    const hud = $('#camera-hud-box');
    const actions = $('#camera-actions-panel');

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      return toast('Tu navegador no soporta captura de cámara web.', 'error');
    }

    try {
      toast('Solicitando acceso a la cámara...', 'info');
      const constraints = {
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: { ideal: 'environment' }
        },
        audio: false
      };
      chefCameraStream = await navigator.mediaDevices.getUserMedia(constraints);
      if (standby) {
        standby.hidden = true;
        standby.style.display = 'none';
      }
      if (video) {
        video.srcObject = chefCameraStream;
        video.hidden = false;
        video.style.display = 'block';
        await video.play();
      }
      if (hud) {
        hud.hidden = false;
        hud.style.display = 'flex';
      }
      if (actions) {
        actions.hidden = false;
        actions.style.display = 'flex';
      }

      const resBadge = $('#hud-cam-res');
      if (resBadge && video) {
        video.addEventListener(
          'loadedmetadata',
          () => {
            resBadge.textContent = `${video.videoWidth}x${video.videoHeight}`;
          },
          { once: true }
        );
      }
      toast('Cámara del Chef transmitiendo en vivo.', 'success');
    } catch (err) {
      console.error('Error accediendo a cámara:', err);
      toast('No se pudo acceder a la cámara. Revisa los permisos de tu navegador.', 'error');
    }
  }

  function renderVisionResults(data) {
    $('#vision-placeholder').hidden = true;
    $('#vision-results').hidden = false;
    $('#vision-people').textContent = data.people_count;

    // Banner de Sincronización en Vivo con Dijkstra
    const syncAlert = $('#vision-sync-alert');
    const syncDesc = $('#vision-sync-desc');
    if (syncAlert && syncDesc) {
      syncAlert.hidden = false;
      const criticalCount = (data.updated_zones || []).filter(z => z.level === 'critica').length;
      if (criticalCount > 0) {
        syncAlert.className = 'vision-sync-banner sync-warning';
        syncDesc.textContent = `Se detectó alta densidad (${criticalCount} zona en alerta crítica). El motor de ruteo Dijkstra desviará automáticamente a los meseros para evitar cuellos de botella.`;
      } else {
        syncAlert.className = 'vision-sync-banner sync-success';
        syncDesc.textContent = data.sync_notice || 'Las zonas del salón han sido sincronizadas en tiempo real con la afluencia detectada por OpenCV.';
      }
    }

    // Estado de Almacenamiento en la Nube (AWS S3)
    const s3Badge = $('#vision-s3-status');
    if (s3Badge) {
      s3Badge.textContent = data.s3_status || (data.aws_saved ? '✓ Guardado en AWS S3' : 'Almacenamiento local');
      s3Badge.className = `vision-s3-badge ${data.aws_saved ? 's3-cloud-ok' : 's3-cloud-local'}`;
    }

    // Tarjetas de Distribución por Sectores y Zonas
    const zoneSectors = {
      'A': 'Salón Jardín',
      'B': 'Pasillo Central',
      'C': 'Salón Terraza'
    };

    $('#vision-zone-counts').replaceChildren(
      ...['A', 'B', 'C'].map((zoneCode) => {
        const count = data.zone_counts?.[zoneCode] || 0;
        const updated = (data.updated_zones || []).find(z => z.code === zoneCode);
        const level = updated ? updated.level : (count >= 3 ? 'critica' : count >= 1 ? 'moderada' : 'normal');

        const card = document.createElement('div');
        card.className = `vision-zone-stat-card level-${level}`;

        const top = document.createElement('div');
        top.className = 'vision-zone-top';

        const strong = document.createElement('strong');
        strong.textContent = `${count} pax`;

        const pill = document.createElement('span');
        pill.className = `zone-mini-pill pill-${level}`;
        pill.textContent = level === 'critica' ? 'Demora' : level === 'moderada' ? 'Fluido' : 'Rápido';

        top.append(strong, pill);

        const sub = document.createElement('div');
        sub.className = 'vision-zone-sub';
        sub.textContent = `Zona ${zoneCode} · ${zoneSectors[zoneCode] || ''}`;

        card.append(top, sub);
        return card;
      })
    );

    $('#vision-annotated').src = data.annotated_image;
    $('#vision-note').textContent = data.disclaimer;
    $('#vision-aws-warning').textContent = data.aws_warning || '';
  }

  $('#btn-start-camera')?.addEventListener('click', startChefCamera);
  $('#btn-stop-camera')?.addEventListener('click', stopChefCamera);

  $('#btn-capture-snapshot')?.addEventListener('click', async () => {
    const video = $('#camera-video');
    const container = $('#camera-stream-container');
    const btn = $('#btn-capture-snapshot');

    if (!video || !chefCameraStream || video.videoWidth === 0) {
      return toast('La cámara no está transmitiendo video.', 'error');
    }

    if (container) {
      container.classList.add('camera-flash');
      setTimeout(() => container.classList.remove('camera-flash'), 400);
    }

    btn.disabled = true;
    btn.innerHTML = '<span class="capture-icon">⏳</span> <span>Analizando fotograma con OpenCV…</span>';

    try {
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext('2d');
      if (!ctx) throw new Error('No se pudo iniciar el canvas de captura.');
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.90));
      if (!blob) throw new Error('No se pudo capturar el fotograma de la cámara.');

      const form = new FormData();
      form.append('file', blob, 'chef_cam_snapshot.jpg');

      const r = await fetch('/api/vision/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': csrf() },
        body: form,
      });

      const data = await r.json();
      if (!r.ok) throw new Error(data.error || 'No se pudo analizar la foto de la cámara.');

      renderVisionResults(data);
      toast('Fotograma analizado con éxito por OpenCV.', 'success');
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = '<span class="btn-cam-snap-icon">📸</span> <span>Capturar y Analizar con OpenCV</span> <span class="btn-arrow-right">→</span>';
    }
  });

  $('#image-file')?.addEventListener('change', (e) => {
    $('#upload-filename').textContent = e.target.files?.[0]?.name || 'Ningún archivo seleccionado';
  });

  $('#vision-form')?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const file = $('#image-file').files?.[0];
    if (!file) return toast('Selecciona una imagen.', 'error');
    if (file.size > 5 * 1024 * 1024) return toast('Máximo 5 MB por fotografía.', 'error');

    const btn = $('#vision-submit');
    btn.disabled = true;
    btn.textContent = 'Analizando imagen…';

    try {
      const form = new FormData();
      form.append('file', file);
      const r = await fetch('/api/vision/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': csrf() },
        body: form,
      });

      const data = await r.json();
      if (!r.ok) throw new Error(data.error || 'No se pudo analizar la foto.');

      renderVisionResults(data);
      toast('Análisis OpenCV completado.', 'success');
    } catch (err) {
      toast(err.message, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = 'Analizar Archivo con OpenCV <span>→</span>';
    }
  });

  // --- Gráficos de Barras de Indicadores ---
  const chart = $('.bar-chart');
  if (chart) {
    const values = chart.dataset.values.split(',').map(Number);
    const max = Math.max(...values, 1);
    $$('.bar-fill').forEach((b, i) => {
      b.style.height = `${values[i] === 0 ? 0 : Math.max(5, (values[i] / max) * 100)}%`;
    });
  }

  // --- Conmutador de Visibilidad de Contraseña (Eye Toggle) ---
  $$('[data-toggle-password]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const wrap = btn.closest('.password-pill-wrap, .password-field, .form-field-group');
      const field = wrap?.querySelector('input');
      if (!field) return;
      const isPass = field.type === 'password';
      field.type = isPass ? 'text' : 'password';
      btn.setAttribute('aria-label', isPass ? 'Ocultar contraseña' : 'Mostrar contraseña');
      btn.classList.toggle('is-active', isPass);
      btn.innerHTML = isPass
        ? '<svg class="icon-eye" viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24M1 1l22 22"/></svg>'
        : '<svg class="icon-eye" viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';
    });
  });

  // --- Carga Rápida de Tareas Asignadas (Mesero) ---
  $$('.btn-quick-load').forEach((btn) => {
    btn.addEventListener('click', () => {
      const orig = btn.dataset.origin;
      const dest = btn.dataset.dest;
      const taskType = btn.dataset.taskType;
      const routeId = btn.dataset.routeId;
      if (orig && $('#origin')) $('#origin').value = orig;
      if (dest && $('#destination')) $('#destination').value = dest;
      if (taskType && $('#task-type')) $('#task-type').value = taskType;
      if (routeId) lastRouteId = Number(routeId);
      toast('Tarea cargada en el mapa. Trazando recorrido...', 'info');
      requestRoute(false);
    });
  });

  // --- Dropdown de Notificaciones y Avisos Administrativos ---
  const notifTrigger = $('#btn-topbar-notif');
  const notifDropdown = $('#notif-dropdown');

  if (notifTrigger && notifDropdown) {
    notifTrigger.addEventListener('click', (e) => {
      e.stopPropagation();
      notifDropdown.classList.toggle('is-hidden');
    });

    document.addEventListener('click', (e) => {
      if (!e.target.closest('#topbar-notif-wrap')) {
        notifDropdown.classList.add('is-hidden');
      }
    });

    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') notifDropdown.classList.add('is-hidden');
    });
  }

  // Marcar notificación como leída asíncronamente
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('.btn-mark-read');
    if (!btn) return;
    const notifId = btn.dataset.notifId;
    if (!notifId) return;

    btn.disabled = true;
    try {
      await postJSON(`/api/notificaciones/${notifId}/leer/`, {});
      const row = btn.closest('.notif-item-row') || btn.closest('.profile-notif-card');
      if (row) {
        row.classList.add('is-read');
        btn.remove();
      }

      // Actualizar contador visual de notificaciones
      const badge = $('#notif-count-badge');
      if (badge) {
        const cur = Number(badge.textContent.trim()) || 0;
        const next = Math.max(0, cur - 1);
        badge.textContent = next;
        if (next === 0) {
          badge.classList.add('is-hidden');
        }
      }
      toast('Notificación marcada como revisada.', 'success');
    } catch (err) {
      btn.disabled = false;
      toast(err.message || 'No se pudo actualizar el aviso.', 'error');
    }
  });
})();

