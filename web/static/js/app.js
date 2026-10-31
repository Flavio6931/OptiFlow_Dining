/* OptiFlow Dining · Orquestador Principal de Módulos Cliente. */
(() => {
  'use strict';

  const OptiFlow = (window.OptiFlow = window.OptiFlow || {});

  /** Inicializa en orden determinista los submódulos disponibles en la vista actual. */
  function bootstrap() {
    OptiFlow.initCore?.();
    OptiFlow.initFloorPlan?.();
    OptiFlow.initRouting?.();
    OptiFlow.initCadTables?.();
    OptiFlow.initVisionZones?.();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrap);
  } else {
    bootstrap();
  }
})();
