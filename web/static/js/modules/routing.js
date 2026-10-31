/* OptiFlow Dining · Ruteo Dijkstra, atención sin duplicados y cierre reactivo de tareas asignadas. */
(() => {
  'use strict';

  const OptiFlow = (window.OptiFlow = window.OptiFlow || {});
  const { $, $$, escapeHtml, toast, postJSON, syncWaiterTopbarPill } = OptiFlow;

  let lastRouteId = null;

  /** Despliega el modal explicativo de congestión con evidencia fotográfica OpenCV. */
  function openCongestionModal(node) {
    const modal = $('#congestion-modal');
    const modalBody = $('#congestion-modal-body');
    const modalTitle = $('#congestion-modal-title');
    const modalSub = $('#congestion-modal-subtitle');
    if (!modal || !modalBody) return;

    const [x, y] = String(node).split(',').map(Number);
    const layout = OptiFlow.layoutData || OptiFlow.getLayout() || {};
    let zoneCode = 'B';
    for (const z of layout.zones || []) {
      if ((z.columns || []).map(Number).includes(x)) {
        zoneCode = String(z.id || 'B').toUpperCase();
        break;
      }
    }

    const metaByZone = {
      A: {
        name: 'Zona A · Salón Jardín',
        desc: 'Sector occidental de mesas bajas y acceso principal.',
      },
      B: {
        name: 'Zona B · Pasillo Central',
        desc: 'Pasillo neurálgico de conexión entre Cocina y los salones.',
      },
      C: {
        name: 'Zona C · Salón Terraza',
        desc: 'Sector oriental de mesas amplias y ventanales.',
      },
    };
    const meta = metaByZone[zoneCode] || metaByZone.B;

    if (modalTitle) modalTitle.textContent = `Alerta de Congestión: Nodo (${node})`;
    if (modalSub) modalSub.textContent = `${meta.name} · Estado Crítico Operativo`;

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
          <strong>Motivo de la Alerta:</strong> Alta afluencia peatonal en este pasillo, superando el límite seguro de tránsito para meseros.
        </p>
      </div>
      <div class="congestion-evidence-card">
        <div class="evidence-header">
          <div class="evidence-title">
            <span class="evidence-icon">📷</span>
            <strong>Evidencia Visual · Análisis OpenCV</strong>
          </div>
          <span class="evidence-tag">Afluencia: ${escapeHtml(peopleInZone)} en Sector ${escapeHtml(zoneCode)}</span>
        </div>
        <div class="evidence-image-frame">
          <img src="${escapeHtml(visionImgUrl)}" alt="Captura analizada por OpenCV" class="evidence-img">
          <div class="evidence-zone-overlay">
            <span>Sector analizado: <strong>${escapeHtml(meta.name)}</strong></span>
            <small>Detección computacional activa (${escapeHtml(totalPeople)} total)</small>
          </div>
        </div>
      </div>
      <div class="congestion-info-card">
        <div class="congestion-detail-row">
          <span class="detail-label">Sector Afectado:</span>
          <strong>${escapeHtml(meta.name)}</strong>
        </div>
        <div class="congestion-detail-row">
          <span class="detail-label">Ubicación en Red:</span>
          <code>Columna ${x}, Fila ${y} (${y === 2 ? 'Pasillo Central' : 'Pasillo Secundario'})</code>
        </div>
        <p class="congestion-desc">
          ${escapeHtml(meta.desc)} Cruzar por este nodo con bandejas implica riesgo de demoras o colisiones.
        </p>
      </div>
      <div class="congestion-recommendation-box">
        <strong>💡 Recomendación del Sistema:</strong>
        <p>Pulsa <strong>Recalcular ruta</strong> para que Dijkstra trace un desvío seguro dentro del plano.</p>
      </div>
    `;
    modal.classList.remove('is-hidden');
  }

  /** Cierra el modal explicativo de congestión. */
  function closeCongestionModal() {
    $('#congestion-modal')?.classList.add('is-hidden');
  }

  /** Renderiza la tarjeta de mensajería asistida en 3 partes bajo el formulario de rutas. */
  function feedback(title, message, type = 'success', actionHint = '') {
    const routeFeedback = $('#route-feedback');
    if (!routeFeedback) return;
    routeFeedback.hidden = false;
    routeFeedback.className = `route-feedback ${type}`;
    routeFeedback.innerHTML = `
      <div class="feedback-badge-row">
        <span class="feedback-icon">${type === 'success' ? '✔' : type === 'warning' ? '⚠' : '✖'}</span>
        <strong>${escapeHtml(title)}</strong>
      </div>
      <p class="feedback-body">${message}</p>
      ${actionHint ? `<div class="feedback-action-hint">💡 <span>${escapeHtml(actionHint)}</span></div>` : ''}
    `;
  }

  /** Limpia inmediatamente las alertas, tarjetas y píldoras tras finalizar una tarea asignada. */
  function applyTaskCompletedUI(routeId, data) {
    const idNum = Number(routeId);

    // 1. Actualizar píldora de estado en tablas de historial (Rutas y Perfil)
    const pill = $(`#status-pill-${idNum}`);
    if (pill) {
      pill.className = 'status-pill normal';
      pill.textContent = 'Finalizada';
    }
    const profilePill = $(`#profile-status-pill-${idNum}`);
    if (profilePill) {
      profilePill.className = 'status-pill normal';
      profilePill.textContent = 'Finalizada';
    }

    // 2. Retirar chip de tarea asignada en Rutas y actualizar/ocultar caja urgente
    const chip = $(`#assigned-chip-${idNum}`);
    if (chip) {
      chip.remove();
    }
    const box = $('#assigned-tasks-box') || $('.assigned-tasks-box');
    if (box) {
      const remainingChips = box.querySelectorAll('.assigned-task-chip').length;
      const nextCount = typeof data.pending_assigned_count === 'number'
        ? data.pending_assigned_count
        : remainingChips;
      if (nextCount <= 0 || remainingChips === 0) {
        box.remove();
      } else {
        const plural = nextCount === 1 ? '' : 's';
        const countTitle = $('#assigned-tasks-count-title') || box.querySelector('.assigned-tasks-header strong');
        if (countTitle) {
          countTitle.textContent = `Tienes ${nextCount} tarea${plural} asignada${plural}`;
        }
      }
    }

    // 3. Retirar tarjeta de asignación pendiente en Perfil y actualizar KPIs
    const profCard = $(`#profile-assigned-card-${idNum}`);
    if (profCard) {
      profCard.remove();
      const profList = $('#profile-assigned-list');
      if (profList && profList.querySelectorAll('.assigned-task-card').length === 0) {
        profList.innerHTML =
          '<div class="simple-empty-box compact-empty-box"><p>No tienes tareas asignadas pendientes en este momento.</p></div>';
      }
      const kpiPending = $('#kpi-profile-pending');
      if (kpiPending && typeof data.pending_assigned_count === 'number') {
        kpiPending.textContent = String(data.pending_assigned_count);
      }
      const kpiDone = $('#kpi-profile-completed');
      if (kpiDone) {
        kpiDone.textContent = String((Number(kpiDone.textContent) || 0) + 1);
      }
    }

    // 4. Actualizar o esconder píldora urgente del topbar en tiempo real
    if (typeof data.pending_assigned_count === 'number') {
      syncWaiterTopbarPill(data.pending_assigned_count);
    }

    // 5. Si era la ruta activa en el mapa, ocultar botones y limpiar recorrido activo
    if (lastRouteId === idNum) {
      lastRouteId = null;
      const actions = $('#route-actions');
      if (actions) actions.hidden = true;
      if ($('#floor-plan') && OptiFlow.layoutData) {
        OptiFlow.floorPlan(OptiFlow.layoutData, [], null, []);
      }
      feedback(
        'Tarea de servicio finalizada',
        escapeHtml(data.message || 'Tarea finalizada correctamente.'),
        'success',
        'El estado cambió a Finalizada y la alerta pendiente fue retirada.'
      );
    }
  }

  /** Finaliza en el servidor una ruta por ID y dispara la limpieza reactiva en la UI. */
  async function completeRouteById(routeId) {
    if (!routeId) {
      toast('Primero selecciona o calcula una ruta activa.', 'error');
      return;
    }
    try {
      const data = await postJSON(`/api/rutas/${routeId}/finalizar/`, {});
      applyTaskCompletedUI(routeId, data);
      toast(data.message || 'Tarea finalizada correctamente.', 'success');
    } catch (err) {
      toast(err.message || 'No se pudo finalizar la tarea.', 'error');
    }
  }

  /** Solicita el cálculo de una nueva ruta al backend y actualiza plano e historial. */
  async function requestRoute(avoid = false) {
    const btn = avoid ? $('#route-recalculate') : $('#route-submit');
    if (btn) btn.disabled = true;
    const layout = OptiFlow.layoutData || OptiFlow.getLayout();

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
      OptiFlow.floorPlan(layout, data.path, data.destination, data.congested_nodes);

      if (data.is_assigned && data.assigned_waiter_name) {
        feedback(
          `Ruta despachada a ${data.assigned_waiter_name}`,
          `Recorrido ${escapeHtml(data.origin.toUpperCase())} ➔ ${escapeHtml(data.destination.toUpperCase())} (${data.distance} tramos) enviado con estado Pendiente.`,
          'success',
          'Recibirás una notificación en la campana 🔔 en cuanto el mesero finalice la tarea.'
        );
      } else if (data.congested && !avoid) {
        feedback(
          'Se detectó congestión en el trayecto directo',
          `El recorrido cruza por nodos de alta afluencia (marcados con <strong>!</strong> en rojo). Distancia: ${data.distance} tramos.`,
          'warning',
          'Haz clic en los puntos rojos del mapa para ver motivos, o pulsa "↻ Recalcular ruta".'
        );
      } else if (avoid) {
        feedback(
          'Ruta alternativa optimizada con Dijkstra',
          `El trayecto fue recalculado dentro del salón evitando pasillos saturados. Distancia: ${data.distance} tramos.`,
          'success',
          'Ruta libre de cuellos de botella lista para atender.'
        );
      } else {
        feedback(
          'Ruta directa recomendada sin congestión',
          `Pasillos despejados entre ${escapeHtml(data.origin.toUpperCase())} y ${escapeHtml(data.destination.toUpperCase())}. Distancia: ${data.distance} tramos.`,
          'success',
          'Camino óptimo verificado dentro de las dimensiones del salón.'
        );
      }

      const tbody = $('#recent-routes-tbody');
      if (tbody) {
        $('#empty-routes-row')?.remove();
        const tr = document.createElement('tr');
        tr.id = `route-row-${data.route_id}`;
        tr.className = 'newly-added-row';
        const assignedBadge = data.assigned_waiter_name
          ? `<span class="badge-role-tag badge-assigned">Asignado: ${escapeHtml(data.assigned_waiter_name)}</span>`
          : '<span class="badge-role-tag badge-self">Auto-atención</span>';
        const statusLabel = data.status_label || (data.is_assigned ? 'Pendiente' : 'En curso');

        tr.innerHTML = `
          <td><strong>${escapeHtml((data.destination_label || data.destination).toUpperCase())}</strong></td>
          <td>${escapeHtml(data.task_type_display || 'Entrega de comida')}</td>
          <td>${assignedBadge}</td>
          <td>${escapeHtml(data.created_at || 'Hace un momento')}</td>
          <td>
            <span id="status-pill-${data.route_id}" class="status-pill moderada">${escapeHtml(statusLabel)}</span>
          </td>
        `;
        tbody.prepend(tr);
      }

      $('#route-actions').hidden = false;
      $('#route-complete').hidden = Boolean(data.is_assigned);
      $('#route-recalculate').hidden = avoid || !data.congested;
      toast(
        data.is_assigned
          ? `Tarea asignada a ${data.assigned_waiter_name}.`
          : avoid
            ? 'Ruta alternativa calculada sin demoras.'
            : 'Ruta calculada con éxito.',
        'success'
      );
    } catch (error) {
      feedback(
        'No se pudo completar el trazado de la ruta',
        escapeHtml(error.message || 'El motor de ruteo no pudo calcular una trayectoria válida.'),
        'error',
        'Verifica que las mesas estén dentro de las dimensiones activas o pulsa "Recalcular ruta".'
      );
      if ($('#route-actions')) $('#route-actions').hidden = false;
      if ($('#route-recalculate')) $('#route-recalculate').hidden = false;
      if ($('#route-complete')) $('#route-complete').hidden = true;
      toast(error.message, 'error');
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  /** Inicializa eventos de ruteo, atención directa de asignaciones sin duplicar y modal de alertas. */
  function initRouting() {
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

    $('#route-form')?.addEventListener('submit', (e) => {
      e.preventDefault();
      requestRoute(false);
    });

    $('#route-recalculate')?.addEventListener('click', () => requestRoute(true));

    $('#route-complete')?.addEventListener('click', () => {
      completeRouteById(lastRouteId);
    });

    // Cargar tarea asignada en el mapa SIN crear ruta duplicada (conserva el ID real asignado)
    document.addEventListener('click', (e) => {
      const loadBtn = e.target.closest('.btn-quick-load');
      if (loadBtn) {
        const orig = loadBtn.dataset.origin;
        const dest = loadBtn.dataset.dest;
        const taskType = loadBtn.dataset.taskType;
        const routeId = Number(loadBtn.dataset.routeId);
        const distance = Number(loadBtn.dataset.distance || 0);
        const isRecalc = loadBtn.dataset.recalculated === 'true';
        const assigner = loadBtn.dataset.assigner || 'Supervisión';

        let savedPath = [];
        try {
          savedPath = JSON.parse(loadBtn.dataset.path || '[]');
        } catch (_) {
          savedPath = [];
        }

        if (orig && $('#origin')) $('#origin').value = orig;
        if (dest && $('#destination')) $('#destination').value = dest;
        if (taskType && $('#task-type')) $('#task-type').value = taskType;

        $$('.assigned-task-chip').forEach((c) => c.classList.remove('is-attending'));
        loadBtn.closest('.assigned-task-chip')?.classList.add('is-attending');

        if (routeId && savedPath.length > 0) {
          lastRouteId = routeId;
          const layout = OptiFlow.layoutData || OptiFlow.getLayout();
          OptiFlow.floorPlan(layout, savedPath, dest, []);
          feedback(
            `Atendiendo tarea asignada · ${(dest || '').toUpperCase()}`,
            `Despachada por <strong>${escapeHtml(assigner)}</strong> (${distance || savedPath.length - 1} tramos${isRecalc ? ' · 🛡️ Ruta Segura' : ''}).`,
            'success',
            'Cuando entregues o retires el servicio, pulsa "✓ Finalizar tarea" para cerrar la alerta y avisar al supervisor.'
          );
          if ($('#route-actions')) $('#route-actions').hidden = false;
          if ($('#route-complete')) $('#route-complete').hidden = false;
          if ($('#route-recalculate')) $('#route-recalculate').hidden = true;
          $('#floor-plan')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
          toast('Ruta asignada cargada en el mapa. Pulsa "Finalizar tarea" al concluir.', 'info');
        } else {
          requestRoute(isRecalc);
        }
        return;
      }

      // Botón directo para finalizar tarea desde la tarjeta de asignación urgente o perfil
      const doneBtn = e.target.closest('.btn-complete-assigned');
      if (doneBtn) {
        const routeId = Number(doneBtn.dataset.routeId);
        if (routeId) {
          doneBtn.disabled = true;
          completeRouteById(routeId).finally(() => {
            doneBtn.disabled = false;
          });
        }
      }
    });
  }

  Object.assign(OptiFlow, {
    openCongestionModal,
    closeCongestionModal,
    completeRouteById,
    requestRoute,
    initRouting,
  });
})();

