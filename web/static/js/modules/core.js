/* OptiFlow Dining · Módulo Base: utilidades DOM, CSRF, notificaciones, modales y navegación. */
(() => {
  'use strict';

  const OptiFlow = (window.OptiFlow = window.OptiFlow || {});
  const SVGNS = 'http://www.w3.org/2000/svg';

  /** Selecciona el primer elemento coincidente en el DOM. */
  const $ = (selector, root = document) => root.querySelector(selector);

  /** Selecciona todos los elementos coincidentes como arreglo. */
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

  /** Escapa caracteres especiales HTML para inserción segura en plantillas cliente. */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = String(text ?? '');
    return div.innerHTML;
  }

  /** Obtiene el token CSRF activo desde la etiqueta meta o la cookie csrftoken. */
  function csrf() {
    return (
      document.querySelector('meta[name="csrf-token"]')?.content ||
      (document.cookie.match(/(?:^|; )csrftoken=([^;]*)/) || [])[1] ||
      ''
    );
  }

  let toastTimer = null;

  /** Muestra un aviso flotante temporal tipo toast en la esquina de la interfaz. */
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
    }, 4500);
  }

  /** Ejecuta una petición POST JSON autenticada con credenciales de sesión y CSRF. */
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

  /** Construye un nodo SVG con atributos tipados y texto opcional. */
  function svg(tag, attributes = {}, textContent = '') {
    const el = document.createElementNS(SVGNS, tag);
    Object.entries(attributes).forEach(([k, v]) => el.setAttribute(k, String(v)));
    if (textContent) {
      el.textContent = textContent;
    }
    return el;
  }

  /** Deserializa la configuración topológica del salón embebida en la página. */
  function getLayout() {
    try {
      const el = $('#floor-layout');
      return el ? JSON.parse(el.textContent) : null;
    } catch (_) {
      return null;
    }
  }

  /** Actualiza en tiempo real la píldora de tareas urgentes del mesero en el topbar. */
  function syncWaiterTopbarPill(pendingCount) {
    const count = Math.max(0, Number(pendingCount) || 0);
    const pill = $('#waiter-urgent-pill') || $('.waiter-urgent-topbar-pill');
    if (!pill) return;

    if (count === 0) {
      pill.classList.add('is-hidden');
      pill.style.display = 'none';
      return;
    }

    pill.classList.remove('is-hidden');
    pill.style.display = '';
    const plural = count === 1 ? '' : 's';
    pill.title = `Tienes ${count} tarea${plural} asignada${plural} pendiente${plural}`;
    const txt = pill.querySelector('.waiter-urgent-text');
    if (txt) {
      txt.textContent = `⚡ ${count} tarea${plural} urgente${plural}`;
    }
  }

  /** Refresca silenciosamente el contador de avisos del supervisor o alertas del mesero. */
  async function refreshTopbarAlerts() {
    if (document.hidden) return;
    const hasNotifWrap = Boolean($('#topbar-notif-wrap'));
    const hasWaiterPill = Boolean($('#waiter-urgent-pill') || $('.waiter-urgent-topbar-pill'));
    if (!hasNotifWrap && !hasWaiterPill) return;

    try {
      const r = await fetch('/api/notificaciones/resumen/', { credentials: 'same-origin' });
      if (!r.ok) return;
      const data = await r.json();

      if (typeof data.unread_count === 'number') {
        let badge = $('#notif-count-badge');
        const btn = $('#btn-topbar-notif');
        if (!badge && btn && data.unread_count > 0) {
          badge = document.createElement('span');
          badge.className = 'notif-count-badge';
          badge.id = 'notif-count-badge';
          btn.appendChild(badge);
        }
        if (badge) {
          badge.textContent = String(data.unread_count);
          badge.classList.toggle('is-hidden', data.unread_count === 0);
        }
        const subCount = $('.notif-sub-count');
        if (subCount) {
          subCount.textContent = `${data.unread_count} pendientes`;
        }
        const listEl = $('#notif-dropdown-list');
        if (listEl && Array.isArray(data.items)) {
          if (data.items.length === 0) {
            listEl.innerHTML = '<div class="notif-empty-state">No hay avisos pendientes.</div>';
          } else {
            listEl.innerHTML = data.items
              .map(
                (n) => `
                <div class="notif-item-row" id="notif-item-${n.id}">
                  <div class="notif-item-text">
                    <strong>${escapeHtml(n.title)}</strong>
                    <p>${escapeHtml(n.message)}</p>
                    <small>${escapeHtml(n.ago)}</small>
                  </div>
                  <button type="button" class="btn-mark-read" data-notif-id="${n.id}" title="Marcar como leída">✔</button>
                </div>`
              )
              .join('');
          }
        }
      } else if (typeof data.waiter_pending_count === 'number') {
        syncWaiterTopbarPill(data.waiter_pending_count);
      }
    } catch (_) {
      // Silencioso en caso de desconexión temporal
    }
  }

  /** Inicializa navegación lateral, contraseñas, avisos, QR LAN, gráficos y roles. */
  function initCore() {
    $('#menu-trigger')?.addEventListener('click', () => $('#sidebar')?.classList.toggle('open'));
    $('#sidebar-backdrop')?.addEventListener('click', () => $('#sidebar')?.classList.remove('open'));
    document.addEventListener('click', (e) => {
      if (!e.target.closest('.sidebar') && !e.target.closest('#menu-trigger')) {
        $('#sidebar')?.classList.remove('open');
      }
      const overlay = e.target.classList?.contains('cad-modal-overlay') ? e.target : null;
      if (overlay) {
        overlay.classList.add('is-hidden');
      }
    });

    // Conmutador de visibilidad de contraseñas
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

    // Cierre genérico de modales por atributo data-close
    $$('[data-close]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const modalId = btn.dataset.close;
        $(`#${modalId}`)?.classList.add('is-hidden');
      });
    });

    // Dropdown de notificaciones para supervisores (Admin, Capitán, Gerente)
    const notifTrigger = $('#btn-topbar-notif');
    const notifDropdown = $('#notif-dropdown');
    if (notifTrigger && notifDropdown) {
      notifTrigger.addEventListener('click', (e) => {
        e.stopPropagation();
        notifDropdown.classList.toggle('is-hidden');
        if (!notifDropdown.classList.contains('is-hidden')) {
          refreshTopbarAlerts();
        }
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

    // Marcar aviso como leído de forma asíncrona
    document.addEventListener('click', async (e) => {
      const btn = e.target.closest('.btn-mark-read');
      if (!btn) return;
      const notifId = btn.dataset.notifId;
      if (!notifId) return;

      btn.disabled = true;
      try {
        const res = await postJSON(`/api/notificaciones/${notifId}/leer/`, {});
        const row = btn.closest('.notif-item-row') || btn.closest('.profile-notif-card');
        if (row) {
          row.classList.add('is-read');
          row.classList.remove('unread-glow');
          btn.remove();
        }

        const badge = $('#notif-count-badge');
        if (badge) {
          const next = typeof res.unread_count === 'number'
            ? res.unread_count
            : Math.max(0, (Number(badge.textContent.trim()) || 0) - 1);
          badge.textContent = String(next);
          badge.classList.toggle('is-hidden', next === 0);
          const subCount = $('.notif-sub-count');
          if (subCount) subCount.textContent = `${next} pendientes`;
        }
        toast('Notificación marcada como revisada.', 'success');
      } catch (err) {
        btn.disabled = false;
        toast(err.message || 'No se pudo actualizar el aviso.', 'error');
      }
    });

    // Conectividad LAN Móvil / Tablet
    $('#btn-open-lan-modal')?.addEventListener('click', () => {
      $('#modal-lan-connect')?.classList.remove('is-hidden');
    });

    $('#btn-copy-lan-url')?.addEventListener('click', () => {
      const urlText = $('#lan-url-display')?.textContent?.trim();
      if (urlText && navigator.clipboard) {
        navigator.clipboard.writeText(urlText).then(() => {
          toast(`Enlace copiado al portapapeles: ${urlText}`, 'success');
        }).catch(() => {
          toast(`Enlace: ${urlText}`, 'info');
        });
      } else if (urlText) {
        toast(`Enlace: ${urlText}`, 'info');
      }
    });

    // Gestión blindada de roles de personal (Admin)
    document.addEventListener('click', async (e) => {
      const btn = e.target.closest('.btn-save-role');
      if (!btn) return;
      const userId = btn.dataset.userId;
      if (!userId) return;

      const select = $(`#role-select-${userId}`);
      if (!select) return;
      const newRole = select.value;

      btn.disabled = true;
      btn.textContent = 'Guardando...';
      try {
        const res = await postJSON(`/api/usuarios/${userId}/rol/`, { role: newRole });
        toast(res.message, 'success');
        const pill = $(`#user-role-pill-${userId}`);
        if (pill) {
          pill.textContent = res.new_role_display;
          pill.className = `status-pill ${newRole === 'admin' || newRole === 'gerente' ? 'critica' : newRole === 'capitan' ? 'moderada' : 'normal'}`;
        }
      } catch (err) {
        toast(err.message || 'No se pudo actualizar el rol.', 'error');
      } finally {
        btn.disabled = false;
        btn.textContent = 'Guardar ➔';
      }
    });

    // Gráficos de barras en analítica
    const chart = $('.bar-chart');
    if (chart && chart.dataset.values) {
      const values = chart.dataset.values.split(',').map(Number);
      const max = Math.max(...values, 1);
      $$('.bar-fill').forEach((b, i) => {
        b.style.height = `${values[i] === 0 ? 0 : Math.max(5, (values[i] / max) * 100)}%`;
      });
    }

    // Sondeo ligero cada 12s para avisos de tareas finalizadas o nuevas asignaciones
    if ($('#topbar-notif-wrap') || $('#waiter-urgent-pill') || $('.waiter-urgent-topbar-pill')) {
      setInterval(refreshTopbarAlerts, 12000);
    }
  }

  Object.assign(OptiFlow, {
    $,
    $$,
    SVGNS,
    escapeHtml,
    csrf,
    toast,
    postJSON,
    svg,
    getLayout,
    syncWaiterTopbarPill,
    refreshTopbarAlerts,
    initCore,
  });
})();

