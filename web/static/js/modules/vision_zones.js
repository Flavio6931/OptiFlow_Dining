/* OptiFlow Dining · Saturación de Zonas y Visión Computacional OpenCV (Chef Cam & S3). */
(() => {
  'use strict';

  const OptiFlow = (window.OptiFlow = window.OptiFlow || {});
  const { $, $$, escapeHtml, csrf, toast, postJSON } = OptiFlow;

  let chefCameraStream = null;

  // --- Detección en vivo con YOLOX (microservicio OpenCV vía /api/vision/en-vivo/) ---------
  // Cada modo: ancho del fotograma enviado y etiqueta. El servidor usa YOLOX a 416 px (rápido),
  // 640 px (normal) o 640 px + mosaico (preciso); enviar más píxeles de los que usa solo gasta red.
  const LIVE_MODES = {
    rapido: { width: 640, label: '⚡ Rápido', name: 'rápido' },
    normal: { width: 960, label: '⚖️ Normal', name: 'normal' },
    preciso: { width: 960, label: '🎯 Preciso', name: 'preciso' },
  };
  const LIVE_MODE_ORDER = ['rapido', 'normal', 'preciso'];
  const LIVE_MIN_INTERVAL_MS = 60; // el ritmo lo marca la respuesta (un fotograma en vuelo)
  const LIVE_JPEG_QUALITY = 0.7;
  const LIVE_MATCH_DISTANCE = 0.12; // distancia normalizada para reconocer la misma persona
  const LIVE_MODE_KEY = 'optiflow.liveMode';

  let liveSession = 0; // se incrementa al encender/apagar: invalida respuestas atrasadas
  let liveTimer = 0;
  let liveErrors = 0;
  let liveFrameCanvas = null;
  let liveMode = 'rapido';
  try {
    const saved = localStorage.getItem(LIVE_MODE_KEY);
    if (LIVE_MODES[saved]) liveMode = saved;
  } catch (_) {
    /* almacenamiento no disponible: se queda en rápido */
  }

  // Animación de las cajas entre una respuesta y la siguiente
  let shownBoxes = [];
  let liveAnimFrame = 0;
  let liveFpsAvg = 0;

  function renderLiveModeButton() {
    const btn = $('#btn-live-mode');
    if (!btn) return;
    btn.textContent = LIVE_MODES[liveMode].label;
    btn.dataset.mode = liveMode;
    btn.setAttribute('aria-label', `Modo de detección en vivo: ${LIVE_MODES[liveMode].name}. Pulsa para cambiar.`);
  }

  function cycleLiveMode() {
    liveMode = LIVE_MODE_ORDER[(LIVE_MODE_ORDER.indexOf(liveMode) + 1) % LIVE_MODE_ORDER.length];
    try {
      localStorage.setItem(LIVE_MODE_KEY, liveMode);
    } catch (_) {
      /* sin almacenamiento: el cambio vale solo para esta visita */
    }
    liveFpsAvg = 0;
    renderLiveModeButton();
  }

  /** Reduce el fotograma actual al ancho del modo y lo codifica en JPEG. */
  function grabLiveFrame(video) {
    const scale = Math.min(1, LIVE_MODES[liveMode].width / video.videoWidth);
    liveFrameCanvas = liveFrameCanvas || document.createElement('canvas');
    liveFrameCanvas.width = Math.round(video.videoWidth * scale);
    liveFrameCanvas.height = Math.round(video.videoHeight * scale);
    liveFrameCanvas.getContext('2d').drawImage(video, 0, 0, liveFrameCanvas.width, liveFrameCanvas.height);
    return new Promise((resolve) => liveFrameCanvas.toBlob(resolve, 'image/jpeg', LIVE_JPEG_QUALITY));
  }

  /** Ajusta el lienzo superpuesto al tamaño mostrado (con densidad de píxeles) y lo limpia. */
  function prepareLiveOverlay() {
    const overlay = $('#camera-live-overlay');
    if (!overlay) return null;
    const dpr = window.devicePixelRatio || 1;
    const w = overlay.clientWidth;
    const h = overlay.clientHeight;
    if (overlay.width !== Math.round(w * dpr) || overlay.height !== Math.round(h * dpr)) {
      overlay.width = Math.round(w * dpr);
      overlay.height = Math.round(h * dpr);
    }
    const ctx = overlay.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    return { ctx, w, h };
  }

  /**
   * Dibuja las cajas (normalizadas 0-1 respecto al fotograma) sobre el vídeo. El vídeo usa
   * object-fit: cover, así que se aplica el mismo escalado y recorte centrado. `alphas` permite
   * que las personas recién aparecidas entren con un fundido.
   */
  function drawLiveBoxes(video, boxes, alphas = []) {
    const target = prepareLiveOverlay();
    if (!target || !video.videoWidth) return;
    const { ctx, w, h } = target;
    const scale = Math.max(w / video.videoWidth, h / video.videoHeight);
    const shownW = video.videoWidth * scale;
    const shownH = video.videoHeight * scale;
    const offX = (w - shownW) / 2;
    const offY = (h - shownH) / 2;

    // Divisiones de las zonas A/B/C, igual que en la imagen anotada del análisis
    ctx.strokeStyle = 'rgba(230, 200, 70, 0.45)';
    ctx.lineWidth = 1;
    ctx.setLineDash([6, 6]);
    [1 / 3, 2 / 3].forEach((f) => {
      ctx.beginPath();
      ctx.moveTo(offX + shownW * f, 0);
      ctx.lineTo(offX + shownW * f, h);
      ctx.stroke();
    });
    ctx.setLineDash([]);

    ctx.font = '600 11px Inter, system-ui, sans-serif';
    boxes.forEach(([nx, ny, nw, nh, score], i) => {
      const x = offX + nx * shownW;
      const y = offY + ny * shownH;
      const bw = nw * shownW;
      const bh = nh * shownH;
      ctx.globalAlpha = alphas[i] ?? 1;
      ctx.shadowColor = 'rgba(255, 123, 61, 0.9)';
      ctx.shadowBlur = 8;
      ctx.strokeStyle = '#ff7b3d';
      ctx.lineWidth = 2.5;
      ctx.beginPath();
      ctx.roundRect(x, y, bw, bh, 8);
      ctx.stroke();
      ctx.shadowBlur = 0;

      const label = `Persona ${Math.round(score * 100)}%`;
      const labelW = ctx.measureText(label).width + 12;
      const labelY = Math.max(0, y - 20);
      ctx.fillStyle = 'rgba(255, 123, 61, 0.92)';
      ctx.beginPath();
      ctx.roundRect(x, labelY, labelW, 18, 6);
      ctx.fill();
      ctx.fillStyle = '#ffffff';
      ctx.fillText(label, x + 6, labelY + 13);
    });
    ctx.globalAlpha = 1;
  }

  /**
   * Desliza cada caja desde su posición anterior hasta la nueva durante `durationMs`, para que
   * entre respuestas los recuadros sigan a las personas en lugar de saltar. Cada caja nueva se
   * empareja con la caja anterior más cercana; las que no tienen pareja aparecen con un fundido.
   */
  function animateLiveBoxes(video, boxes, durationMs) {
    const center = (b) => [b[0] + b[2] / 2, b[1] + b[3] / 2];
    const used = new Set();
    const from = boxes.map((b) => {
      const [cx, cy] = center(b);
      let best = -1;
      let bestDist = LIVE_MATCH_DISTANCE;
      shownBoxes.forEach((p, i) => {
        if (used.has(i)) return;
        const [px, py] = center(p);
        const dist = Math.hypot(px - cx, py - cy);
        if (dist < bestDist) {
          best = i;
          bestDist = dist;
        }
      });
      if (best < 0) return null;
      used.add(best);
      return shownBoxes[best];
    });

    cancelAnimationFrame(liveAnimFrame);
    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    const duration = reduceMotion ? 0 : Math.min(300, Math.max(80, durationMs));
    const start = performance.now();
    const step = (now) => {
      const t = duration ? Math.min(1, (now - start) / duration) : 1;
      const ease = 1 - (1 - t) ** 3;
      shownBoxes = boxes.map((b, i) =>
        from[i] ? b.map((v, k) => (k < 4 ? from[i][k] + (v - from[i][k]) * ease : v)) : b
      );
      drawLiveBoxes(video, shownBoxes, from.map((f) => (f ? 1 : ease)));
      if (t < 1) liveAnimFrame = requestAnimationFrame(step);
    };
    liveAnimFrame = requestAnimationFrame(step);
  }

  function clearLiveBoxes() {
    cancelAnimationFrame(liveAnimFrame);
    shownBoxes = [];
    prepareLiveOverlay();
  }

  function setLiveBadge(text, state = '') {
    const badge = $('#hud-live-count');
    if (!badge) return;
    badge.textContent = text;
    badge.dataset.state = state;
  }

  function scheduleLiveTick(session, delay) {
    clearTimeout(liveTimer);
    liveTimer = setTimeout(() => liveTick(session), delay);
  }

  /** Envía un fotograma, anima el resultado y programa el siguiente (uno en vuelo a la vez). */
  async function liveTick(session) {
    if (session !== liveSession || !chefCameraStream) return;
    const video = $('#camera-video');
    if (document.hidden || !video || video.videoWidth === 0) {
      scheduleLiveTick(session, 600);
      return;
    }

    const started = performance.now();
    try {
      const blob = await grabLiveFrame(video);
      const form = new FormData();
      form.append('file', blob, 'frame.jpg');
      form.append('modo', liveMode);
      const r = await fetch('/api/vision/en-vivo/', {
        method: 'POST',
        body: form,
        headers: { 'X-CSRFToken': csrf() },
        credentials: 'same-origin',
      });
      if (session !== liveSession) return;
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.error || `Error ${r.status}`);

      const roundTrip = performance.now() - started;
      animateLiveBoxes(video, data.boxes || [], roundTrip);
      const fps = 1000 / Math.max(LIVE_MIN_INTERVAL_MS, roundTrip);
      liveFpsAvg = liveFpsAvg ? liveFpsAvg * 0.7 + fps * 0.3 : fps; // media móvil: cifra estable
      const n = data.people_count || 0;
      setLiveBadge(
        `YOLOX ${LIVE_MODES[liveMode].name} · ${n} ${n === 1 ? 'persona' : 'personas'} · ${liveFpsAvg.toFixed(1)} fps`,
        'ok'
      );
      liveErrors = 0;
    } catch (_) {
      if (session !== liveSession) return;
      liveErrors += 1;
      clearLiveBoxes();
      setLiveBadge('YOLOX en pausa · reintentando…', 'error');
    }

    const elapsed = performance.now() - started;
    const backoff = liveErrors ? Math.min(8000, 1000 * 2 ** (liveErrors - 1)) : 0;
    scheduleLiveTick(session, Math.max(0, LIVE_MIN_INTERVAL_MS - elapsed) + backoff);
  }

  function startLiveDetection() {
    liveSession += 1;
    liveErrors = 0;
    liveFpsAvg = 0;
    setLiveBadge('YOLOX · iniciando…');
    scheduleLiveTick(liveSession, 0);
  }

  function stopLiveDetection() {
    liveSession += 1;
    clearTimeout(liveTimer);
    clearLiveBoxes();
    setLiveBadge('YOLOX · —');
  }

  /** Actualiza sin recargar el mapa de calor, etiquetas y alertas críticas de una zona. */
  function updateZoneUI(code, level, dwell, alert) {
    const labelText = level === 'normal' ? 'Normal' : level === 'moderada' ? 'Moderada' : 'Crítica';
    const pill = $(`#zone-pill-${code}`);
    if (pill) {
      pill.className = `status-pill ${level}`;
      pill.textContent = labelText;
    }

    const heatCard = $(`#heat-zone-${code}`);
    if (heatCard) heatCard.className = `heat-zone heat-${level}`;

    const heatLevel = $(`#heat-level-${code}`);
    if (heatLevel) heatLevel.textContent = labelText;

    const heatDwell = $(`#heat-dwell-${code}`);
    if (heatDwell) heatDwell.textContent = `${Number(dwell).toFixed(1)} min de permanencia`;

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
            <strong>Zona ${escapeHtml(code)} con congestión crítica</strong>
            <span>${Number(dwell).toFixed(1)} minutos de permanencia: supera el límite de 4 minutos.</span>
          </div>
        `;
        alertsContainer.prepend(banner);
      } else if (banner) {
        const span = banner.querySelector('span');
        if (span) {
          span.textContent = `Permanencia registrada: ${Number(dwell).toFixed(1)} minutos. Supera el umbral de 4 minutos.`;
        }
      }
    } else if (banner) {
      banner.remove();
    }
  }

  /** Detiene la transmisión de video activa de la Cámara del Chef. */
  function stopChefCamera() {
    stopLiveDetection();
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

  /** Inicia la captura en tiempo real de cámara web para análisis de afluencia en sala. */
  async function startChefCamera() {
    const video = $('#camera-video');
    const standby = $('#camera-standby-box');
    const hud = $('#camera-hud-box');
    const actions = $('#camera-actions-panel');

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      toast('Tu navegador no soporta captura de cámara web.', 'error');
      return;
    }

    try {
      toast('Solicitando acceso a la cámara...', 'info');
      chefCameraStream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          facingMode: { ideal: 'environment' },
        },
        audio: false,
      });

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
      startLiveDetection();
      toast('Cámara del Chef transmitiendo en vivo.', 'success');
    } catch (_) {
      toast('No se pudo acceder a la cámara. Revisa los permisos de tu navegador.', 'error');
    }
  }

  /** Renderiza los conteos, desglose zonal, imagen anotada y estado S3 tras procesar con OpenCV. */
  function renderVisionResults(data) {
    $('#vision-placeholder').hidden = true;
    $('#vision-results').hidden = false;
    $('#vision-people').textContent = data.people_count;

    const syncAlert = $('#vision-sync-alert');
    const syncDesc = $('#vision-sync-desc');
    if (syncAlert && syncDesc) {
      syncAlert.hidden = false;
      const criticalCount = (data.updated_zones || []).filter((z) => z.level === 'critica').length;
      if (criticalCount > 0) {
        syncAlert.className = 'vision-sync-banner sync-warning';
        syncDesc.textContent = `Se detectó alta densidad (${criticalCount} zona en alerta crítica). Dijkstra desviará automáticamente a los meseros.`;
      } else {
        syncAlert.className = 'vision-sync-banner sync-success';
        syncDesc.textContent = data.sync_notice || 'Zonas sincronizadas en tiempo real con la afluencia detectada.';
      }
    }

    const s3Badge = $('#vision-s3-status');
    if (s3Badge) {
      s3Badge.textContent = data.s3_status || (data.aws_saved ? '✓ Guardado en AWS S3' : 'Almacenamiento local');
      s3Badge.className = `vision-s3-badge ${data.aws_saved ? 's3-cloud-ok' : 's3-cloud-local'}`;
    }

    const zoneSectors = { A: 'Salón Jardín', B: 'Pasillo Central', C: 'Salón Terraza' };
    $('#vision-zone-counts').replaceChildren(
      ...['A', 'B', 'C'].map((zoneCode) => {
        const count = data.zone_counts?.[zoneCode] || 0;
        const updated = (data.updated_zones || []).find((z) => z.code === zoneCode);
        const level = updated ? updated.level : count >= 3 ? 'critica' : count >= 1 ? 'moderada' : 'normal';

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

  // Los mismos límites valida el servidor al guardar una zona.
  const ZONE_NORMAL_MAX_MIN = 2;
  const ZONE_MODERATE_MAX_MIN = 4;
  const ZONE_MAX_MINUTES = 240;
  const ZONE_LEVEL_DEFAULT_MIN = { normal: 1, moderada: 3, critica: 4.5 };
  const ZONE_SAVE_DELAY_MS = 500;

  /** Inicializa formularios de saturación zonal y captura/carga de imágenes OpenCV. */
  function initVisionZones() {
    window.switchVisionTab = function switchVisionTab(mode) {
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
        if (!isCam && chefCameraStream) {
          stopChefCamera();
        }
      }
    };

    const zoneSaveTimers = {};

    const showZoneState = (code, message, stateClass = '') => {
      const state = $(`#zone-state-${code}`);
      if (!state) return;
      state.textContent = message;
      state.className = `zone-save-state ${stateClass}`.trim();
    };

    const syncLevelButtons = (code) => {
      const level = $(`#level-${code}`)?.value;
      $$(`.level-segment[data-zone="${code}"] .level-option`).forEach((option) => {
        option.setAttribute('aria-pressed', String(option.dataset.level === level));
      });
    };

    const saveZone = async (code) => {
      const level = $(`#level-${code}`).value;
      const dwell = Number($(`#dwell-${code}`).value);
      showZoneState(code, 'Guardando…');
      try {
        const res = await postJSON(`/api/zonas/${code}/`, { level, dwell_minutes: dwell });
        updateZoneUI(code, level, dwell, res.alert);
        showZoneState(code, `✓ Guardado: ${dwell.toFixed(1)} min`, 'is-saved');
      } catch (err) {
        showZoneState(code, 'No se pudo guardar', 'is-error');
        toast(err.message, 'error');
      }
    };

    const scheduleZoneSave = (code) => {
      clearTimeout(zoneSaveTimers[code]);
      showZoneState(code, 'Guardando…');
      zoneSaveTimers[code] = setTimeout(() => saveZone(code), ZONE_SAVE_DELAY_MS);
    };

    const levelForMinutes = (minutes) => {
      if (minutes <= ZONE_NORMAL_MAX_MIN) return 'normal';
      return minutes <= ZONE_MODERATE_MAX_MIN ? 'moderada' : 'critica';
    };

    // Los minutos determinan el nivel; elegir un nivel lleva a un valor típico de su rango.
    $$('input[id^="dwell-"]').forEach((input) => {
      const code = input.id.replace('dwell-', '');
      input.addEventListener('input', () => {
        const minutes = parseFloat(input.value);
        const select = $(`#level-${code}`);
        if (Number.isNaN(minutes) || minutes < 0 || !select) return;
        select.value = levelForMinutes(minutes);
        syncLevelButtons(code);
        scheduleZoneSave(code);
      });
    });

    $$('.dwell-step').forEach((step) => {
      step.addEventListener('click', () => {
        const input = $(`#dwell-${step.dataset.zone}`);
        const next = (parseFloat(input.value) || 0) + Number(step.dataset.step);
        input.value = Math.min(ZONE_MAX_MINUTES, Math.max(0, next)).toFixed(1);
        input.dispatchEvent(new Event('input', { bubbles: true }));
      });
    });

    $$('.level-option').forEach((option) => {
      option.addEventListener('click', () => {
        const code = option.closest('.level-segment').dataset.zone;
        const input = $(`#dwell-${code}`);
        const level = option.dataset.level;
        $(`#level-${code}`).value = level;
        if (levelForMinutes(parseFloat(input.value) || 0) !== level) {
          input.value = ZONE_LEVEL_DEFAULT_MIN[level].toFixed(1);
        }
        syncLevelButtons(code);
        scheduleZoneSave(code);
      });
    });

    $('#btn-start-camera')?.addEventListener('click', startChefCamera);
    $('#btn-stop-camera')?.addEventListener('click', stopChefCamera);
    $('#btn-live-mode')?.addEventListener('click', cycleLiveMode);
    renderLiveModeButton();

    $('#btn-capture-snapshot')?.addEventListener('click', async () => {
      const video = $('#camera-video');
      const container = $('#camera-stream-container');
      const btn = $('#btn-capture-snapshot');

      if (!video || !chefCameraStream || video.videoWidth === 0) {
        toast('La cámara no está transmitiendo video.', 'error');
        return;
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

        const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.9));
        if (!blob) throw new Error('No se pudo capturar el fotograma.');

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
      if (!file) {
        toast('Selecciona una imagen.', 'error');
        return;
      }
      if (file.size > 5 * 1024 * 1024) {
        toast('Máximo 5 MB por fotografía.', 'error');
        return;
      }

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
  }

  Object.assign(OptiFlow, {
    updateZoneUI,
    renderVisionResults,
    initVisionZones,
  });
})();

