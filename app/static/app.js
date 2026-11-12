(() => {
  "use strict";

  const API = "/api";
  const TOKEN_KEY = "rt_token";
  const USER_KEY = "rt_user";
  const SESION_KEY = "rt_sesion";

  const REGIMEN_LABELS = {
    mype_tributario: "MYPE Tributario",
    regimen_general: "Régimen General",
    regimen_especial: "Régimen Especial",
  };
  const RUBRO_LABELS = {
    comercio: "Comercio",
    servicios: "Servicios",
    manufactura: "Manufactura",
    construccion: "Construcción",
  };
  const SEV_ORDER = { alta: 0, media: 1, baja: 2 };
  const SEV_LABEL = { alta: "Alta", media: "Media", baja: "Baja" };
  const FIELD_STEP = {
    regimen: 1, rubro: 1, antiguedad_anios: 1,
    ventas_comprobantes: 2, ventas_declaradas: 2, compras_declaradas: 2,
    compras_proveedores_riesgo: 2, gastos_no_deducibles: 2,
    meses_fuera_plazo: 3, multas_previas: 3, meses_saldo_favor: 3,
  };
  const NUMERIC_FIELDS = [
    "antiguedad_anios", "ventas_comprobantes", "ventas_declaradas", "compras_declaradas",
    "compras_proveedores_riesgo", "gastos_no_deducibles", "meses_fuera_plazo",
    "multas_previas", "meses_saldo_favor",
  ];
  const DEFAULTS = {
    referencia: "", regimen: "mype_tributario", rubro: "comercio",
    antiguedad_anios: "", ventas_comprobantes: "", ventas_declaradas: "",
    compras_declaradas: "", compras_proveedores_riesgo: "", gastos_no_deducibles: "",
    meses_fuera_plazo: "", multas_previas: "", meses_saldo_favor: "",
  };

  const $ = (id) => document.getElementById(id);
  const $$ = (selector, scope = document) => Array.from(scope.querySelectorAll(selector));

  let token = storageGet(TOKEN_KEY);
  let user = safeJson(storageGet(USER_KEY));
  let opciones = null;
  let sesion = safeJson(storageGet(SESION_KEY));
  let current = null;
  let timer = null;
  let guideStep = 1;
  let view = "nuevo";
  let formState = { ...DEFAULTS };
  let toastTimer = null;

  function storageGet(key) {
    try { return sessionStorage.getItem(key); } catch (e) { return null; }
  }
  function storageSet(key, value) {
    try { sessionStorage.setItem(key, value); } catch (e) { /* modo privado */ }
  }
  function storageRemove(key) {
    try { sessionStorage.removeItem(key); } catch (e) { /* modo privado */ }
  }
  function safeJson(raw) {
    try { return raw ? JSON.parse(raw) : null; } catch (e) { return null; }
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function toast(message, isError = false) {
    const box = $("toast");
    box.textContent = message;
    box.className = `toast${isError ? " error" : ""}`;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => box.classList.add("hidden"), 4600);
  }

  function fmtSoles(value) {
    return `S/ ${Number(value || 0).toLocaleString("es-PE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }

  function fmtDuration(seconds) {
    const s = Math.max(0, Math.round(Number(seconds) || 0));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const rest = s % 60;
    if (h > 0) return `${h} h ${m} min`;
    if (m > 0) return `${m} min ${String(rest).padStart(2, "0")} s`;
    return `${rest} s`;
  }

  function fmtDate(iso) {
    if (!iso) return "—";
    const date = new Date(iso.endsWith("Z") ? iso : `${iso}Z`);
    if (Number.isNaN(date.getTime())) return iso;
    return date.toLocaleString("es-PE", {
      day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
    });
  }

  function fmtPct(value, digits = 1) {
    return `${(Number(value) * 100).toFixed(digits)}%`;
  }

  // ------------------------------- API -------------------------------
  async function api(path, options = {}) {
    const headers = { Accept: "application/json", ...(options.headers || {}) };
    if (options.body && !(options.body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }
    if (token) headers.Authorization = `Bearer ${token}`;
    const res = await fetch(`${API}${path}`, { ...options, headers });
    const type = res.headers.get("content-type") || "";
    const data = type.includes("application/json") ? await res.json() : await res.text();

    if (!res.ok) {
      if (res.status === 401 && token) logout(false);
      const error = new Error((data && data.error) || `Error ${res.status}`);
      error.status = res.status;
      error.data = data;
      throw error;
    }
    return data;
  }

  async function apiBlob(path) {
    const res = await fetch(`${API}${path}`, { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) {
      if (res.status === 401) logout(false);
      throw new Error(res.status === 404 ? "Reporte no encontrado" : `Error ${res.status}`);
    }
    return res.blob();
  }

  // ------------------------------- AUTH -------------------------------
  function showLogin() {
    $("loginView").classList.remove("hidden");
    $("appView").classList.add("hidden");
    switchAuthTab("login");
    setAuthError("");
  }

  function showApp() {
    $("loginView").classList.add("hidden");
    $("appView").classList.remove("hidden");
  }

  function setAuthError(message) {
    const box = $("authError");
    box.textContent = message || "";
    box.classList.toggle("hidden", !message);
  }

  function setUserUI() {
    if (!user) return;
    $("userName").textContent = user.nombre;
    $("userMeta").textContent = `${fmtSoles(user.tarifa_hora)}/h`;
    $("userInitial").textContent = (user.nombre || "C").trim().charAt(0).toUpperCase();
  }

  async function login(email, password) {
    const data = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    token = data.token;
    user = data.usuario;
    sesion = null;
    storageRemove(SESION_KEY);
    storageSet(TOKEN_KEY, token);
    storageSet(USER_KEY, JSON.stringify(user));
    await initApp();
  }

  async function register(payload) {
    await api("/auth/registro", { method: "POST", body: JSON.stringify(payload) });
    await login(payload.email, payload.password);
  }

  function logout(notify = true) {
    token = null;
    user = null;
    sesion = null;
    current = null;
    storageRemove(TOKEN_KEY);
    storageRemove(USER_KEY);
    storageRemove(SESION_KEY);
    stopTimer();
    if (notify) toast("Sesión cerrada");
    showLogin();
  }

  async function initApp() {
    showApp();
    setUserUI();
    await loadOptions();
    loadModel();
    if (sesion && sesion.inicio) {
      showView("nuevo");
      startTimer();
    } else {
      await startNewCase(true);
    }
  }

  // ------------------------------- OPTIONS -------------------------------
  async function loadOptions() {
    try {
      opciones = await api("/opciones");
      populateSelects();
      updateMarginHelp();
      updatePreview();
    } catch (error) {
      toast("No se pudieron cargar las opciones del formulario.", true);
    }
  }

  function populateSelects() {
    if (!opciones) return;
    $$('[data-field="regimen"]').forEach((select) => {
      const value = formState.regimen;
      select.replaceChildren();
      opciones.regimenes.forEach((code) => {
        const option = el("option", null, REGIMEN_LABELS[code] || code);
        option.value = code;
        select.appendChild(option);
      });
      select.value = value;
    });
    $$('[data-field="rubro"]').forEach((select) => {
      const value = formState.rubro;
      select.replaceChildren();
      opciones.rubros.forEach((code) => {
        const option = el("option", null, RUBRO_LABELS[code] || code);
        option.value = code;
        select.appendChild(option);
      });
      select.value = value;
    });
  }

  function updateMarginHelp() {
    if (!opciones) return;
    const pct = Math.round((opciones.margen_referencia[formState.rubro] || 0) * 100);
    $$('[data-margin-for="rubro"]').forEach((node) => {
      node.textContent = `Margen bruto referencial del rubro: ${pct}%.`;
    });
  }

  // ------------------------------- FORM STATE -------------------------------
  function mirrorField(field, value) {
    $$(`[data-field="${field}"]`).forEach((input) => {
      if (input.value !== value) input.value = value;
    });
  }

  function setField(field, value, source = null) {
    formState[field] = value;
    $$(`[data-field="${field}"]`).forEach((input) => {
      if (input !== source && input.value !== value) input.value = value;
    });
    clearFieldError(field);
    if (field === "rubro") updateMarginHelp();
    updatePreview();
  }

  function bindFields() {
    $$("[data-field]").forEach((input) => {
      const field = input.dataset.field;
      const handler = () => setField(field, input.value, input);
      input.addEventListener("input", handler);
      input.addEventListener("change", handler);
    });
  }

  function setFormState(next) {
    formState = { ...DEFAULTS, ...next };
    Object.keys(formState).forEach((field) => mirrorField(field, formState[field]));
  }

  function clearFieldError(field) {
    $$(`[data-error-for="${field}"]`).forEach((node) => { node.textContent = ""; });
    $$(`[data-field="${field}"]`).forEach((input) => input.removeAttribute("aria-invalid"));
  }

  function clearErrors(form) {
    $$(".field-error", form).forEach((node) => { node.textContent = ""; });
    $$("[data-field]", form).forEach((input) => input.removeAttribute("aria-invalid"));
    $$(".form-error", form).forEach((node) => { node.textContent = ""; node.classList.add("hidden"); });
  }

  function showFormError(form, message) {
    const box = form.querySelector(".form-error");
    if (!box) return;
    box.textContent = message;
    box.classList.remove("hidden");
  }

  function fieldStep(field) {
    return FIELD_STEP[field] || 0;
  }

  function applyValidationErrors(form, data) {
    const detalle = (data && data.detalle) || {};
    let first = null;
    let step = 0;
    Object.entries(detalle).forEach(([field, message]) => {
      $$(`[data-error-for="${field}"]`, form).forEach((node) => { node.textContent = message; });
      $$(`[data-field="${field}"]`, form).forEach((input) => {
        input.setAttribute("aria-invalid", "true");
        if (!first) first = input;
      });
      const s = fieldStep(field);
      if (s && (!step || s < step)) step = s;
    });
    if (form.id === "guideForm" && step) showGuideStep(step);
    if (first) {
      first.focus({ preventScroll: true });
      first.scrollIntoView({ behavior: "smooth", block: "center" });
    }
    if (!Object.keys(detalle).length) {
      showFormError(form, (data && data.error) || "No se pudo procesar el caso.");
    } else if (data && data.error) {
      showFormError(form, data.error);
    }
  }

  // ------------------------------- SESSION / TIMER -------------------------------
  function saveSession(data) {
    sesion = { sesion: data.sesion, inicio: data.inicio };
    storageSet(SESION_KEY, JSON.stringify(sesion));
    startTimer();
  }

  async function ensureSession(force = false) {
    if (!force && sesion && sesion.sesion) {
      const age = Date.now() - new Date(`${sesion.inicio}Z`).getTime();
      if (age >= 0 && age < 8 * 3600 * 1000) {
        startTimer();
        return;
      }
    }
    const data = await api("/evaluaciones/iniciar", { method: "POST" });
    saveSession(data);
  }

  function startTimer() {
    stopTimer();
    updateTimer();
    timer = setInterval(updateTimer, 1000);
    $("sessionPill").textContent = "Sesión activa · T en curso";
  }

  function stopTimer() {
    if (timer) clearInterval(timer);
    timer = null;
  }

  function updateTimer() {
    const target = $("sessionTimer");
    if (!target) return;
    if (!sesion || !sesion.inicio) {
      target.textContent = "00:00";
      return;
    }
    const start = new Date(`${sesion.inicio}Z`).getTime();
    const seconds = Math.max(0, Math.floor((Date.now() - start) / 1000));
    const h = String(Math.floor(seconds / 3600)).padStart(2, "0");
    const m = String(Math.floor((seconds % 3600) / 60)).padStart(2, "0");
    const s = String(seconds % 60).padStart(2, "0");
    target.textContent = h === "00" ? `${m}:${s}` : `${h}:${m}:${s}`;
  }

  async function startNewCase(force = false) {
    if (force) {
      sesion = null;
      storageRemove(SESION_KEY);
      setFormState(DEFAULTS);
      clearErrors($("fileForm"));
      clearErrors($("guideForm"));
      resetFileInputs();
      showGuideStep(1);
      stopTimer();
    }
    showView("nuevo");
    try {
      await ensureSession(force);
    } catch (error) {
      if (error.status !== 401) toast(error.message, true);
    }
  }

  function resetFileInputs() {
    ["fileVentas", "filePdt", "fileCompras"].forEach((id) => {
      const input = $(id);
      if (input) input.value = "";
    });
    $("nameVentas").textContent = "Seleccionar archivo";
    $("namePdt").textContent = "Seleccionar archivo";
    $("nameCompras").textContent = "Seleccionar archivo";
  }

  // ------------------------------- NAV / VIEWS -------------------------------
  const VIEW_META = {
    nuevo: { kicker: "Expediente", title: "Nuevo caso" },
    resultado: { kicker: "Dictamen", title: "Resultado" },
    historial: { kicker: "Registro", title: "Historial" },
  };

  function showView(name) {
    view = name;
    ["nuevo", "resultado", "historial"].forEach((key) => {
      $(`view${key.charAt(0).toUpperCase()}${key.slice(1)}`).classList.toggle("hidden", key !== name);
    });
    const meta = VIEW_META[name] || VIEW_META.nuevo;
    $("pageKicker").textContent = meta.kicker;
    $("pageTitle").textContent = meta.title;
    $$(".nav-item").forEach((item) => {
      item.classList.toggle("active", item.dataset.nav === name || (name === "resultado" && item.dataset.nav === "nuevo"));
    });
    if (name === "historial") loadHistory();
  }

  // ------------------------------- FILES UI -------------------------------
  function bindFileInputs() {
    [["fileVentas", "nameVentas"], ["filePdt", "namePdt"], ["fileCompras", "nameCompras"]].forEach(([inputId, labelId]) => {
      const input = $(inputId);
      input.addEventListener("change", () => {
        const file = input.files && input.files[0];
        const size = file
          ? (file.size < 1024 ? `${file.size} B` : `${Math.round(file.size / 1024)} KB`)
          : "";
        $(labelId).textContent = file ? `${file.name} · ${size}` : "Seleccionar archivo";
        $("fileError").classList.add("hidden");
      });
    });
  }

  // TEMPORAL: carga un caso de ejemplo para probar el flujo de archivos.
  async function cargarCasoEjemplo() {
    const button = $("btnCasoEjemplo");
    button.disabled = true;
    button.textContent = "Cargando…";
    try {
      const [ventas, pdt, compras] = await Promise.all([
        fetch("/static/ejemplos/ventas.csv"),
        fetch("/static/ejemplos/pdt621.csv"),
        fetch("/static/ejemplos/compras.csv"),
      ]);
      if (!ventas.ok || !pdt.ok || !compras.ok) throw new Error("No se pudieron cargar los archivos de ejemplo.");
      const [ventasTxt, pdtTxt, comprasTxt] = await Promise.all([ventas.text(), pdt.text(), compras.text()]);
      const asignar = (inputId, labelId, nombre, contenido) => {
        const archivo = new File([contenido], nombre, { type: "text/csv" });
        const dt = new DataTransfer();
        dt.items.add(archivo);
        $(inputId).files = dt.files;
        $(labelId).textContent = `${nombre} · ${archivo.size} B`;
      };
      asignar("fileVentas", "nameVentas", "ventas_ejemplo.csv", ventasTxt);
      asignar("filePdt", "namePdt", "pdt621_ejemplo.csv", pdtTxt);
      asignar("fileCompras", "nameCompras", "compras_ejemplo.csv", comprasTxt);
      setFormState({
        ...formState,
        referencia: "Caso-Ejemplo-001",
        regimen: "mype_tributario",
        rubro: "comercio",
        antiguedad_anios: "8",
        meses_fuera_plazo: "7",
        multas_previas: "3",
        meses_saldo_favor: "8",
        compras_proveedores_riesgo: "180000",
        gastos_no_deducibles: "30000",
      });
      $("fileError").classList.add("hidden");
      toast("Caso de ejemplo cargado. Revisa y pulsa «Procesar archivos».");
    } catch (error) {
      showFormError($("fileForm"), error.message);
    } finally {
      button.disabled = false;
      button.textContent = "Cargar caso de ejemplo";
    }
  }

  function fileFormData() {
    const fd = new FormData();
    const ventas = $("fileVentas").files[0];
    const pdt = $("filePdt").files[0];
    const compras = $("fileCompras").files[0];
    if (!ventas || !pdt) throw new Error("El Registro de ventas y el PDT 621 son obligatorios.");
    fd.append("ventas", ventas);
    fd.append("pdt621", pdt);
    if (compras) fd.append("compras", compras);
    ["referencia", "regimen", "rubro", "antiguedad_anios", "meses_fuera_plazo",
     "multas_previas", "meses_saldo_favor", "compras_proveedores_riesgo", "gastos_no_deducibles"]
      .forEach((field) => {
        if (String(formState[field] ?? "").trim() !== "") fd.append(field, formState[field]);
      });
    if (sesion) fd.append("sesion", sesion.sesion);
    return fd;
  }

  async function submitFiles(event) {
    event.preventDefault();
    const form = $("fileForm");
    clearErrors(form);
    const missing = [];
    if (!$("fileVentas").files[0]) missing.push("Registro de ventas");
    if (!$("filePdt").files[0]) missing.push("PDT 621");
    if (missing.length) {
      showFormError(form, `Falta cargar: ${missing.join(" y ")}.`);
      return;
    }
    if (!validateCommonCompany(form)) return;
    const button = $("btnFileSubmit");
    button.disabled = true;
    button.textContent = "Procesando…";
    try {
      const fd = fileFormData();
      const data = await api("/evaluaciones/archivo", { method: "POST", body: fd });
      handleEvaluation(data);
    } catch (error) {
      if (error.status === 422 && error.data) applyValidationErrors(form, error.data);
      else if (error.status !== 401) showFormError(form, error.message);
    } finally {
      button.disabled = false;
      button.textContent = "Procesar archivos";
    }
  }

  function validateCommonCompany(form) {
    let ok = true;
    ["regimen", "rubro", "antiguedad_anios", "meses_fuera_plazo", "multas_previas", "meses_saldo_favor"].forEach((field) => {
      const value = String(formState[field] ?? "").trim();
      if (value === "") {
        setInlineError(field, "Completa este campo.");
        ok = false;
      }
    });
    return ok;
  }

  function setInlineError(field, message) {
    $$(`[data-error-for="${field}"]`).forEach((node) => { node.textContent = message; });
    $$(`[data-field="${field}"]`).forEach((input) => input.setAttribute("aria-invalid", "true"));
  }

  // ------------------------------- GUIDED UI -------------------------------
  function showGuideStep(step) {
    guideStep = Math.min(3, Math.max(1, Number(step) || 1));
    $$(".step-panel").forEach((panel) => {
      panel.classList.toggle("hidden", Number(panel.dataset.step) !== guideStep);
    });
    $$(".step").forEach((button) => {
      const n = Number(button.dataset.stepBtn);
      button.classList.toggle("active", n === guideStep);
      button.classList.toggle("done", n < guideStep);
    });
    $("btnPrevStep").classList.toggle("hidden", guideStep === 1);
    $("btnNextStep").classList.toggle("hidden", guideStep === 3);
    $("btnGuideSubmit").classList.toggle("hidden", guideStep !== 3);
    if (guideStep === 2) updatePreview();
  }

  function validateStep(step) {
    let ok = true;
    $$(`.step-panel[data-step="${step}"] [required]`).forEach((input) => {
      if (!input.checkValidity() || String(formState[input.dataset.field] ?? "").trim() === "") {
        setInlineError(input.dataset.field, "Completa este campo con un valor válido.");
        ok = false;
      }
    });
    return ok;
  }

  function nextStep() {
    if (!validateStep(guideStep)) return;
    if (guideStep < 3) showGuideStep(guideStep + 1);
  }

  function prevStep() {
    if (guideStep > 1) showGuideStep(guideStep - 1);
  }

  function updatePreview() {
    if (!$("previewBrecha")) return;
    const vc = Number(formState.ventas_comprobantes);
    const vd = Number(formState.ventas_declaradas);
    const cd = Number(formState.compras_declaradas);
    const riesgo = Number(formState.compras_proveedores_riesgo);
    const rubro = formState.rubro;
    if (![vc, vd, cd].every(Number.isFinite) || vc + vd <= 0 || !opciones) {
      $("previewBrecha").textContent = "—";
      $("previewRiesgo").textContent = "—";
      $("previewMargen").textContent = "—";
      return;
    }
    const brecha = (vc - vd) / Math.max(vc, vd, 1);
    const pctRiesgo = cd > 0 ? riesgo / cd : 0;
    const margen = 1 - cd / Math.max(vd, 1);
    const ref = opciones.margen_referencia[rubro] || 0;
    $("previewBrecha").textContent = fmtPct(brecha);
    $("previewRiesgo").textContent = fmtPct(pctRiesgo);
    $("previewMargen").textContent = `${fmtPct(margen)} (ref. ${fmtPct(ref, 0)})`;
  }

  async function submitGuide(event) {
    event.preventDefault();
    const form = $("guideForm");
    clearErrors(form);
    for (let step = 1; step <= 3; step += 1) {
      if (!validateStep(step)) {
        showGuideStep(step);
        return;
      }
    }
    const datos = {};
    NUMERIC_FIELDS.forEach((field) => { datos[field] = Number(formState[field]); });
    datos.regimen = formState.regimen;
    datos.rubro = formState.rubro;
    const button = $("btnGuideSubmit");
    button.disabled = true;
    button.textContent = "Evaluando…";
    try {
      const data = await api("/evaluaciones", {
        method: "POST",
        body: JSON.stringify({
          referencia: formState.referencia || undefined,
          sesion: sesion ? sesion.sesion : undefined,
          datos,
        }),
      });
      handleEvaluation(data);
    } catch (error) {
      if (error.status === 422 && error.data) applyValidationErrors(form, error.data);
      else if (error.status !== 401) showFormError(form, error.message);
    } finally {
      button.disabled = false;
      button.textContent = "Evaluar riesgo";
    }
  }

  // ------------------------------- RESULT -------------------------------
  function handleEvaluation(ev) {
    current = ev;
    stopTimer();
    sesion = null;
    storageRemove(SESION_KEY);
    $("sessionPill").textContent = "Sesión finalizada";
    renderResult(ev);
    showView("resultado");
    loadHistory();
    toast(`Evaluación #${ev.id} registrada · riesgo ${ev.nivel_riesgo}`);
  }

  function renderResult(ev) {
    const level = ev.nivel_riesgo;
    $("resReference").textContent = ev.referencia ? `Caso: ${ev.referencia}` : "Caso sin referencia";
    $("resMeta").textContent = `Evaluación #${ev.id} · ${fmtDate(ev.creado)} · Origen: ${ev.origen} · Modelo: ${ev.modelo}`;
    const seal = $("riskSeal");
    seal.dataset.risk = level;
    $("resLevel").textContent = level;
    $("resProb").textContent = fmtPct(ev.probabilidad);
    $("resModel").textContent = ev.modelo;

    const bars = $("probBars");
    bars.replaceChildren();
    ["Bajo", "Medio", "Alto"].forEach((name) => {
      const value = Number((ev.probabilidades || {})[name] || 0);
      const row = el("div", `prob-row ${name === "Bajo" ? "low" : name === "Medio" ? "mid" : "high"}`);
      row.appendChild(el("span", null, name));
      const track = el("div", "prob-track");
      const fill = el("div", "prob-fill");
      fill.style.width = `${Math.min(100, Math.max(0, value * 100))}%`;
      track.appendChild(fill);
      row.appendChild(track);
      row.appendChild(el("b", null, fmtPct(value)));
      bars.appendChild(row);
    });

    renderAlerts(ev.alertas || []);
    renderInfluences(ev.variables_influyentes || []);
    renderAvisos(ev.avisos || []);
    renderTimeCost(ev);
  }

  function renderAlerts(alerts) {
    const box = $("alertsList");
    box.replaceChildren();
    const sorted = [...alerts].sort((a, b) => (SEV_ORDER[a.severidad] ?? 9) - (SEV_ORDER[b.severidad] ?? 9));
    if (!sorted.length) {
      box.appendChild(el("p", "empty-state", "No se identificaron alertas con las reglas actuales."));
      return;
    }
    sorted.forEach((alert) => {
      const card = el("article", "alert");
      card.dataset.sev = alert.severidad;
      const head = el("div", "alert-head");
      head.appendChild(el("span", "sev", SEV_LABEL[alert.severidad] || alert.severidad));
      head.appendChild(el("p", null, alert.mensaje));
      card.appendChild(head);
      const action = el("div", "alert-action");
      action.appendChild(el("strong", null, "Qué revisar"));
      action.appendChild(document.createTextNode(alert.accion));
      card.appendChild(action);
      box.appendChild(card);
    });
  }

  function renderInfluences(items) {
    const list = $("influencesList");
    list.replaceChildren();
    if (!items.length) {
      list.appendChild(el("li", "empty-state", "Sin variables destacadas."));
      return;
    }
    items.forEach((item) => {
      const li = el("li");
      li.appendChild(el("span", null, item.etiqueta || item.variable));
      li.appendChild(el("b", null, `${item.impacto >= 0 ? "+" : ""}${item.impacto} · ${item.efecto}`));
      list.appendChild(li);
    });
  }

  function renderAvisos(avisos) {
    const box = $("avisosBox");
    const list = $("avisosList");
    list.replaceChildren();
    box.classList.toggle("hidden", !avisos.length);
    avisos.forEach((aviso) => list.appendChild(el("li", null, aviso)));
  }

  function renderTimeCost(ev) {
    if (ev.tiempo) {
      $("resTime").textContent = fmtDuration(ev.tiempo.duracion_seg);
      $("resMethod").textContent = ev.tiempo.metodo === "sesion"
        ? "Desde la apertura del caso"
        : "Solo procesamiento del servidor";
    } else {
      $("resTime").textContent = "—";
      $("resMethod").textContent = "Sin registro";
    }
    const costo = ev.costo || {};
    $("costFinal").textContent = fmtSoles(costo.final);
    const corregido = costo.corregido !== null && costo.corregido !== undefined;
    $("costCalc").textContent = corregido
      ? `Corregido · calculado ${fmtSoles(costo.calculado)} · tarifa ${fmtSoles(costo.tarifa_hora)}/h`
      : `Calculado · tarifa ${fmtSoles(costo.tarifa_hora)}/h`;
    $("btnCostReset").classList.toggle("hidden", !corregido);
    $("costEditor").classList.add("hidden");
    $("costInput").value = corregido ? costo.corregido : "";
  }

  async function saveCost(value) {
    if (!current) return;
    try {
      const updated = await api(`/evaluaciones/${current.id}/costo`, {
        method: "PATCH",
        body: JSON.stringify({ costo: value }),
      });
      current = updated;
      renderTimeCost(updated);
      toast(value === null ? "Costo restablecido al calculado." : "Costo corregido.");
    } catch (error) {
      if (error.status === 422) toast(error.message, true);
      else if (error.status !== 401) toast(error.message, true);
    }
  }

  async function openReport() {
    if (!current) return;
    try {
      const blob = await apiBlob(`/evaluaciones/${current.id}/reporte`);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.target = "_blank";
      link.rel = "noopener";
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (error) {
      toast(error.message, true);
    }
  }

  // ------------------------------- HISTORY -------------------------------
  async function loadHistory() {
    const body = $("historyBody");
    try {
      const data = await api("/evaluaciones?per_page=30");
      body.replaceChildren();
      if (!data.items.length) {
        const tr = el("tr");
        const td = el("td", "empty-cell", "Todavía no hay evaluaciones registradas.");
        td.colSpan = 9;
        tr.appendChild(td);
        body.appendChild(tr);
        return;
      }
      data.items.forEach((ev) => {
        const tr = el("tr");
        tr.appendChild(el("td", null, `#${ev.id}`));
        tr.appendChild(el("td", null, ev.referencia || "—"));
        tr.appendChild(el("td", null, fmtDate(ev.creado)));
        tr.appendChild(el("td", null, ev.origen === "archivo" ? "Archivo" : "Formulario"));
        const levelCell = el("td");
        levelCell.appendChild(el("span", `level-tag ${ev.nivel_riesgo}`, ev.nivel_riesgo));
        tr.appendChild(levelCell);
        tr.appendChild(el("td", null, fmtPct(ev.probabilidad)));
        tr.appendChild(el("td", null, ev.tiempo ? fmtDuration(ev.tiempo.duracion_seg) : "—"));
        tr.appendChild(el("td", null, fmtSoles(ev.costo ? ev.costo.final : 0)));
        const action = el("td");
        const button = el("button", "row-link", "Abrir");
        button.type = "button";
        button.addEventListener("click", () => openEvaluation(ev.id));
        action.appendChild(button);
        tr.appendChild(action);
        body.appendChild(tr);
      });
    } catch (error) {
      if (error.status !== 401) {
        body.replaceChildren();
        const tr = el("tr");
        const td = el("td", "empty-cell", error.message);
        td.colSpan = 9;
        tr.appendChild(td);
        body.appendChild(tr);
      }
    }
  }

  async function openEvaluation(id) {
    try {
      const ev = await api(`/evaluaciones/${id}`);
      current = ev;
      renderResult(ev);
      showView("resultado");
    } catch (error) {
      if (error.status !== 401) toast(error.message, true);
    }
  }

  // ------------------------------- MODEL -------------------------------
  async function loadModel() {
    try {
      const data = await api("/modelo");
      const name = data.modelo_seleccionado || "modelo";
      const metrics = (data.holdout_20pct || {})[name] || {};
      const f1 = metrics.f1 !== undefined ? Number(metrics.f1).toFixed(3) : "—";
      $("modelPill").textContent = `${name} · F1 ${f1}`;
    } catch (error) {
      $("modelPill").textContent = "Modelo no disponible";
    }
  }

  // ------------------------------- BINDINGS -------------------------------
  function switchAuthTab(mode) {
    const isLogin = mode === "login";
    $("tabLogin").classList.toggle("active", isLogin);
    $("tabRegister").classList.toggle("active", !isLogin);
    $("tabLogin").setAttribute("aria-selected", String(isLogin));
    $("tabRegister").setAttribute("aria-selected", String(!isLogin));
    $("loginForm").classList.toggle("hidden", !isLogin);
    $("registerForm").classList.toggle("hidden", isLogin);
    setAuthError("");
  }

  function switchCaseTab(tab) {
    $$("[data-tab]").forEach((button) => {
      const active = button.dataset.tab === tab;
      button.classList.toggle("active", active);
      button.setAttribute("aria-selected", String(active));
    });
    $("panelArchivos").classList.toggle("hidden", tab !== "archivos");
    $("panelGuiado").classList.toggle("hidden", tab !== "guiado");
  }

  function confirmRestart() {
    const hasData = Object.entries(formState).some(([key, value]) =>
      !["regimen", "rubro"].includes(key) && String(value).trim() !== "");
    if (!hasData || window.confirm("Se reiniciará el caso y el cronómetro. ¿Continuar?")) {
      startNewCase(true);
    }
  }

  function bind() {
    $("tabLogin").addEventListener("click", () => switchAuthTab("login"));
    $("tabRegister").addEventListener("click", () => switchAuthTab("register"));

    $("loginForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      setAuthError("");
      const button = event.submitter;
      if (button) button.disabled = true;
      try {
        await login($("loginEmail").value.trim(), $("loginPassword").value);
      } catch (error) {
        setAuthError(error.message);
      } finally {
        if (button) button.disabled = false;
      }
    });

    $("registerForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      setAuthError("");
      const button = event.submitter;
      if (button) button.disabled = true;
      const payload = {
        nombre: $("regName").value.trim(),
        email: $("regEmail").value.trim(),
        password: $("regPassword").value,
      };
      const tariff = Number($("regTarifa").value);
      if (Number.isFinite(tariff) && tariff > 0) payload.tarifa_hora = tariff;
      try {
        await register(payload);
      } catch (error) {
        setAuthError(error.message);
      } finally {
        if (button) button.disabled = false;
      }
    });

    $("btnLogout").addEventListener("click", () => logout());
    $$("[data-nav]").forEach((button) => {
      button.addEventListener("click", async () => {
        const name = button.dataset.nav;
        if (name === "nuevo") {
          if (sesion && sesion.sesion) showView("nuevo");
          else await startNewCase(true);
          return;
        }
        showView(name);
      });
    });

    $$("[data-tab]").forEach((button) => {
      button.addEventListener("click", () => switchCaseTab(button.dataset.tab));
    });

    $("btnRestartCase").addEventListener("click", confirmRestart);
    $("btnResultNew").addEventListener("click", () => startNewCase(true));

    $("fileForm").addEventListener("submit", submitFiles);
    $("guideForm").addEventListener("submit", submitGuide);
    $("btnNextStep").addEventListener("click", nextStep);
    $("btnPrevStep").addEventListener("click", prevStep);
    $$("[data-step-btn]").forEach((button) => {
      button.addEventListener("click", () => {
        const target = Number(button.dataset.stepBtn);
        if (target < guideStep || validateStep(guideStep)) showGuideStep(target);
      });
    });

    $("btnCostEdit").addEventListener("click", () => {
      $("costEditor").classList.remove("hidden");
      $("costInput").focus();
    });
    $("btnCostSave").addEventListener("click", () => {
      const raw = $("costInput").value;
      const value = raw === "" ? null : Number(raw);
      if (value !== null && (!Number.isFinite(value) || value < 0)) {
        toast("El costo debe ser un número mayor o igual a 0.", true);
        return;
      }
      saveCost(value);
    });
    $("btnCostReset").addEventListener("click", () => saveCost(null));
    $("btnReport").addEventListener("click", openReport);
    $("btnRefreshHistory").addEventListener("click", loadHistory);

    bindFields();
    bindFileInputs();
    // TEMPORAL: botón de caso de ejemplo para pruebas.
    $("btnCasoEjemplo").addEventListener("click", cargarCasoEjemplo);
  }

  async function boot() {
    bind();
    if (token && user) {
      try {
        await initApp();
        return;
      } catch (error) {
        logout(false);
      }
    }
    showLogin();
    loadModel();
  }

  document.addEventListener("DOMContentLoaded", boot);
})();
