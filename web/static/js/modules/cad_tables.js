/* OptiFlow Dining · Gestión CAD de Mesas, Dimensiones Estrictas y Reubicación Automática por Zona. */
(() => {
  'use strict';

  const OptiFlow = (window.OptiFlow = window.OptiFlow || {});
  const { $, $$, toast, postJSON } = OptiFlow;

  /** Recalcula en tiempo real los contadores KPI y filtros de estado en Plano y Mesas. */
  function updateLayoutKPIs() {
    if (!window.currentTableStates) return;
    const vals = Object.values(window.currentTableStates);
    const avail = vals.filter((v) => v === 'disponible').length;
    const active = vals.filter((v) => v === 'activa').length;
    const occupied = vals.filter((v) => v === 'ocupada').length;
    const total = vals.length || 1;
    const pct = Math.round(((active + occupied) / total) * 100);

    if ($('#kpi-available-tables')) $('#kpi-available-tables').textContent = String(avail);
    if ($('#kpi-active-tables')) $('#kpi-active-tables').textContent = String(active);
    if ($('#kpi-occupied-tables')) $('#kpi-occupied-tables').textContent = String(occupied);
    if ($('#kpi-occupancy-sub')) $('#kpi-occupancy-sub').textContent = `${pct}% de ocupación`;

    if ($('#count-filter-all')) $('#count-filter-all').textContent = String(vals.length);
    if ($('#count-filter-disponible')) $('#count-filter-disponible').textContent = String(avail);
    if ($('#count-filter-activa')) $('#count-filter-activa').textContent = String(active);
    if ($('#count-filter-ocupada')) $('#count-filter-ocupada').textContent = String(occupied);
  }

  /** Resuelve la zona (A, B o C) propietaria de una columna X según el layout activo. */
  function inferZoneFromColumn(colX) {
    const layout = OptiFlow.layoutData || OptiFlow.getLayout() || {};
    for (const z of layout.zones || []) {
      if ((z.columns || []).map(Number).includes(colX)) {
        return String(z.id || 'A').toUpperCase();
      }
    }
    return null;
  }

  /** Muestra un banner de error visible dentro del modal CAD activo además del toast. */
  function showModalError(modalEl, message) {
    if (!modalEl) return;
    let box = modalEl.querySelector('.cad-inline-error');
    if (!box) {
      box = document.createElement('div');
      box.className = 'cad-inline-error';
      box.setAttribute('role', 'alert');
      const form = modalEl.querySelector('form') || modalEl.querySelector('.cad-modal-content');
      form?.prepend(box);
    }
    box.textContent = `⚠ ${message}`;
    box.hidden = false;
  }

  /** Oculta el banner de error previo de un modal CAD al abrirlo o reintentar. */
  function clearModalError(modalEl) {
    const box = modalEl?.querySelector('.cad-inline-error');
    if (box) {
      box.textContent = '';
      box.hidden = true;
    }
  }

  /** Inicializa controles de estado, filtros, modales CAD, límites y reubicación zonal. */
  function initCadTables() {
    const layout = OptiFlow.layoutData || OptiFlow.getLayout();

    // Cambio en vivo del estado operativo de una mesa
    $$('.table-status-select').forEach((select) =>
      select.addEventListener('change', async () => {
        const code = select.dataset.code;
        const newState = select.value;
        const prevClass = select.className;

        try {
          await postJSON(`/api/mesas/${code}/`, { state: newState });
          if (!window.currentTableStates) window.currentTableStates = {};
          window.currentTableStates[code] = newState;

          OptiFlow.floorPlan(layout, [], null, [], window.currentTableStates);

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
          updateLayoutKPIs();
          toast(`${code.toUpperCase()} actualizada a ${newState.toUpperCase()}.`, 'success');
        } catch (err) {
          select.className = prevClass;
          toast(err.message, 'error');
        }
      })
    );

    // Filtros rápidos de mesas por estado
    $$('#table-filter-group .table-filter-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        $$('#table-filter-group .table-filter-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        const filter = btn.dataset.filter;
        $$('.table-state-card').forEach((card) => {
          card.style.display = filter === 'all' || card.dataset.state === filter ? '' : 'none';
        });
      });
    });

    // Resaltado bidireccional tarjeta <-> SVG
    $$('.table-state-card').forEach((card) => {
      card.addEventListener('mouseenter', () => {
        const code = card.dataset.code;
        $$('.blueprint-table-group').forEach((g) => {
          g.classList.toggle('card-hovered-table', g.dataset.tableId === code);
        });
      });
      card.addEventListener('mouseleave', () => {
        $$('.blueprint-table-group').forEach((g) => g.classList.remove('card-hovered-table'));
      });
    });

    const modalCreate = $('#modal-create-table');
    const modalUnify = $('#modal-unify-tables');
    const modalMove = $('#modal-move-table');
    const modalDims = $('#modal-dimensions');

    $('#btn-open-create-table')?.addEventListener('click', () => {
      clearModalError(modalCreate);
      if ($('#new-table-node') && !$('#new-table-node').value) {
        $('#new-table-node').value = 'auto';
      }
      modalCreate?.classList.remove('is-hidden');
    });

    $('#btn-open-unify-modal')?.addEventListener('click', () => {
      clearModalError(modalUnify);
      modalUnify?.classList.remove('is-hidden');
    });

    $('#btn-open-dimensions-modal')?.addEventListener('click', () => {
      clearModalError(modalDims);
      modalDims?.classList.remove('is-hidden');
    });

    // Abrir modal de reubicar mesa preservando zona y nodo de origen
    $$('.btn-move-table').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        clearModalError(modalMove);
        const code = btn.dataset.code || '';
        const node = btn.dataset.node || '';
        const label = btn.dataset.label || code;
        const zone = (btn.dataset.zone || 'A').toUpperCase();

        if (modalMove) {
          modalMove.dataset.origNode = node;
          modalMove.dataset.origZone = zone;
        }
        if ($('#move-table-code')) $('#move-table-code').value = code;
        if ($('#move-table-node')) $('#move-table-node').value = node;
        if ($('#move-table-zone')) $('#move-table-zone').value = zone;
        if ($('#move-modal-title')) $('#move-modal-title').textContent = `⚙️ Reubicar ${label}`;
        const hint = $('#move-zone-auto-hint');
        if (hint) {
          hint.textContent = "Cambia la Zona para reubicar automáticamente en un sitio libre o escribe 'X,Y'.";
        }
        modalMove?.classList.remove('is-hidden');
      });
    });

    // Al cambiar la Zona en el modal de reubicación, activar nodo 'auto' en esa nueva zona
    $('#move-table-zone')?.addEventListener('change', (e) => {
      clearModalError(modalMove);
      const newZone = e.target.value;
      const origZone = modalMove?.dataset.origZone || '';
      const origNode = modalMove?.dataset.origNode || '';
      const nodeInput = $('#move-table-node');
      const hint = $('#move-zone-auto-hint');

      if (nodeInput) {
        if (newZone !== origZone) {
          nodeInput.value = 'auto';
          if (hint) {
            hint.textContent = `Se moverá físicamente al primer espacio libre de la Zona ${newZone}.`;
          }
        } else {
          nodeInput.value = origNode;
          if (hint) {
            hint.textContent = "Cambia la Zona para reubicar automáticamente en un sitio libre o escribe 'X,Y'.";
          }
        }
      }
    });

    // Si el usuario escribe manualmente coordenadas X,Y, sincronizar el selector de Zona
    $('#move-table-node')?.addEventListener('input', (e) => {
      clearModalError(modalMove);
      const val = e.target.value.trim();
      const parts = val.split(',');
      if (parts.length === 2 && !Number.isNaN(Number(parts[0])) && parts[0].trim() !== '') {
        const matchedZone = inferZoneFromColumn(Number(parts[0].trim()));
        if (matchedZone && $('#move-table-zone')) {
          $('#move-table-zone').value = matchedZone;
        }
      }
    });

    // Si en Crear Mesa escribe coordenadas X,Y explícitas, sincronizar Zona automáticamente
    $('#new-table-node')?.addEventListener('input', (e) => {
      clearModalError(modalCreate);
      const val = e.target.value.trim();
      const parts = val.split(',');
      if (parts.length === 2 && !Number.isNaN(Number(parts[0])) && parts[0].trim() !== '') {
        const matchedZone = inferZoneFromColumn(Number(parts[0].trim()));
        if (matchedZone && $('#new-table-zone')) {
          $('#new-table-zone').value = matchedZone;
        }
      }
    });

    $('#new-table-zone')?.addEventListener('change', () => {
      clearModalError(modalCreate);
      const nodeEl = $('#new-table-node');
      if (nodeEl && nodeEl.value.trim() && nodeEl.value.trim().toLowerCase() !== 'auto') {
        const parts = nodeEl.value.split(',');
        const matched = inferZoneFromColumn(Number(parts[0]));
        if (matched && matched !== $('#new-table-zone').value) {
          nodeEl.value = 'auto';
        }
      }
    });

    // Suma dinámica de asientos en unificación
    const unifyBoxes = $$('input[name="unify_tables"]');
    const unifySeatsDisplay = $('#unify-total-seats');
    unifyBoxes.forEach((chk) => {
      chk.addEventListener('change', () => {
        let total = 0;
        unifyBoxes.forEach((c) => {
          if (c.checked) total += Number(c.dataset.seats) || 0;
        });
        if (unifySeatsDisplay) unifySeatsDisplay.textContent = `${total} personas`;
      });
    });

    // Crear nueva mesa CAD
    $('#form-create-table')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      clearModalError(modalCreate);
      const code = $('#new-table-code').value.trim();
      const label = $('#new-table-label').value.trim();
      const seats = Number($('#new-table-seats').value);
      const zone = $('#new-table-zone').value;
      const node = $('#new-table-node').value.trim() || 'auto';

      try {
        const res = await postJSON('/api/mesas/crear/', { code, label, seats, zone, node });
        toast(res.message, 'success');
        modalCreate?.classList.add('is-hidden');
        setTimeout(() => location.reload(), 650);
      } catch (err) {
        const msg = err.message || 'Error al crear la mesa.';
        showModalError(modalCreate, msg);
        toast(msg, 'error');
      }
    });

    // Unificar mesas
    $('#form-unify-tables')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      clearModalError(modalUnify);
      const checked = unifyBoxes.filter((c) => c.checked).map((c) => c.value);
      if (checked.length < 2) {
        const msg = 'Selecciona al menos 2 mesas para fusionar.';
        showModalError(modalUnify, msg);
        toast(msg, 'error');
        return;
      }
      const label = $('#unify-result-label').value;

      try {
        const res = await postJSON('/api/mesas/unificar/', {
          table_codes: checked,
          unified_label: label,
        });
        toast(res.message, 'success');
        modalUnify?.classList.add('is-hidden');
        setTimeout(() => location.reload(), 650);
      } catch (err) {
        const msg = err.message || 'Error al unificar mesas.';
        showModalError(modalUnify, msg);
        toast(msg, 'error');
      }
    });

    // Reubicar mesa por coordenadas o cambio físico de Zona
    $('#form-move-table')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      clearModalError(modalMove);
      const code = $('#move-table-code').value;
      const node = $('#move-table-node').value.trim() || 'auto';
      const zone = $('#move-table-zone').value;

      try {
        const res = await postJSON(`/api/mesas/${code}/mover/`, { node, zone });
        toast(res.message, 'success');
        modalMove?.classList.add('is-hidden');
        setTimeout(() => location.reload(), 650);
      } catch (err) {
        const msg = err.message || 'Error al reubicar la mesa.';
        showModalError(modalMove, msg);
        toast(msg, 'error');
      }
    });

    // Separar mesa unificada
    $$('.btn-separate-table').forEach((btn) => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const code = btn.dataset.code;
        const label = btn.dataset.label || code;
        if (!confirm(`¿Deseas desunificar '${label}' y restaurar sus mesas originales?`)) {
          return;
        }
        try {
          const res = await postJSON('/api/mesas/separar/', { code });
          toast(res.message, 'success');
          setTimeout(() => location.reload(), 650);
        } catch (err) {
          toast(err.message || 'Error al separar la mesa.', 'error');
        }
      });
    });

    // Guardar dimensiones estrictas del salón CAD
    $('#form-dimensions')?.addEventListener('submit', async (e) => {
      e.preventDefault();
      clearModalError(modalDims);
      const columns = Number($('#dim-columns').value);
      const rows = Number($('#dim-rows').value);
      try {
        const res = await postJSON('/api/plano/dimensiones/', { columns, rows });
        toast(res.message, 'success');
        modalDims?.classList.add('is-hidden');
        setTimeout(() => location.reload(), 650);
      } catch (err) {
        const msg = err.message || 'Error al actualizar dimensiones del salón.';
        showModalError(modalDims, msg);
        toast(msg, 'error');
      }
    });
  }

  Object.assign(OptiFlow, {
    updateLayoutKPIs,
    initCadTables,
  });
})();

