/* OptiFlow Dining · Saturación de Zonas y Visión Computacional OpenCV (Chef Cam & S3). */
(() => {
  'use strict';

  const OptiFlow = (window.OptiFlow = window.OptiFlow || {});
  const { $, $$, escapeHtml, csrf, toast, postJSON } = OptiFlow;

  let chefCameraStream = null;

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
            <strong>Congestión crítica · Nodo de la zona ${escapeHtml(code)}</strong>
            <span>Permanencia registrada: ${Number(dwell).toFixed(1)} minutos. Supera el umbral de 4 minutos.</span>
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

    $$('.zone-save').forEach((btn) =>
      btn.addEventListener('click', async () => {
        const code = btn.dataset.zone;
        const levelVal = $(`#level-${code}`).value;
        const dwellVal = Number($(`#dwell-${code}`).value);

        if (levelVal === 'critica' && dwellVal <= 4.0) {
          toast('Una zona solo puede clasificarse como Crítica si supera 4.0 minutos.', 'error');
          $(`#dwell-${code}`).focus();
          return;
        }
        if (levelVal === 'normal' && dwellVal > 2.0) {
          toast('Una zona con permanencia superior a 2.0 min no puede ser Normal.', 'error');
          $(`#dwell-${code}`).focus();
          return;
        }
        if (levelVal === 'moderada' && (dwellVal <= 2.0 || dwellVal > 4.0)) {
          toast('Una zona Moderada debe estar entre 2.1 y 4.0 minutos.', 'error');
          $(`#dwell-${code}`).focus();
          return;
        }

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

    $$('input[id^="dwell-"]').forEach((input) => {
      input.addEventListener('input', () => {
        const val = parseFloat(input.value);
        const code = input.id.replace('dwell-', '');
        const select = $(`#level-${code}`);
        if (!Number.isNaN(val) && select) {
          if (val <= 2.0) select.value = 'normal';
          else if (val <= 4.0) select.value = 'moderada';
          else select.value = 'critica';
        }
      });
    });

    $$('select[id^="level-"]').forEach((select) => {
      select.addEventListener('change', () => {
        const code = select.id.replace('level-', '');
        const dwellInput = $(`#dwell-${code}`);
        if (!dwellInput) return;
        const dwell = parseFloat(dwellInput.value);
        if (select.value === 'critica' && (Number.isNaN(dwell) || dwell <= 4.0)) {
          dwellInput.value = '4.5';
          toast(`Zona ${code}: tiempo ajustado a 4.5 min para rango Crítico (> 4 min).`, 'info');
        } else if (select.value === 'moderada' && (Number.isNaN(dwell) || dwell <= 2.0 || dwell > 4.0)) {
          dwellInput.value = '3.0';
          toast(`Zona ${code}: tiempo ajustado a 3.0 min para rango Moderado (2.1 a 4 min).`, 'info');
        } else if (select.value === 'normal' && (Number.isNaN(dwell) || dwell > 2.0)) {
          dwellInput.value = '1.0';
          toast(`Zona ${code}: tiempo ajustado a 1.0 min para rango Normal (<= 2 min).`, 'info');
        }
      });
    });

    $('#btn-start-camera')?.addEventListener('click', startChefCamera);
    $('#btn-stop-camera')?.addEventListener('click', stopChefCamera);

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

