const fallbackCatalog = [];

const drugRowsContainer = document.getElementById("drugRows");
const rowTemplate = document.getElementById("drugRowTemplate");
const birthDateInput = document.getElementById("birthDate");
const ageValue = document.getElementById("ageValue");
const statusText = document.getElementById("statusText");
const directoryTableBody = document.getElementById("directoryTableBody");
const directoryArchiveBody = document.getElementById("directoryArchiveBody");
const recipeDoctorInput = document.getElementById("recipeDoctorInput");
const settingsDoctorInput = document.getElementById("settingsDoctorInput");
const doctorModalInput = document.getElementById("doctorModalInput");
const saveDoctorBtn = document.getElementById("saveDoctorBtn");
const changeDoctorBtn = document.getElementById("changeDoctorBtn");
const cardNumberInput = document.getElementById("cardNumberInput");
const patientNameInput = document.getElementById("patientNameInput");
const patientSmartInput = document.getElementById("patientSmartInput");
const patientParsedHint = document.getElementById("patientParsedHint");
const saveHistoryBtn = document.getElementById("saveHistoryBtn");
const printBtn = document.getElementById("printBtn");
const loadHistoryBtn = document.getElementById("loadHistoryBtn");
const clearFormBtn = document.getElementById("clearFormBtn");
const restoreAutosaveBtn = document.getElementById("restoreAutosaveBtn");
const saveTemplateBtn = document.getElementById("saveTemplateBtn");
const loadTemplateBtn = document.getElementById("loadTemplateBtn");
const templateSelect = document.getElementById("templateSelect");
const templateManagerSelect = document.getElementById("templateManagerSelect");
const templateManagerName = document.getElementById("templateManagerName");
const templateManagerSaveBtn = document.getElementById("templateManagerSaveBtn");
const templateManagerLoadBtn = document.getElementById("templateManagerLoadBtn");
const templateManagerDeleteBtn = document.getElementById("templateManagerDeleteBtn");
const templateManagerPreview = document.getElementById("templateManagerPreview");
const showSchemeBtn = document.getElementById("showSchemeBtn");
const treatmentParseInput = document.getElementById("treatmentParseInput");
const parseTreatmentBtn = document.getElementById("parseTreatmentBtn");
const treatmentParseHint = document.getElementById("treatmentParseHint");
const globalDrugSearch = document.getElementById("globalDrugSearch");
const drugSearchDropdown = document.getElementById("drugSearchDropdown");
const appVersionLabel = document.getElementById("appVersionLabel");
const appUpdateStatus = document.getElementById("appUpdateStatus");
const topbarVersion = document.getElementById("topbarVersion");
const checkUpdateBtn = document.getElementById("checkUpdateBtn");
const applyUpdateBtn = document.getElementById("applyUpdateBtn");
const restartAppBtn = document.getElementById("restartAppBtn");
const openRepoBtn = document.getElementById("openRepoBtn");

let catalogDrugs = [...fallbackCatalog];
let doctorModalInstance = null;
let autosaveTimer = null;
let searchMatches = [];
let searchActiveIndex = 0;
let latestUpdateStatus = null;
let printBlankCssText = "";
let autoUpdateStarted = false;

const DUPLEX_BACK_SLOT = [1, 0, 3, 2];
const PRINT_CUT_MARKS_HTML = `
      <div class="cut-marks" aria-hidden="true">
        <span class="tick tick-v tick-top"></span>
        <span class="tick tick-v tick-bottom"></span>
        <span class="tick tick-h tick-left"></span>
        <span class="tick tick-h tick-right"></span>
        <span class="cross-h"></span>
        <span class="cross-v"></span>
      </div>`;
const PRINT_TOOLBAR_STYLE = `
      .print-toolbar{position:sticky;top:0;z-index:20;display:flex;flex-wrap:wrap;align-items:center;gap:10px;max-width:210mm;margin:0 auto 10px;padding:10px 12px;background:#eef4ff;border:1px solid #c8d9f0;border-radius:8px;box-shadow:0 2px 8px rgba(0,0,0,.08)}
      .print-action-btn{border:0;border-radius:6px;padding:8px 16px;font-size:14px;font-weight:600;cursor:pointer}
      .print-action-btn-primary{background:#0d6efd;color:#fff}
      .print-action-btn-secondary{background:#fff;color:#333;border:1px solid #ccc}
      .print-note{font-size:12px;color:#444;line-height:1.35}
      @media print{.print-toolbar,.print-hint{display:none!important}}
    `;
const BACK_BLANK_HTML = `
    <div class="blank">
      <table class="form back">
        <colgroup>
          <col class="b1" />
          <col class="b2" />
          <col class="b3" />
          <col class="b4" />
          <col class="b5" />
        </colgroup>
        <tr class="row-1">
          <th>Наименование лекарственного препарата, его лекарственная форма, дозировка, фасовка</th>
          <th>Количество реализо-<br>ванных упаковок</th>
          <th>Цена за упаковку, рублей</th>
          <th>Сумма, рублей</th>
          <th>№ аптеки, адрес, дата реализации и подпись фармацевтического работника</th>
        </tr>
        <tr class="row-2">
          <td></td><td></td><td></td><td></td><td></td>
        </tr>
        <tr class="row-3">
          <td colspan="5"></td>
        </tr>
        <tr class="row-4">
          <td colspan="2">Номер лекарственного препарата аптечного изготовления</td>
          <td colspan="3">Штамп аптеки</td>
        </tr>
        <tr class="row-5">
          <td>Принял</td>
          <td>Приготовил</td>
          <td>Проверил</td>
          <td colspan="2">Реализовал</td>
        </tr>
        <tr class="row-6">
          <td></td><td></td><td></td><td colspan="2"></td>
        </tr>
      </table>
    </div>
  `;

function setStatus(message) {
    statusText.textContent = message;
}

function normalizePreviewData(state, preview) {
    const previewData = preview || {};
    return {
        stampHtml: (Array.isArray(previewData.stamp_lines) ? previewData.stamp_lines : [])
            .map((line) => `<p>${escapeHtml(line)}</p>`)
            .join(""),
        todayLong: String(previewData.today_long || ""),
        patientName: String(previewData.patient_name || formatNameWithInitials(state.patient_name)),
        birthDate: String(previewData.birth_date || normalizeBirthDate(state.birth_date)),
        doctorName: String(previewData.doctor_name || state.doctor_name || ""),
        frontBatches: Array.isArray(previewData.front_batches) ? previewData.front_batches : [],
        backFilledBatches: Array.isArray(previewData.back_filled_batches) ? previewData.back_filled_batches : [],
        duplexBackSlot: Array.isArray(previewData.duplex_back_slot) && previewData.duplex_back_slot.length === 4
            ? previewData.duplex_back_slot
            : DUPLEX_BACK_SLOT,
        unp: escapeHtml(previewData.unp || "191896187"),
    };
}

function buildSheetMarkup(frontHtml, backHtml) {
    return `
        <section class="a4-sheet">
          ${PRINT_CUT_MARKS_HTML}
          <div class="a4-grid">${frontHtml}</div>
        </section>
        <section class="a4-sheet">
          ${PRINT_CUT_MARKS_HTML}
          <div class="a4-grid">${backHtml}</div>
        </section>
    `;
}

function buildPreviewDocumentHtml(sheets, printStyles, escapedPdfPath) {
    return `
        <!DOCTYPE html>
        <html lang="ru">
        <head>
            <meta charset="UTF-8">
            <title>Печать рецептов</title>
            <style>${printStyles}</style>
            <style>${PRINT_TOOLBAR_STYLE}</style>
        </head>
        <body>
            <div class="print-toolbar">
              <button type="button" class="print-action-btn print-action-btn-primary" id="doPrintBtn">Печать</button>
              <button type="button" class="print-action-btn print-action-btn-secondary" id="closePreviewBtn">Закрыть</button>
              <span class="print-note">A4 · масштаб 100% · отступ 4 мм в макете · дуплекс по длинной стороне${escapedPdfPath ? ` · PDF: ${escapedPdfPath}` : ""}</span>
            </div>
            <div class="print-hint">
              Нажмите синюю кнопку <strong>Печать</strong> (или Ctrl+P). В диалоге принтера выберите двустороннюю печать
              <strong>по длинной стороне</strong>.
            </div>
            ${sheets.join("")}
            <script>
              document.getElementById("doPrintBtn").addEventListener("click", function () { window.print(); });
              document.getElementById("closePreviewBtn").addEventListener("click", function () { window.close(); });
              window.addEventListener("load", function () {
                window.focus();
                setTimeout(function () { window.print(); }, 400);
              });
            </script>
        </body>
        </html>
    `;
}

async function copyTextToClipboard(text) {
    const value = String(text || "");
    if (!value) {
        return false;
    }
    if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(value);
        return true;
    }

    const textarea = document.createElement("textarea");
    textarea.value = value;
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";
    document.body.appendChild(textarea);
    textarea.select();
    try {
        return document.execCommand("copy");
    } finally {
        document.body.removeChild(textarea);
    }
}

function buildSchemeClipboardText(drugs) {
    return drugs
        .filter((drug) => drug.mnn)
        .map((drug) => {
            const form = String(drug.drug_form || "").trim();
            const latin = String(drug.latin_name || "").trim();
            const title = latin || String(drug.russian_name || drug.mnn || "").trim();
            const trades = (Array.isArray(drug.trade_names) ? drug.trade_names : [])
                .map((name) => String(name || "").trim())
                .filter(Boolean);
            const tradePart = trades.length ? `(${trades.join(", ")})` : "";
            const dosage = String(drug.dosage || "").trim();
            const head = [form, title, tradePart, dosage].filter(Boolean).join(" ").trim();
            const scheme = String(drug.selectedScheme || "").trim();
            return scheme ? `${head} — ${scheme}` : head;
        })
        .filter(Boolean);
}

function syncDoctorInputs(value) {
    recipeDoctorInput.value = value || "";
    settingsDoctorInput.value = value || "";
    doctorModalInput.value = value || "";
}

function getRowState(row) {
    return {
        mode: row.querySelector(".drug-mode-select").value,
        selectedTrade: row.querySelector(".drug-trade-select").value,
        mnn: row.querySelector(".drug-mnn-input").value.trim(),
        russian_name: row.querySelector(".drug-russian-input").value.trim(),
        latin_name: row.querySelector(".drug-latin-input").value.trim(),
        drug_form: row.querySelector(".drug-form-select").value.trim(),
        dosage: row.querySelector(".drug-dosage-select").value.trim(),
        packaging: row.querySelector(".drug-packaging-input").value.trim(),
        dispenseQty: row.querySelector(".drug-dispense-input").value,
        trade_names: Array.from(row.querySelector(".drug-trade-select").options).map((option) => option.value).filter(Boolean),
        form_options: Array.from(row.querySelector(".drug-form-select").options).map((option) => option.value).filter(Boolean),
        dosage_options: Array.from(row.querySelector(".drug-dosage-select").options).map((option) => option.value).filter(Boolean),
        form_dosage_map: JSON.parse(row.dataset.formDosageMap || "{}"),
        scheme_options: collectSchemeOptions(row),
        selectedScheme: row.querySelector(".drug-scheme-input").value.trim(),
        availability: row.querySelector(".drug-availability-badge").textContent.trim(),
    };
}

function getFormState() {
    return {
        card_number: cardNumberInput.value.trim(),
        patient_name: formatNameWithInitials(patientNameInput.value),
        birth_date: normalizeBirthDate(birthDateInput.value),
        doctor_name: recipeDoctorInput.value.trim(),
        drugs: Array.from(document.querySelectorAll(".drug-row")).map(getRowState),
    };
}

function refreshDrugsEmptyState() {
    const emptyState = document.getElementById("drugsEmptyState");
    if (!emptyState) {
        return;
    }
    emptyState.classList.toggle("is-visible", drugRowsContainer.children.length === 0);
}

function clearDrugRows() {
    drugRowsContainer.innerHTML = "";
    refreshDrugsEmptyState();
}

function escapeHtml(value) {
    return String(value || "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
}

function extractDefaultDispenseQty(packaging) {
    const match = String(packaging || "").match(/\d+/);
    return match ? Number(match[0]) : 1;
}

function openPrintPreview(state, pdfPath = "", preview = null) {
    const previewModel = normalizePreviewData(state, preview);
    const { stampHtml, todayLong, patientName, birthDate, doctorName, frontBatches, backFilledBatches, duplexBackSlot, unp } = previewModel;

    function renderDrugCell(drug) {
        if (!drug) {
            return "";
        }
        const lines = Array.isArray(drug.rp_lines) ? drug.rp_lines : [];
        return `
            <p class="drug">${escapeHtml(lines[0] || "")}</p>
            <p>${escapeHtml(lines[1] || "")}</p>
            <p class="sig-small">${escapeHtml(lines[2] || "S.")}</p>
        `;
    }

    function renderFront(drugs) {
        if (!drugs || !drugs.length) {
            return `<div class="blank blank-empty"></div>`;
        }
        const d0 = drugs[0] || null;
        const d1 = drugs[1] || null;
        return `
            <div class="blank">
              <table class="form front">
                <colgroup>
                  <col class="c1" />
                  <col class="c2" />
                  <col class="c3" />
                </colgroup>
                <tr class="h-r0">
                  <td colspan="2" class="org block-tight">${stampHtml}</td>
                  <td class="law-head block-tight">
                    <p>Медицинская документация Форма 1</p>
                    <p>Утверждена</p>
                    <p>Министерством здравоохранения</p>
                    <p>Республики Беларусь</p>
                    <p>УНП организации здравоохранения ${unp}</p>
                  </td>
                </tr>
                <tr class="h-r1">
                  <td colspan="2" class="center middle title">РЕЦЕПТ ВРАЧА</td>
                  <td class="date-box center middle head-label">
                    <p>Дата выписки рецепта</p>
                    <p>${escapeHtml(todayLong)}</p>
                    <p>Рецепт врача действителен с</p>
                    <p>${escapeHtml(todayLong)}</p>
                  </td>
                </tr>
                <tr class="h-r2">
                  <td colspan="3" class="person block-tight">
                    <p>Фамилия, инициалы пациента&nbsp;&nbsp;${escapeHtml(patientName)}</p>
                    <p>Дата рождения&nbsp;&nbsp;${escapeHtml(birthDate)}</p>
                    <p>Фамилия, инициалы врача&nbsp;&nbsp;${escapeHtml(doctorName)}</p>
                    <p>(иного медицинского работника)</p>
                  </td>
                </tr>
                <tr class="h-r3">
                  <td class="rx-label middle">Rp:</td>
                  <td colspan="2" class="rx">${renderDrugCell(d0)}</td>
                </tr>
                <tr class="h-r4">
                  <td class="rx-label middle">Rp:</td>
                  <td colspan="2" class="rx">${renderDrugCell(d1)}</td>
                </tr>
                <tr class="h-r5">
                  <td class="rx-label middle">Rp:</td>
                  <td colspan="2" class="sign-block">
                    <div style="height:10mm;"></div>
                    <p>Подпись врача (иного медицинского работника)</p>
                    <p>Печать врача (иного медицинского работника)</p>
                  </td>
                </tr>
                <tr>
                  <td colspan="3" class="validity">
                    <div>Настоящий рецепт действителен в течение <span class="strike">30 дней</span>, 60 дней</div>
                    <div>(ненужное зачеркнуть)</div>
                  </td>
                </tr>
              </table>
            </div>
        `;
    }

    function renderBack(filled = true) {
        if (!filled) {
            return `<div class="blank blank-empty"></div>`;
        }
        return BACK_BLANK_HTML;
    }

    function renderFrontSheet(batch) {
        return [0, 1, 2, 3]
            .map((slot) => `<div class="blank-slot blank-slot-${slot}">${renderFront(batch[slot])}</div>`)
            .join("");
    }

    function renderBackSheet(batch) {
        return [0, 1, 2, 3]
            .map((frontIdx) => {
                const slot = duplexBackSlot[frontIdx];
                return `<div class="blank-slot blank-slot-${slot}">${renderBack(Boolean(batch[frontIdx]))}</div>`;
            })
            .join("");
    }

    const sheets = [];
    for (let i = 0; i < frontBatches.length; i += 1) {
        const batch = Array.isArray(frontBatches[i]) ? frontBatches[i] : [null, null, null, null];
        const backBatch = Array.isArray(backFilledBatches[i]) ? backFilledBatches[i] : [false, false, false, false];
        sheets.push(buildSheetMarkup(renderFrontSheet(batch), renderBackSheet(backBatch)));
    }

    const previewWindow = window.open("", "_blank", "width=1100,height=820");
    if (!previewWindow) {
        setStatus("Не удалось открыть окно печати.");
        return;
    }

    const printStyles = printBlankCssText || "";
    const escapedPdfPath = escapeHtml(pdfPath || "");
    previewWindow.document.write(buildPreviewDocumentHtml(sheets, printStyles, escapedPdfPath));
    previewWindow.document.close();
    previewWindow.focus();
}

async function loadPrintBlankCss() {
    try {
        const response = await fetch("/css/print_blank.css", { cache: "no-store" });
        if (response.ok) {
            printBlankCssText = await response.text();
        }
    } catch (error) {
        console.warn("print_blank.css not loaded", error);
    }
}

function calculateAge(dateString) {
    if (!dateString) {
        return "";
    }

    const birthDate = parseBirthDate(dateString);
    if (!birthDate) {
        return "";
    }

    const today = new Date();
    let age = today.getFullYear() - birthDate.getFullYear();
    const monthDiff = today.getMonth() - birthDate.getMonth();

    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
        age -= 1;
    }

    return String(age);
}

function parseBirthDate(dateString) {
    const normalized = normalizeBirthDate(dateString);
    const match = String(normalized || "").trim().match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
    if (!match) {
        return null;
    }

    const [, day, month, year] = match;
    const date = new Date(Number(year), Number(month) - 1, Number(day));
    if (
        Number.isNaN(date.getTime()) ||
        date.getDate() !== Number(day) ||
        date.getMonth() !== Number(month) - 1 ||
        date.getFullYear() !== Number(year)
    ) {
        return null;
    }
    return date;
}

function formatBirthDateInput(value) {
    const digits = String(value || "").replace(/\D/g, "").slice(0, 8);
    const day = digits.slice(0, 2);
    const month = digits.slice(2, 4);
    const year = digits.slice(4, 8);

    return [day, month, year].filter(Boolean).join(".");
}

function normalizeBirthDate(value) {
    const raw = String(value || "").trim();
    if (!raw) {
        return "";
    }

    const iso = raw.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/);
    if (iso) {
        return `${String(iso[3]).padStart(2, "0")}.${String(iso[2]).padStart(2, "0")}.${iso[1]}`;
    }

    if (/^\d{2}\.\d{2}\.\d{4}$/.test(raw)) {
        return raw;
    }

    const dotted = raw.match(/^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$/);
    if (dotted) {
        return `${String(dotted[1]).padStart(2, "0")}.${String(dotted[2]).padStart(2, "0")}.${dotted[3]}`;
    }

    return formatBirthDateInput(raw);
}

function composePatientSmartValue(name, birthDate, cardNumber = "") {
    return [String(name || "").trim(), normalizeBirthDate(birthDate), normalizeCardNumber(cardNumber)]
        .filter(Boolean)
        .join(" ");
}

function normalizeCardNumber(value) {
    return String(value || "")
        .trim()
        .replace(/^[№#]\s*/i, "")
        .replace(/\s+/g, "");
}

function extractCardNumber(text) {
    const patterns = [
        /(?<!\d)№?\s*(\d{3,}\/\d{2})(?!\d)/i,
        /(?<!\d)№?\s*(\d{5,})(?!\d)/i,
    ];

    for (const pattern of patterns) {
        const match = text.match(pattern);
        if (!match) {
            continue;
        }
        const card = normalizeCardNumber(match[1]);
        const remainder = `${text.slice(0, match.index)} ${text.slice(match.index + match[0].length)}`;
        return { card_number: card, text: remainder };
    }

    return { card_number: "", text };
}

function isInitialToken(word) {
    const value = String(word || "").trim();
    if (!value) {
        return false;
    }
    if (/^[A-Za-zА-Яа-яЁё]\.?$/u.test(value)) {
        return true;
    }
    return /^(?:[A-Za-zА-Яа-яЁё]\.){1,3}$/u.test(value)
        || /^(?:[A-Za-zА-Яа-яЁё]\.){1,2}[A-Za-zА-Яа-яЁё]$/u.test(value);
}

function initialsFromPart(part) {
    const value = String(part || "").trim();
    if (isInitialToken(value)) {
        return (value.match(/[A-Za-zА-Яа-яЁё]/gu) || [])
            .map((letter) => `${letter.toUpperCase()}.`)
            .join("");
    }
    const letter = value.replace(/\./g, "").charAt(0);
    return letter ? `${letter.toUpperCase()}.` : "";
}

function isPersonNameWord(word) {
    const value = String(word || "").trim();
    if (!value) {
        return false;
    }
    if (isInitialToken(value)) {
        return true;
    }
    return /^[A-Za-zА-Яа-яЁё]{2,}(?:-[A-Za-zА-Яа-яЁё]+)*$/u.test(value);
}

function capitalizePersonWord(word) {
    const value = String(word || "").trim();
    if (!value) {
        return "";
    }
    if (isInitialToken(value)) {
        return initialsFromPart(value);
    }
    return value.charAt(0).toUpperCase() + value.slice(1);
}

function cleanPatientNameText(text) {
    return String(text || "")
        .replace(/\([^)]*\)?/g, " ")
        .replace(/\[[^\]]*\]?/g, " ")
        .replace(/[()[\]{}<>«»"'`´]/g, " ")
        .replace(/[,;|·•]+/g, " ")
        .replace(/\b(?:г\.?р\.?|года?|р\.?)\b/gi, " ")
        .replace(/\s+/g, " ")
        .replace(/^[\s.,;:/\-–—]+|[\s.,;:/\-–—]+$/g, "")
        .trim();
}

function nameSlotCount(parts) {
    return parts.reduce((total, part) => {
        const letters = part.match(/[A-Za-zА-Яа-яЁё]/gu) || [];
        if (isInitialToken(part) && letters.length > 1) {
            return total + letters.length;
        }
        return total + 1;
    }, 0);
}

function extractPersonNameParts(fullName) {
    const words = cleanPatientNameText(fullName).split(/\s+/).filter(Boolean);
    const parts = [];

    for (const word of words) {
        if (!isPersonNameWord(word)) {
            if (parts.length) {
                break;
            }
            continue;
        }
        parts.push(word);
        if (nameSlotCount(parts) >= 3) {
            break;
        }
    }

    return parts;
}

function formatNameWithInitials(fullName) {
    const parts = extractPersonNameParts(fullName);
    if (!parts.length) {
        return "";
    }

    if (isInitialToken(parts[0])) {
        return initialsFromPart(parts[0]);
    }

    const surname = capitalizePersonWord(parts[0]).replace(/\.$/, "");
    if (parts.length === 1) {
        return surname;
    }

    const initials = parts.slice(1).map(initialsFromPart).join("");
    return `${surname} ${initials}`.trim();
}

function parsePatientSmartInput(raw) {
    let text = String(raw || "")
        .replace(/\u00a0/g, " ")
        .replace(/[|·•]+/g, " ")
        .trim();

    let birthDate = "";
    let matched = null;

    const patterns = [
        /(\d{1,2})[./-](\d{1,2})[./-](\d{4})/,
        /(\d{4})[./-](\d{1,2})[./-](\d{1,2})/,
    ];

    for (const pattern of patterns) {
        const match = text.match(pattern);
        if (!match) {
            continue;
        }
        matched = match;
        if (match[1].length === 4) {
            birthDate = normalizeBirthDate(`${match[1]}-${match[2]}-${match[3]}`);
        } else {
            birthDate = normalizeBirthDate(`${match[1]}.${match[2]}.${match[3]}`);
        }
        break;
    }

    if (matched) {
        text = `${text.slice(0, matched.index)} ${text.slice(matched.index + matched[0].length)}`;
    }

    const cardParsed = extractCardNumber(text);
    text = cardParsed.text;
    const cardNumber = cardParsed.card_number;

    const nameParts = extractPersonNameParts(text);
    const fullName = nameParts.join(" ");
    const patientName = formatNameWithInitials(fullName);

    return {
        patient_name: patientName,
        birth_date: birthDate,
        card_number: cardNumber,
        full_name: fullName,
    };
}

function applyPatientSmartInput(options = {}) {
    const parsed = parsePatientSmartInput(patientSmartInput.value);
    patientNameInput.value = parsed.patient_name;
    birthDateInput.value = parsed.birth_date;
    ageValue.value = calculateAge(parsed.birth_date);
    // Всегда синхронизируем карту из единого поля (в т.ч. очищаем).
    cardNumberInput.value = parsed.card_number || "";

    const parts = [];
    if (parsed.patient_name) {
        parts.push(`<span>${escapeHtml(parsed.patient_name)}</span>`);
    }
    if (parsed.birth_date) {
        parts.push(`<span>${escapeHtml(parsed.birth_date)}</span>`);
    }
    if (ageValue.value) {
        parts.push(`<span>${escapeHtml(ageValue.value)} лет</span>`);
    }
    if (parsed.card_number) {
        parts.push(
            `<button type="button" class="patient-card-link" data-card="${escapeHtml(parsed.card_number)}" title="Загрузить прошлое лечение по этой карте">карта ${escapeHtml(parsed.card_number)}</button>`
            + `<span class="patient-card-hint"> — нажмите, чтобы загрузить прошлое лечение</span>`,
        );
    }

    if (patientParsedHint) {
        if (parts.length) {
            patientParsedHint.innerHTML = parts.join(" · ");
            patientParsedHint.classList.remove("is-empty");
        } else {
            patientParsedHint.textContent = "Вставьте ФИО, дату и номер карты — всё разложится само";
            patientParsedHint.classList.add("is-empty");
        }
    }

    if (options.normalizeField) {
        patientSmartInput.value = composePatientSmartValue(
            parsed.patient_name,
            parsed.birth_date,
            parsed.card_number,
        );
    }

    return parsed;
}

function syncPatientSmartFromFields() {
    patientSmartInput.value = composePatientSmartValue(
        patientNameInput.value,
        birthDateInput.value,
        cardNumberInput.value,
    );
    applyPatientSmartInput();
}

function initAgeField() {
    initPatientSmartInput();
}

function initPatientSmartInput() {
    if (!patientSmartInput || patientSmartInput.dataset.bound) {
        return;
    }

    patientSmartInput.addEventListener("input", () => {
        applyPatientSmartInput();
    });
    patientSmartInput.addEventListener("paste", () => {
        window.setTimeout(() => applyPatientSmartInput(), 0);
    });
    patientSmartInput.addEventListener("blur", () => {
        applyPatientSmartInput({ normalizeField: true });
    });
    patientSmartInput.dataset.bound = "true";
    applyPatientSmartInput();
    bindPatientCardHistoryClick();
}

async function loadHistoryByCardNumber(cardNumber, options = {}) {
    const card = String(cardNumber || "").trim();
    if (!card) {
        setStatus("Введите номер карты для загрузки истории.");
        return false;
    }
    if (!window.eel || typeof window.eel.load_last_history_entry !== "function") {
        setStatus("Backend недоступен для загрузки истории.");
        return false;
    }

    try {
        const state = await window.eel.load_last_history_entry(card)();
        if (!state) {
            setStatus(`История по карте ${card} не найдена.`);
            return false;
        }

        const keepPatient = Boolean(options.keepCurrentPatient);
        const currentName = patientNameInput.value;
        const currentBirth = birthDateInput.value;

        restoreFormState({
            ...state,
            card_number: card,
            patient_name: keepPatient && currentName ? currentName : (state.patient_name || ""),
            birth_date: keepPatient && currentBirth ? currentBirth : (state.birth_date || ""),
        }, {
            keepCardNumber: true,
            keepTreatmentParse: true,
        });

        const drugCount = Array.isArray(state.drugs)
            ? state.drugs.filter((drug) => drug.mnn || drug.russian_name).length
            : 0;
        setStatus(
            drugCount
                ? `Загружено прошлое лечение по карте ${card} (${drugCount} преп.).`
                : `Запись по карте ${card} загружена, препаратов в ней нет.`,
        );
        return true;
    } catch (error) {
        console.error(error);
        setStatus("Не удалось загрузить историю.");
        return false;
    }
}

function bindPatientCardHistoryClick() {
    if (!patientParsedHint || patientParsedHint.dataset.cardBound) {
        return;
    }
    patientParsedHint.addEventListener("click", async (event) => {
        const target = event.target.closest(".patient-card-link");
        if (!target) {
            return;
        }
        event.preventDefault();
        const card = target.getAttribute("data-card") || cardNumberInput.value;
        await loadHistoryByCardNumber(card, { keepCurrentPatient: true });
    });
    patientParsedHint.dataset.cardBound = "true";
}

function availabilityMeta(status) {
    if (status === "low") {
        return { label: "Мало", className: "status-low" };
    }
    if (status === "none") {
        return { label: "Нет", className: "status-none" };
    }
    if (status === "unknown") {
        return { label: "?", className: "status-none" };
    }
    return { label: "Есть", className: "status-good" };
}

function availabilityFromLabel(label) {
    const text = String(label || "").trim();
    if (text === "Мало") {
        return "low";
    }
    if (text === "Нет" || text.startsWith("Нет ") || text === "—") {
        return "none";
    }
    if (text === "?" || text === "…" || text === "Нет данных") {
        return "unknown";
    }
    return "good";
}

function normalizeText(value) {
    return String(value || "").trim().toLowerCase().replace(/\s+/g, " ");
}

function fillOptions(select, options, selectedValue) {
    select.innerHTML = "";

    if (!options.length) {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = "Выбрать";
        select.appendChild(option);
        return;
    }

    options.forEach((optionValue) => {
        const option = document.createElement("option");
        option.value = optionValue;
        option.textContent = optionValue;
        if (optionValue === selectedValue) {
            option.selected = true;
        }
        select.appendChild(option);
    });
}

function collectSchemeOptions(row) {
    const list = row.querySelector(".drug-scheme-datalist");
    const values = Array.from(list?.options || [])
        .map((option) => option.value.trim())
        .filter(Boolean);
    const selected = row.querySelector(".drug-scheme-input")?.value.trim() || "";
    if (selected && !values.includes(selected)) {
        values.push(selected);
    }
    return values;
}

function normalizeSchemeLines(values) {
    const normalized = [];
    for (const value of values || []) {
        const text = String(value || "").trim();
        if (text && !normalized.includes(text)) {
            normalized.push(text);
        }
    }
    return normalized;
}

function ensureSchemeListId(row) {
    const input = row.querySelector(".drug-scheme-input");
    const list = row.querySelector(".drug-scheme-datalist");
    if (!input || !list) {
        return;
    }
    if (!list.id) {
        list.id = `scheme-list-${Math.random().toString(36).slice(2, 10)}`;
    }
    input.setAttribute("list", list.id);
}

function fillSchemeOptions(row, options, selectedValue) {
    ensureSchemeListId(row);
    const list = row.querySelector(".drug-scheme-datalist");
    const input = row.querySelector(".drug-scheme-input");
    const values = [];
    for (const optionValue of options || []) {
        const text = String(optionValue || "").trim();
        if (text && !values.includes(text)) {
            values.push(text);
        }
    }
    const selected = String(selectedValue || "").trim();
    if (selected && !values.includes(selected)) {
        values.unshift(selected);
    }

    list.innerHTML = "";
    values.forEach((value) => {
        const option = document.createElement("option");
        option.value = value;
        list.appendChild(option);
    });
    input.value = selected || values[0] || "";
}

function resolveDrugByQuery(query) {
    const normalizedQuery = normalizeText(query);
    if (!normalizedQuery || normalizedQuery.length < 2) {
        return null;
    }

    const exactMatch = catalogDrugs.find((drug) => {
        const candidates = [
            drug.mnn,
            drug.russian_name,
            drug.latin_name,
            ...(drug.trade_names || []),
            ...(drug.search_aliases || []),
        ];
        return candidates.some((candidate) => normalizeText(candidate) === normalizedQuery);
    });
    if (exactMatch) {
        return exactMatch;
    }

    return catalogDrugs.find((drug) => {
        const candidates = [
            drug.mnn,
            drug.russian_name,
            drug.latin_name,
            ...(drug.trade_names || []),
            ...(drug.search_aliases || []),
        ];
        return candidates.some((candidate) => normalizeText(candidate).includes(normalizedQuery));
    }) || null;
}

function findDrugsByQuery(query) {
    const normalizedQuery = normalizeText(query);
    if (!normalizedQuery || normalizedQuery.length < 2) {
        return [];
    }

    return catalogDrugs.filter((drug) => {
        const candidates = [
            drug.mnn,
            drug.russian_name,
            drug.latin_name,
            ...(drug.trade_names || []),
            ...(drug.search_aliases || []),
        ];
        return candidates.some((candidate) => normalizeText(candidate).includes(normalizedQuery));
    }).slice(0, 8);
}

function renderDirectoryTable() {
    directoryTableBody.innerHTML = "";
    for (const drug of catalogDrugs) {
        const row = document.createElement("tr");
        row.innerHTML = `
            <td>${escapeHtml(drug.category)}</td>
            <td>${escapeHtml(drug.mnn)}</td>
            <td>${escapeHtml(drug.russian_name)}</td>
            <td>${escapeHtml(drug.latin_name)}</td>
            <td>${escapeHtml((drug.form_options || [drug.drug_form]).join(", "))}</td>
            <td>${escapeHtml((drug.dosage_options || [drug.dosage]).join(", "))}</td>
            <td>${escapeHtml(drug.packaging)}</td>
            <td>${escapeHtml((drug.trade_names || []).join(", "))}</td>
        `;
        directoryTableBody.appendChild(row);
    }
}

function renderDirectoryArchive(drugs) {
    if (!directoryArchiveBody) {
        return;
    }
    directoryArchiveBody.innerHTML = "";
    const rows = Array.isArray(drugs) ? drugs : [];
    if (!rows.length) {
        directoryArchiveBody.innerHTML = `<tr><td colspan="8" class="text-muted">Архив пуст</td></tr>`;
        return;
    }
    for (const drug of rows) {
        const row = document.createElement("tr");
        row.className = "directory-archive-row";
        row.innerHTML = `
            <td>${escapeHtml(drug.category)}</td>
            <td>${escapeHtml(drug.mnn)}</td>
            <td>${escapeHtml(drug.russian_name)}</td>
            <td>${escapeHtml(drug.latin_name)}</td>
            <td>${escapeHtml((drug.form_options || [drug.drug_form]).join(", "))}</td>
            <td>${escapeHtml((drug.dosage_options || [drug.dosage]).join(", "))}</td>
            <td>${escapeHtml((drug.trade_names || []).join(", "))}</td>
            <td>${escapeHtml(drug.archive_reason || "Архив")}</td>
        `;
        directoryArchiveBody.appendChild(row);
    }
}

async function loadArchivedDrugsFromBackend() {
    if (!directoryArchiveBody) {
        return;
    }
    if (!window.eel || typeof window.eel.get_archived_drugs !== "function") {
        directoryArchiveBody.innerHTML = `<tr><td colspan="8" class="text-muted">Архив недоступен в этой версии backend</td></tr>`;
        return;
    }
    try {
        const archived = await window.eel.get_archived_drugs()();
        renderDirectoryArchive(archived);
    } catch (error) {
        console.error(error);
        directoryArchiveBody.innerHTML = `<tr><td colspan="8" class="text-muted">Не удалось загрузить архив</td></tr>`;
    }
}

function updateCatalogDrugSchemes(mnn, schemeOptions, hasCustomScheme = true) {
    const normalized = normalizeSchemeLines(schemeOptions);
    const match = catalogDrugs.find((drug) => drug.mnn === mnn);
    if (match) {
        match.scheme_options = normalized;
        match.has_custom_scheme = hasCustomScheme;
    }
    Array.from(document.querySelectorAll(".drug-row")).forEach((row) => {
        const rowState = getRowState(row);
        if (rowState.mnn !== mnn) {
            return;
        }
        fillSchemeOptions(row, normalized, rowState.selectedScheme);
    });
}

function syncTradeAvailability(row, announceChange) {
    const modeSelect = row.querySelector(".drug-mode-select");
    const tradeSelect = row.querySelector(".drug-trade-select");
    const isTradeMode = modeSelect.value === "trade";
    tradeSelect.disabled = !isTradeMode;

    if (announceChange) {
        setStatus(isTradeMode
            ? "Режим выписки переключен на торговое название."
            : "Режим выписки переключен на МНН.");
    }
}

function bindModeSelect(row) {
    const modeSelect = row.querySelector(".drug-mode-select");
    if (!modeSelect.dataset.bound) {
        modeSelect.addEventListener("change", () => syncTradeAvailability(row, true));
        modeSelect.dataset.bound = "true";
    }
    syncTradeAvailability(row, false);
}

function bindTradeSelect(row) {
    const tradeSelect = row.querySelector(".drug-trade-select");
    if (!tradeSelect.dataset.bound) {
        tradeSelect.addEventListener("change", () => {
            const details = JSON.parse(row.dataset.tradeDetails || "{}");
            const selectedTrade = tradeSelect.value;
            const selectedDetails = details[selectedTrade];

            if (selectedDetails) {
                row.querySelector(".drug-packaging-input").value = selectedDetails.packaging || row.querySelector(".drug-packaging-input").value;
                row.querySelector(".drug-dispense-input").value = selectedDetails.dispense_qty || row.querySelector(".drug-dispense-input").value;
                setStatus(`Для торгового названия ${selectedTrade} подставлены упаковка и количество.`);
            }
        });
        tradeSelect.dataset.bound = "true";
    }
}

function bindSchemeInput(row) {
    const schemeInput = row.querySelector(".drug-scheme-input");
    if (!schemeInput || schemeInput.dataset.bound) {
        return;
    }
    ensureSchemeListId(row);
    const persistScheme = async () => {
        const value = schemeInput.value.trim();
        if (value) {
            const list = row.querySelector(".drug-scheme-datalist");
            const exists = Array.from(list.options).some((option) => option.value === value);
            if (!exists) {
                const option = document.createElement("option");
                option.value = value;
                list.appendChild(option);
            }
            const state = getRowState(row);
            if (window.eel && typeof window.eel.save_drug_schemes === "function" && state.mnn) {
                try {
                    const result = await window.eel.save_drug_schemes(state.mnn, normalizeSchemeLines(collectSchemeOptions(row)))();
                    updateCatalogDrugSchemes(state.mnn, result.scheme_options || collectSchemeOptions(row), true);
                    setStatus("Схема приёма сохранена и будет предложена в следующий раз.");
                } catch (error) {
                    console.error(error);
                    setStatus("Схема сохранена локально, но не записана в общий список.");
                }
            } else {
                setStatus("Схема приёма сохранена.");
            }
        }
        scheduleAutosave();
    };
    schemeInput.addEventListener("input", () => scheduleAutosave());
    schemeInput.addEventListener("change", persistScheme);
    schemeInput.addEventListener("blur", persistScheme);
    schemeInput.dataset.bound = "true";
}

function dosagesForForm(row, form) {
    const map = JSON.parse(row.dataset.formDosageMap || "{}");
    const mapped = map[form];
    if (Array.isArray(mapped) && mapped.length) {
        return mapped;
    }
    return Array.from(row.querySelector(".drug-dosage-select").options)
        .map((option) => option.value)
        .filter(Boolean);
}

function bindFormDosageSelects(row) {
    const formSelect = row.querySelector(".drug-form-select");
    const dosageSelect = row.querySelector(".drug-dosage-select");
    if (!formSelect.dataset.bound) {
        formSelect.addEventListener("change", () => {
            const doses = dosagesForForm(row, formSelect.value);
            const keep = doses.includes(dosageSelect.value) ? dosageSelect.value : (doses[0] || "");
            fillOptions(dosageSelect, doses, keep);
            setStatus(`Форма: ${formSelect.value}. Доступные дозировки обновлены.`);
            scheduleAutosave();
        });
        formSelect.dataset.bound = "true";
    }
    if (!dosageSelect.dataset.bound) {
        dosageSelect.addEventListener("change", () => {
            scheduleAutosave();
        });
        dosageSelect.dataset.bound = "true";
    }
}

function bindRowRemoval(row) {
    row.querySelector(".remove-row-btn").addEventListener("click", () => {
        row.remove();
        refreshDrugsEmptyState();
        setStatus("Строка препарата удалена.");
    });
}

function populateRow(row, drug, options = {}) {
    row.dataset.tradeDetails = JSON.stringify(drug.trade_details || {});
    const formOptions = drug.form_options?.length
        ? drug.form_options
        : (drug.drug_form ? [drug.drug_form] : ["Tab."]);
    const formDosageMap = drug.form_dosage_map && Object.keys(drug.form_dosage_map).length
        ? drug.form_dosage_map
        : Object.fromEntries(formOptions.map((form) => [form, drug.dosage_options?.length ? drug.dosage_options : (drug.dosage ? [drug.dosage] : [])]));
    row.dataset.formDosageMap = JSON.stringify(formDosageMap);

    row.querySelector(".drug-mnn-input").value = drug.mnn || "";
    row.querySelector(".drug-russian-input").value = drug.russian_name || "";
    row.querySelector(".drug-latin-input").value = drug.latin_name || "";
    row.querySelector(".drug-packaging-input").value = drug.packaging || "";
    const hasExplicitDispense = options.dispenseQty !== undefined && options.dispenseQty !== null && options.dispenseQty !== "";
    const baseDispenseQty = hasExplicitDispense
        ? options.dispenseQty
        : (drug.dispense_qty || extractDefaultDispenseQty(drug.packaging));
    row.querySelector(".drug-dispense-input").value = baseDispenseQty;

    const formSelect = row.querySelector(".drug-form-select");
    const dosageSelect = row.querySelector(".drug-dosage-select");
    const selectedForm = options.drug_form || drug.drug_form || formOptions[0] || "";
    fillOptions(formSelect, formOptions, selectedForm);
    const dosesForSelected = formDosageMap[selectedForm] || drug.dosage_options || (drug.dosage ? [drug.dosage] : []);
    const selectedDosage = options.dosage || drug.dosage || dosesForSelected[0] || "";
    fillOptions(dosageSelect, dosesForSelected, selectedDosage);

    const tradeSelect = row.querySelector(".drug-trade-select");
    const selectedTrade = options.selectedTrade || "";
    fillOptions(tradeSelect, drug.trade_names || [], selectedTrade);
    fillSchemeOptions(
        row,
        drug.scheme_options || [],
        options.selectedScheme || drug.selectedScheme || drug.scheme_options?.[0] || "",
    );

    const selectedDetails = (drug.trade_details || {})[selectedTrade];
    if (selectedDetails && !hasExplicitDispense) {
        // Не перетираем № из разбора дневника (например №90) фасовкой торгового.
        row.querySelector(".drug-packaging-input").value = selectedDetails.packaging || row.querySelector(".drug-packaging-input").value;
        row.querySelector(".drug-dispense-input").value = selectedDetails.dispense_qty || extractDefaultDispenseQty(selectedDetails.packaging);
    }
}

function hideSearchDropdown() {
    drugSearchDropdown.hidden = true;
    drugSearchDropdown.innerHTML = "";
    searchMatches = [];
    searchActiveIndex = 0;
}

function renderSearchDropdown(matches, activeIndex = 0) {
    searchMatches = matches;
    searchActiveIndex = matches.length ? Math.max(0, Math.min(activeIndex, matches.length - 1)) : 0;
    drugSearchDropdown.innerHTML = "";

    if (!matches.length) {
        hideSearchDropdown();
        return;
    }

    matches.forEach((drug, index) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `drug-search-item${index === searchActiveIndex ? " is-active" : ""}`;
        button.innerHTML = `
            <div class="drug-search-item-title">${escapeHtml(drug.russian_name)} · ${escapeHtml(drug.mnn)}</div>
            <div class="drug-search-item-meta">${escapeHtml((drug.form_options || [drug.drug_form]).join("/"))} · ${escapeHtml((drug.dosage_options || [drug.dosage]).slice(0, 4).join(", "))} · ${(drug.trade_names || []).slice(0, 3).map(escapeHtml).join(", ")}</div>
        `;
        button.addEventListener("mousedown", (event) => {
            event.preventDefault();
            addDrugFromSearch(drug);
        });
        drugSearchDropdown.appendChild(button);
    });

    drugSearchDropdown.hidden = false;
}

function addDrugFromSearch(drug) {
    if (!drug) {
        return;
    }

    addDrugRow(drug, {
        mode: "mnn",
        availability: "unknown",
        drug_form: drug.drug_form,
        dosage: drug.dosage,
    });
    globalDrugSearch.value = "";
    hideSearchDropdown();
    scheduleAutosave();
    setStatus(`Добавлен: ${drug.russian_name}.`);
    globalDrugSearch.focus();

    const row = drugRowsContainer.lastElementChild;
    if (row) {
        refreshRowAvailability(row);
    }
}

function rowAvailabilityQuery(row) {
    const russian = row.querySelector(".drug-russian-input")?.value.trim() || "";
    const trade = row.querySelector(".drug-trade-select")?.value.trim() || "";
    const mnn = row.querySelector(".drug-mnn-input")?.value.trim() || "";
    const aliases = [];
    if (trade && trade !== russian) {
        aliases.push(trade);
    }
    Array.from(row.querySelector(".drug-trade-select")?.options || [])
        .map((option) => option.value.trim())
        .filter((value) => value && value !== russian && !aliases.includes(value))
        .slice(0, 3)
        .forEach((value) => aliases.push(value));
    return {
        query: russian || trade || mnn,
        aliases,
    };
}

async function refreshRowAvailability(row, query = null) {
    const autoCheck = document.getElementById("autoAvailabilityOnAdd");
    if (autoCheck && !autoCheck.checked) {
        setAvailabilityBadge(row, "none");
        const badge = row.querySelector(".drug-availability-badge");
        if (badge) {
            badge.textContent = "—";
            badge.title = "Автопроверка отключена в Настройках";
        }
        return;
    }
    if (!window.eel || typeof window.eel.check_drug_availability !== "function") {
        return;
    }
    const request = query
        ? { query, aliases: [] }
        : rowAvailabilityQuery(row);
    if (!request.query) {
        return;
    }
    setAvailabilityBadge(row, "unknown");
    const badge = row.querySelector(".drug-availability-badge");
    if (badge) {
        badge.textContent = "…";
        badge.title = "Проверяю tabletka.by…";
    }
    try {
        const result = await window.eel.check_drug_availability(request.query, request.aliases)();
        if (result && result.status) {
            setAvailabilityBadge(row, result.status);
            if (result.label && result.status !== "good" && result.status !== "low" && result.status !== "none") {
                badge.textContent = result.label;
            }
            if (badge) {
                badge.title = result.message || result.label || "";
            }
            setStatus(`${request.query}: ${result.label} (${result.pharmacies_minsk || 0} аптек в Минске)`);
        }
    } catch (error) {
        console.error(error);
        if (badge) {
            badge.textContent = "?";
            badge.title = "Не удалось проверить tabletka.by";
        }
    }
}

async function refreshAvailabilityTable() {
    const body = document.getElementById("availabilityTableBody");
    const button = document.getElementById("refreshAvailabilityBtn");
    if (!body) {
        return;
    }
    if (!window.eel || typeof window.eel.refresh_catalog_availability !== "function") {
        body.innerHTML = "<tr><td colspan=\"4\">Backend недоступен</td></tr>";
        return;
    }

    if (button) {
        button.disabled = true;
    }
    body.innerHTML = "<tr><td colspan=\"4\">Проверяю tabletka.by…</td></tr>";
    setStatus("Проверка наличия в Минске…");

    try {
        const payload = await window.eel.refresh_catalog_availability(15)();
        const rows = payload?.rows || [];
        if (!rows.length) {
            body.innerHTML = "<tr><td colspan=\"4\">Нет данных</td></tr>";
            return;
        }
        body.innerHTML = rows.map((row) => `
            <tr>
                <td>${escapeHtml(row.russian_name)}</td>
                <td><span class="status-badge ${availabilityMeta(row.status).className}">${escapeHtml(row.label)}</span></td>
                <td>${escapeHtml(row.pharmacies_minsk)}</td>
                <td>${escapeHtml(row.message || "")}</td>
            </tr>
        `).join("");
        setStatus(`Наличие обновлено для ${rows.length} препаратов (Минск).`);
    } catch (error) {
        console.error(error);
        body.innerHTML = "<tr><td colspan=\"4\">Ошибка запроса к tabletka.by</td></tr>";
        setStatus("Не удалось обновить наличие.");
    } finally {
        if (button) {
            button.disabled = false;
        }
    }
}

function bindGlobalDrugSearch() {
    if (!globalDrugSearch || globalDrugSearch.dataset.bound) {
        return;
    }

    globalDrugSearch.addEventListener("input", () => {
        const matches = findDrugsByQuery(globalDrugSearch.value);
        renderSearchDropdown(matches, 0);
    });

    globalDrugSearch.addEventListener("keydown", (event) => {
        if (event.key === "ArrowDown") {
            if (!searchMatches.length) {
                return;
            }
            event.preventDefault();
            renderSearchDropdown(searchMatches, searchActiveIndex + 1);
            return;
        }

        if (event.key === "ArrowUp") {
            if (!searchMatches.length) {
                return;
            }
            event.preventDefault();
            renderSearchDropdown(searchMatches, searchActiveIndex - 1);
            return;
        }

        if (event.key === "Escape") {
            hideSearchDropdown();
            return;
        }

        if (event.key === "Enter") {
            event.preventDefault();
            const matches = searchMatches.length ? searchMatches : findDrugsByQuery(globalDrugSearch.value);
            if (!matches.length) {
                setStatus("Ничего не найдено.");
                return;
            }
            const selected = matches[Math.max(0, Math.min(searchActiveIndex, matches.length - 1))]
                || resolveDrugByQuery(globalDrugSearch.value);
            addDrugFromSearch(selected);
        }
    });

    globalDrugSearch.addEventListener("blur", () => {
        window.setTimeout(() => hideSearchDropdown(), 150);
    });

    globalDrugSearch.dataset.bound = "true";
}

function setAvailabilityBadge(row, status = "good") {
    const badge = row.querySelector(".drug-availability-badge");
    const meta = availabilityMeta(status);
    badge.textContent = meta.label;
    badge.className = `status-badge drug-availability-badge ${meta.className}`;
}

function createEmptyRowData() {
    return {
        mnn: "",
        russian_name: "",
        latin_name: "",
        drug_form: "Tab.",
        dosage: "",
        packaging: "",
        form_options: ["Tab.", "Caps."],
        dosage_options: [],
        form_dosage_map: { "Tab.": [], "Caps.": [] },
        trade_names: [],
        scheme_options: ["по 1 таблетке утром", "по 1 таблетке вечером", "по 1/2 таблетки на ночь"],
    };
}

function addDrugRow(drug = null, options = {}) {
    const fragment = rowTemplate.content.cloneNode(true);
    const row = fragment.querySelector(".drug-row");

    populateRow(row, drug || createEmptyRowData(), options);
    row.querySelector(".drug-mode-select").value = options.mode || "mnn";
    bindModeSelect(row);
    bindTradeSelect(row);
    bindFormDosageSelects(row);
    bindSchemeInput(row);
    bindRowRemoval(row);
    setAvailabilityBadge(row, options.availability || "unknown");

    drugRowsContainer.appendChild(row);
    refreshDrugsEmptyState();
}

function clearTreatmentParseInput(message = "Система найдёт препараты в каталоге и добавит их в рецепт") {
    if (treatmentParseInput) {
        treatmentParseInput.value = "";
    }
    if (treatmentParseHint) {
        treatmentParseHint.textContent = message;
    }
}

function restoreFormState(state, options = {}) {
    if (!state) {
        return;
    }

    if (!options.keepCardNumber) {
        cardNumberInput.value = state.card_number || "";
    }
    patientNameInput.value = state.patient_name || "";
    birthDateInput.value = normalizeBirthDate(state.birth_date || "");
    syncPatientSmartFromFields();
    syncDoctorInputs(state.doctor_name || recipeDoctorInput.value || "");
    clearDrugRows();
    if (!options.keepTreatmentParse) {
        clearTreatmentParseInput();
    }

    const drugs = Array.isArray(state.drugs) ? state.drugs : [];
    for (const drug of drugs) {
        if (!drug.mnn && !drug.russian_name) {
            continue;
        }

        const catalogMatch = catalogDrugs.find((item) => item.mnn === drug.mnn) || {};
        addDrugRow(
            {
                ...catalogMatch,
                ...drug,
                form_options: drug.form_options?.length ? drug.form_options : catalogMatch.form_options,
                dosage_options: drug.dosage_options?.length ? drug.dosage_options : catalogMatch.dosage_options,
                form_dosage_map: (drug.form_dosage_map && Object.keys(drug.form_dosage_map).length)
                    ? drug.form_dosage_map
                    : catalogMatch.form_dosage_map,
                trade_names: drug.trade_names?.length ? drug.trade_names : catalogMatch.trade_names,
                scheme_options: drug.scheme_options?.length ? drug.scheme_options : catalogMatch.scheme_options,
                trade_details: Object.keys(drug.trade_details || {}).length
                    ? drug.trade_details
                    : catalogMatch.trade_details,
            },
            {
                mode: drug.mode || "mnn",
                selectedTrade: drug.selectedTrade || "",
                drug_form: drug.drug_form,
                dosage: drug.dosage,
                dispenseQty: drug.dispenseQty || 1,
                selectedScheme: drug.selectedScheme || "",
                availability: "unknown",
            },
        );
    }

    ageValue.value = calculateAge(birthDateInput.value);

    // Перепроверяем наличие, чтобы не показывать устаревшее «Нет» из автосохранения
    Array.from(drugRowsContainer.querySelectorAll(".drug-row")).forEach((row) => {
        refreshRowAvailability(row);
    });
}

function initDoctorModal() {
    const modalElement = document.getElementById("doctorModal");
    if (!modalElement || typeof bootstrap === "undefined") {
        return null;
    }

    doctorModalInstance = new bootstrap.Modal(modalElement);
    return doctorModalInstance;
}

async function saveDoctorNameToBackend(doctorName) {
    const trimmedName = String(doctorName || "").trim();
    syncDoctorInputs(trimmedName);

    if (!window.eel || typeof window.eel.save_doctor_name !== "function") {
        setStatus("Имя врача обновлено локально.");
        return;
    }

    try {
        await window.eel.save_doctor_name(trimmedName)();
        setStatus(trimmedName ? "Врач сохранен." : "Имя врача очищено.");
    } catch (error) {
        console.error(error);
        setStatus("Не удалось сохранить врача.");
    }
}

function bindDoctorControls() {
    const saveDoctor = async () => {
        await saveDoctorNameToBackend(settingsDoctorInput.value || doctorModalInput.value || recipeDoctorInput.value);
    };

    settingsDoctorInput.addEventListener("change", async () => {
        await saveDoctor();
    });
    saveDoctorBtn.addEventListener("click", async () => {
        await saveDoctorNameToBackend(doctorModalInput.value);
        if (doctorModalInstance) {
            doctorModalInstance.hide();
        }
    });
    changeDoctorBtn.addEventListener("click", () => {
        doctorModalInput.value = settingsDoctorInput.value || recipeDoctorInput.value || "";
        if (doctorModalInstance) {
            doctorModalInstance.show();
        }
    });
}

async function loadCatalogFromBackend() {
    if (!window.eel || typeof window.eel.get_catalog_drugs !== "function") {
        setStatus("Backend пока недоступен, используется встроенный демо-каталог.");
        return;
    }

    try {
        const backendCatalog = await window.eel.get_catalog_drugs()();
        if (Array.isArray(backendCatalog) && backendCatalog.length) {
            catalogDrugs = backendCatalog;
            setStatus(`Каталог загружен из SQLite: ${backendCatalog.length} препаратов.`);
        }
    } catch (error) {
        console.error(error);
        setStatus("Не удалось загрузить каталог из backend, используется демо-список.");
    }
}

async function loadSettingsFromBackend() {
    if (!window.eel || typeof window.eel.get_app_settings !== "function") {
        return;
    }

    try {
        const settings = await window.eel.get_app_settings()();
        const doctorName = settings?.doctor_name || "";
        syncDoctorInputs(doctorName);

        if (!doctorName && doctorModalInstance) {
            window.setTimeout(() => doctorModalInstance.show(), 500);
        }
    } catch (error) {
        console.error(error);
        setStatus("Не удалось загрузить настройки врача.");
    }
}

async function saveAutosaveState() {
    if (!window.eel || typeof window.eel.save_autosave !== "function") {
        return;
    }

    try {
        await window.eel.save_autosave(getFormState())();
    } catch (error) {
        console.error(error);
    }
}

function scheduleAutosave() {
    window.clearTimeout(autosaveTimer);
    autosaveTimer = window.setTimeout(() => {
        saveAutosaveState();
    }, 500);
}

async function restoreAutosaveState() {
    if (!window.eel || typeof window.eel.load_autosave !== "function") {
        return;
    }

    try {
        const autosave = await window.eel.load_autosave()();
        if (autosave && Array.isArray(autosave.drugs) && autosave.drugs.length) {
            restoreFormState(autosave);
            setStatus("Форма восстановлена из автосохранения.");
        }
    } catch (error) {
        console.error(error);
    }
}

async function refreshTemplates() {
    if (!window.eel || typeof window.eel.list_templates !== "function") {
        return;
    }

    templateSelect.innerHTML = "<option value=\"\">Шаблон</option>";
    if (templateManagerSelect) {
        templateManagerSelect.innerHTML = "<option value=\"\">Выберите шаблон</option>";
    }

    try {
        const templates = await window.eel.list_templates()();
        for (const template of templates) {
            const option = document.createElement("option");
            option.value = template.name;
            option.textContent = template.name;
            templateSelect.appendChild(option);
            if (templateManagerSelect) {
                const managerOption = document.createElement("option");
                managerOption.value = template.name;
                managerOption.textContent = template.name;
                templateManagerSelect.appendChild(managerOption);
            }
        }
    } catch (error) {
        console.error(error);
    }
}

async function renderTemplateManagerPreview(name) {
    if (!templateManagerPreview) {
        return;
    }
    const templateName = String(name || "").trim();
    if (!templateName) {
        templateManagerPreview.textContent = "Выберите шаблон для просмотра состава.";
        return;
    }
    if (!window.eel || typeof window.eel.load_template !== "function") {
        templateManagerPreview.textContent = "Backend недоступен.";
        return;
    }
    try {
        const state = await window.eel.load_template(templateName)();
        const drugs = Array.isArray(state?.drugs) ? state.drugs.filter((drug) => drug.mnn || drug.russian_name) : [];
        if (!drugs.length) {
            templateManagerPreview.textContent = "Шаблон пуст.";
            return;
        }
        const lines = drugs.map((drug, index) => {
            const title = drug.russian_name || drug.mnn || "Препарат";
            const dose = drug.dosage ? ` ${drug.dosage}` : "";
            const scheme = drug.selectedScheme ? ` — ${drug.selectedScheme}` : "";
            return `${index + 1}. ${title}${dose}${scheme}`;
        });
        templateManagerPreview.textContent = lines.join("\n");
    } catch (error) {
        console.error(error);
        templateManagerPreview.textContent = "Не удалось прочитать шаблон.";
    }
}

async function loadTemplateIntoForm(templateName) {
    if (!templateName) {
        setStatus("Выберите шаблон для загрузки.");
        return false;
    }
    try {
        const state = await window.eel.load_template(templateName)();
        if (!state) {
            setStatus("Шаблон не найден.");
            return false;
        }
        restoreFormState(state, { keepCardNumber: true });
        setStatus(`Шаблон «${templateName}» загружен.`);
        return true;
    } catch (error) {
        console.error(error);
        setStatus("Не удалось загрузить шаблон.");
        return false;
    }
}

function applyParsedTreatmentDrugs(drugs) {
    clearDrugRows();
    for (const drug of drugs) {
        if (!drug?.mnn && !drug?.russian_name) {
            continue;
        }
        const catalogMatch = catalogDrugs.find((item) => item.mnn === drug.mnn) || {};
        addDrugRow(
            {
                ...catalogMatch,
                ...drug,
                form_options: drug.form_options?.length ? drug.form_options : catalogMatch.form_options,
                dosage_options: drug.dosage_options?.length ? drug.dosage_options : catalogMatch.dosage_options,
                form_dosage_map: (drug.form_dosage_map && Object.keys(drug.form_dosage_map).length)
                    ? drug.form_dosage_map
                    : catalogMatch.form_dosage_map,
                trade_names: drug.trade_names?.length ? drug.trade_names : catalogMatch.trade_names,
                scheme_options: drug.scheme_options?.length ? drug.scheme_options : catalogMatch.scheme_options,
                trade_details: Object.keys(drug.trade_details || {}).length
                    ? drug.trade_details
                    : catalogMatch.trade_details,
            },
            {
                mode: drug.mode || (drug.selectedTrade ? "trade" : "mnn"),
                selectedTrade: drug.selectedTrade || "",
                drug_form: drug.drug_form,
                dosage: drug.dosage,
                dispenseQty: drug.dispenseQty || drug.dispense_qty || undefined,
                selectedScheme: drug.selectedScheme || "",
                availability: "unknown",
            },
        );
    }

    Array.from(drugRowsContainer.querySelectorAll(".drug-row")).forEach((row) => {
        refreshRowAvailability(row);
    });
}

function normalizeTreatmentMatchText(value) {
    return String(value || "")
        .replace(/\u00a0/g, " ")
        .trim()
        .toLowerCase()
        .replace(/ё/g, "е")
        .replace(/["'`«»]/g, "")
        .replace(/\s+/g, " ")
        .trim();
}

function normalizeTreatmentDose(value) {
    const raw = String(value || "").trim().toLowerCase().replace(/ё/g, "е").replace(/,/g, ".");
    const match = raw.match(/(?<!\d)(\d+(?:\.\d+)?)\s*(мг|mg|мкг|mcg|г|g)\.?/);
    if (!match) {
        return raw;
    }
    let amount = match[1].replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "");
    const unitMap = { mg: "мг", mcg: "мкг", g: "г" };
    const unit = unitMap[match[2]] || match[2];
    return `${amount} ${unit}`;
}

function buildTreatmentNameIndex(catalog) {
    const entries = [];
    const seen = new Set();

    const add = (raw, drug, kind) => {
        const display = String(raw || "").trim();
        const key = normalizeTreatmentMatchText(display);
        if (key.length < 3) {
            return;
        }
        const marker = `${key}::${drug.mnn || ""}`;
        if (seen.has(marker)) {
            return;
        }
        seen.add(marker);
        entries.push({ key, drug, kind, display });
    };

    for (const drug of catalog) {
        add(drug.russian_name, drug, "russian");
        add(drug.mnn, drug, "mnn");
        add(drug.latin_name, drug, "mnn");
        for (const trade of drug.trade_names || []) {
            add(trade, drug, "trade");
        }
        for (const alias of drug.search_aliases || []) {
            add(alias, drug, "alias");
        }
        const latin = String(drug.latin_name || "").trim();
        if (latin.toLowerCase().endsWith("um") && latin.length > 4) {
            add(latin.slice(0, -2), drug, "mnn");
        }
    }

    entries.sort((a, b) => b.key.length - a.key.length || a.key.localeCompare(b.key));
    return entries;
}

function splitTreatmentLinesLocal(text) {
    const skip = /^(?:лечение|рекомендации|терапия|назначено|принимает|принимать|схема(?:\s+при[её]ма)?|препараты|rp\.?|recipe)\s*:?\s*$/i;
    const bullet = /^\s*(?:[-–—*•]+|\d+[.)]|\(\d+\))\s*/;
    const lines = [];
    for (const block of String(text || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n")) {
        const parts = block.split(/\s*;\s*/).map((part) => part.trim()).filter(Boolean);
        for (const chunk of parts.length ? parts : []) {
            const line = chunk.replace(bullet, "").replace(/^[\s.]+|[\s.]+$/g, "");
            if (!line || skip.test(normalizeTreatmentMatchText(line))) {
                continue;
            }
            lines.push(line);
        }
    }
    return lines;
}

function extractTreatmentFormLocal(line) {
    const patterns = [
        [/\bтаб\.?\b/i, "Tab."],
        [/\btab(?:lets?)?\.?\b/i, "Tab."],
        [/\bтаблет(?:к[аи]|ок|ке|ку)?\b/i, "Tab."],
        [/\bкапс\.?\b/i, "Caps."],
        [/\bcaps?(?:ules?)?\.?\b/i, "Caps."],
        [/\bкапсул(?:ы|а|е|у)?\b/i, "Caps."],
        [/\bsir(?:up)?\.?\b/i, "Sir."],
        [/\bсироп(?:а|е|у)?\b/i, "Sir."],
    ];
    for (const [pattern, form] of patterns) {
        const match = line.match(pattern);
        if (!match) {
            continue;
        }
        const cleaned = `${line.slice(0, match.index)} ${line.slice(match.index + match[0].length)}`
            .replace(/\s+/g, " ")
            .replace(/^[,.;\s]+|[,.;\s]+$/g, "");
        return { form, line: cleaned };
    }
    return { form: "", line };
}

function extractTreatmentPackQtyLocal(line) {
    const match = String(line || "").match(/\(\s*(?:№|N)\s*(\d+)\s*\)|(?:^|[\s,;])(?:№|N)\s*(\d+)(?=$|[\s);,]|\b)/i);
    if (!match) {
        return { qty: null, line };
    }
    const qty = Number.parseInt(match[1] || match[2], 10);
    const cleaned = `${line.slice(0, match.index)} ${line.slice(match.index + match[0].length)}`
        .replace(/\(\s*\)/g, " ")
        .replace(/\s+[()]\s*/g, " ")
        .replace(/\s+/g, " ")
        .replace(/^[,.;()\s]+|[,.;()\s]+$/g, "");
    return { qty: Number.isFinite(qty) ? qty : null, line: cleaned };
}

function cleanTreatmentSchemeLocal(value) {
    return String(value || "")
        .replace(/\([^)]*\)/g, " ")
        .replace(/[()]/g, " ")
        .replace(/\s+/g, " ")
        .replace(/^[,.;\s]+|[,.;\s]+$/g, "");
}

function stripTreatmentParentheticalsLocal(line) {
    return String(line || "")
        .replace(/\([^)]*\)/g, " ")
        .replace(/\s+/g, " ")
        .replace(/^[,.;\s]+|[,.;\s]+$/g, "");
}

function extractTreatmentDoseLocal(line) {
    const match = String(line).match(/(^|[^0-9])(\d+(?:[.,]\d+)?)\s*(мг|mg|мкг|mcg|г|g)\.?/i);
    if (!match) {
        return { dosage: "", line };
    }
    const dosage = normalizeTreatmentDose(match[0].replace(/^[^0-9]+/, ""));
    const from = match.index + (match[1] ? match[1].length : 0);
    const cleaned = `${line.slice(0, from)} ${line.slice(match.index + match[0].length)}`
        .replace(/\s+/g, " ")
        .replace(/^[,.;\s]+|[,.;\s]+$/g, "");
    return { dosage, line: cleaned };
}

function splitTreatmentHeadAndScheme(line) {
    const parts = String(line || "").split(/\s*[—–−]\s*|\s+[-:]\s+/);
    if (parts.length >= 2 && parts[1].trim()) {
        return {
            head: parts[0].replace(/^[,.;\s]+|[,.;\s]+$/g, ""),
            scheme: parts.slice(1).join(" — ").replace(/^[,.;\s]+|[,.;\s]+$/g, ""),
        };
    }
    return { head: String(line || "").trim(), scheme: "" };
}

function extractTreatmentSchemeLocal(line) {
    const text = String(line || "").replace(/^[,.;\s]+|[,.;\s]+$/g, "");
    if (!text) {
        return "";
    }
    const hint = text.match(/\b(?:по\s+\d|утром|вечером|ноч[ьюи]|днём|днем|раза?\s+в\s+день|р\/?д|через\s+день|по\s+потребности|на\s+ночь|перед\s+сном|после\s+еды|до\s+еды|1\/2|½|1[,.]5\s*т|табл|\d+\s*т\b)/i);
    if (hint) {
        return text.slice(hint.index).replace(/^[,.;\s]+|[,.;\s]+$/g, "");
    }
    return text;
}

function treatmentNamePattern(name) {
    const escaped = String(name || "").replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    // Без lookbehind — совместимее с встроенным браузером Eel.
    return new RegExp(`(^|[^0-9a-zA-Zа-яА-ЯёЁ_])${escaped}(?:[аеуыиояю]|ом|ами|ах)?(?=[^0-9a-zA-Zа-яА-ЯёЁ_]|$)`, "i");
}

function findTreatmentDrugInLine(line, index) {
    const normalized = normalizeTreatmentMatchText(line);
    if (!normalized) {
        return null;
    }
    const kindPriority = { russian: 0, mnn: 1, alias: 2, trade: 3 };
    let best = null;
    for (const entry of index) {
        const pattern = treatmentNamePattern(entry.key);
        const match = pattern.exec(normalized);
        if (!match) {
            continue;
        }
        const start = match.index + (match[1] ? match[1].length : 0);
        const rank = [start, kindPriority[entry.kind] ?? 9, -entry.key.length];
        if (!best || rank[0] < best.rank[0] || (rank[0] === best.rank[0] && (rank[1] < best.rank[1] || (rank[1] === best.rank[1] && rank[2] < best.rank[2])))) {
            best = { entry, rank, pattern, start, match };
        }
    }
    if (!best) {
        return null;
    }
    const sourcePattern = treatmentNamePattern(best.entry.display || best.entry.key);
    const sourceMatch = sourcePattern.exec(line) || sourcePattern.exec(normalized);
    let remainder = line;
    if (sourceMatch) {
        const prefixLen = sourceMatch[1] ? sourceMatch[1].length : 0;
        const from = sourceMatch.index + prefixLen;
        remainder = `${line.slice(0, from)} ${line.slice(sourceMatch.index + sourceMatch[0].length)}`;
    } else {
        remainder = normalized.replace(best.pattern, "$1 ");
    }
    remainder = stripTreatmentParentheticalsLocal(remainder);
    return { entry: best.entry, remainder };
}

function pickTreatmentForm(drug, requested) {
    const options = (drug.form_options || []).map((item) => String(item).trim()).filter(Boolean);
    if (!options.length) {
        return requested || drug.drug_form || "";
    }
    if (requested) {
        const found = options.find((option) => option.toLowerCase().replace(/\.$/, "") === requested.toLowerCase().replace(/\.$/, ""));
        if (found) {
            return found;
        }
    }
    return drug.drug_form || options[0];
}

function pickTreatmentDosage(drug, requested, form) {
    const mapped = drug.form_dosage_map?.[form];
    const options = (mapped || drug.dosage_options || []).map((item) => String(item).trim()).filter(Boolean);
    if (!options.length) {
        return requested || drug.dosage || "";
    }
    if (requested) {
        const want = normalizeTreatmentDose(requested);
        const exact = options.find((option) => normalizeTreatmentDose(option) === want);
        if (exact) {
            return exact;
        }
        const wantNum = want.match(/^[\d.]+/);
        if (wantNum) {
            const partial = options.find((option) => normalizeTreatmentDose(option).startsWith(wantNum[0]));
            if (partial) {
                return partial;
            }
        }
        return requested;
    }
    return drug.dosage || options[0];
}

function parseTreatmentTextLocal(text, catalog = catalogDrugs) {
    const lines = splitTreatmentLinesLocal(text);
    if (!lines.length) {
        return { ok: false, drugs: [], unmatched: [], message: "Вставьте текст лечения из дневника." };
    }
    const index = buildTreatmentNameIndex(catalog);
    const drugs = [];
    const unmatched = [];
    const seen = new Set();

    for (const line of lines) {
        const { head, scheme: schemeFromSplit } = splitTreatmentHeadAndScheme(line);
        let working = head;
        let packQty = null;
        const packExtract = extractTreatmentPackQtyLocal(working);
        packQty = packExtract.qty;
        working = packExtract.line;
        const formExtract = extractTreatmentFormLocal(working);
        working = formExtract.line;
        const doseExtract = extractTreatmentDoseLocal(working);
        working = doseExtract.line;
        const found = findTreatmentDrugInLine(stripTreatmentParentheticalsLocal(working) || working, index)
            || findTreatmentDrugInLine(working, index);
        if (!found) {
            unmatched.push(line);
            continue;
        }
        let remainder = found.remainder;
        const form2 = extractTreatmentFormLocal(remainder);
        remainder = form2.line;
        const dose2 = extractTreatmentDoseLocal(remainder);
        remainder = dose2.line;
        const pack2 = extractTreatmentPackQtyLocal(remainder);
        remainder = pack2.line;
        packQty = packQty || pack2.qty;
        let scheme = schemeFromSplit || "";
        if (scheme) {
            const pack3 = extractTreatmentPackQtyLocal(scheme);
            packQty = packQty || pack3.qty;
            scheme = stripTreatmentParentheticalsLocal(pack3.line) || pack3.line;
        } else {
            const pack3 = extractTreatmentPackQtyLocal(remainder);
            packQty = packQty || pack3.qty;
            scheme = extractTreatmentSchemeLocal(stripTreatmentParentheticalsLocal(pack3.line) || pack3.line);
        }
        const form = pickTreatmentForm(found.entry.drug, formExtract.form || form2.form);
        const dosage = pickTreatmentDosage(found.entry.drug, doseExtract.dosage || dose2.dosage, form);
        const drug = found.entry.drug;
        const selectedTrade = found.entry.kind === "trade" ? found.entry.display : "";
        const payload = {
            ...drug,
            drug_form: form,
            dosage,
            packaging: packQty ? `N${packQty}` : (drug.packaging || ""),
            dispenseQty: packQty || undefined,
            selectedTrade,
            selectedScheme: cleanTreatmentSchemeLocal(scheme),
            mode: selectedTrade ? "trade" : "mnn",
            matched_as: found.entry.display,
            match_kind: found.entry.kind,
        };
        if (payload.mnn && seen.has(payload.mnn)) {
            const filtered = drugs.filter((item) => item.mnn !== payload.mnn);
            drugs.length = 0;
            drugs.push(...filtered);
        }
        if (payload.mnn) {
            seen.add(payload.mnn);
        }
        drugs.push(payload);
    }

    if (!drugs.length) {
        return { ok: false, drugs: [], unmatched, message: "Не удалось определить препараты в тексте." };
    }
    let message = `Определено препаратов: ${drugs.length}`;
    if (unmatched.length) {
        message += `, не распознано строк: ${unmatched.length}`;
    }
    return { ok: true, drugs, unmatched, message };
}

async function resolveTreatmentParse(text) {
    if (window.eel && typeof window.eel.parse_treatment === "function") {
        try {
            return await window.eel.parse_treatment(text)();
        } catch (error) {
            console.warn("eel.parse_treatment failed, using local parser", error);
        }
    }
    return parseTreatmentTextLocal(text, catalogDrugs);
}

async function parseAndApplyTreatment() {
    const text = String(treatmentParseInput?.value || "").trim();
    if (!text) {
        setStatus("Вставьте текст лечения из дневника.");
        if (treatmentParseHint) {
            treatmentParseHint.textContent = "Нужен текст лечения";
        }
        treatmentParseInput?.focus();
        return;
    }
    if (!catalogDrugs.length && !(window.eel && typeof window.eel.parse_treatment === "function")) {
        setStatus("Каталог препаратов ещё не загружен.");
        return;
    }

    if (parseTreatmentBtn) {
        parseTreatmentBtn.disabled = true;
    }
    setStatus("Определяю лечение…");
    try {
        const result = await resolveTreatmentParse(text);
        const drugs = Array.isArray(result?.drugs) ? result.drugs : [];
        if (!result?.ok || !drugs.length) {
            const unmatched = (result?.unmatched || []).slice(0, 3).join("; ");
            const detail = unmatched ? ` Не распознано: ${unmatched}` : "";
            setStatus((result?.message || "Не удалось определить лечение.") + detail);
            if (treatmentParseHint) {
                treatmentParseHint.textContent = result?.message || "Ничего не найдено";
            }
            return;
        }

        applyParsedTreatmentDrugs(drugs);
        const unmatchedCount = (result.unmatched || []).length;
        clearTreatmentParseInput(
            unmatchedCount
                ? `Добавлено: ${drugs.length}, не распознано: ${unmatchedCount}`
                : `Добавлено в рецепт: ${drugs.length}`,
        );
        scheduleAutosave();
        setStatus(result.message || `Добавлено препаратов: ${drugs.length}`);
    } catch (error) {
        console.error(error);
        setStatus("Не удалось разобрать лечение.");
        if (treatmentParseHint) {
            treatmentParseHint.textContent = "Ошибка разбора";
        }
    } finally {
        if (parseTreatmentBtn) {
            parseTreatmentBtn.disabled = false;
        }
    }
}

function bindTreatmentParseControls() {
    if (parseTreatmentBtn && !parseTreatmentBtn.dataset.bound) {
        parseTreatmentBtn.addEventListener("click", () => {
            parseAndApplyTreatment();
        });
        parseTreatmentBtn.dataset.bound = "true";
    }
    if (treatmentParseInput && !treatmentParseInput.dataset.bound) {
        treatmentParseInput.addEventListener("keydown", (event) => {
            if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
                event.preventDefault();
                parseAndApplyTreatment();
            }
        });
        treatmentParseInput.dataset.bound = "true";
    }
}

async function bindTemplateManagerControls() {
    if (!templateManagerSelect || templateManagerSelect.dataset.bound) {
        return;
    }
    templateManagerSelect.addEventListener("change", async () => {
        const selected = templateManagerSelect.value;
        if (templateManagerName) {
            templateManagerName.value = selected;
        }
        await renderTemplateManagerPreview(selected);
    });
    templateManagerSelect.dataset.bound = "true";

    if (templateManagerSaveBtn && !templateManagerSaveBtn.dataset.bound) {
        templateManagerSaveBtn.addEventListener("click", async () => {
            const name = String(templateManagerName?.value || templateManagerSelect.value || "").trim();
            if (!name) {
                setStatus("Введите имя шаблона.");
                return;
            }
            try {
                await window.eel.save_template(name, getFormState())();
                await refreshTemplates();
                templateSelect.value = name;
                templateManagerSelect.value = name;
                if (templateManagerName) {
                    templateManagerName.value = name;
                }
                await renderTemplateManagerPreview(name);
                setStatus(`Шаблон «${name}» сохранён.`);
            } catch (error) {
                console.error(error);
                setStatus("Не удалось сохранить шаблон.");
            }
        });
        templateManagerSaveBtn.dataset.bound = "true";
    }

    if (templateManagerLoadBtn && !templateManagerLoadBtn.dataset.bound) {
        templateManagerLoadBtn.addEventListener("click", async () => {
            const name = String(templateManagerSelect.value || templateManagerName?.value || "").trim();
            if (await loadTemplateIntoForm(name)) {
                templateSelect.value = name;
            }
        });
        templateManagerLoadBtn.dataset.bound = "true";
    }

    if (templateManagerDeleteBtn && !templateManagerDeleteBtn.dataset.bound) {
        templateManagerDeleteBtn.addEventListener("click", async () => {
            const name = String(templateManagerSelect.value || templateManagerName?.value || "").trim();
            if (!name) {
                setStatus("Выберите шаблон для удаления.");
                return;
            }
            if (!window.confirm(`Удалить шаблон «${name}»?`)) {
                return;
            }
            try {
                await window.eel.delete_template(name)();
                await refreshTemplates();
                if (templateManagerName) {
                    templateManagerName.value = "";
                }
                templateSelect.value = "";
                await renderTemplateManagerPreview("");
                setStatus(`Шаблон «${name}» удалён.`);
            } catch (error) {
                console.error(error);
                setStatus("Не удалось удалить шаблон.");
            }
        });
        templateManagerDeleteBtn.dataset.bound = "true";
    }
}

async function bindFormActions() {
    document.addEventListener("input", (event) => {
        if (event.target.matches("input, textarea, select")) {
            scheduleAutosave();
        }
    });
    document.addEventListener("change", (event) => {
        if (event.target.matches("input, textarea, select")) {
            scheduleAutosave();
        }
    });

    saveHistoryBtn.addEventListener("click", async () => {
        const state = getFormState();
        if (!state.card_number) {
            setStatus("Для сохранения истории нужен номер карты.");
            return;
        }

        try {
            await window.eel.save_history_entry(state)();
            setStatus("Текущая форма сохранена в историю.");
        } catch (error) {
            console.error(error);
            setStatus("Не удалось сохранить историю.");
        }
    });

    printBtn.addEventListener("click", async () => {
        applyPatientSmartInput({ normalizeField: true });
        const state = getFormState();

        try {
            const result = await window.eel.print_prescription(state)();
            if (!result || result.ok === false) {
                const errors = (result && result.errors) || ["Не удалось напечатать рецепт."];
                setStatus(errors.join(" "));
                return;
            }

            const printState = result.payload || state;
            openPrintPreview(printState, result.pdf_path, result.preview);
            if (printState.card_number) {
                await window.eel.save_history_entry(printState)();
            }

            const warningText = (result.warnings || []).length
                ? ` Предупреждения: ${result.warnings.join(" ")}`
                : "";
            setStatus(
                "Откроется окно предпросмотра — нажмите «Печать» или Ctrl+P. "
                + "Дуплекс: по длинной стороне, масштаб 100%. "
                + "Поля принтера: «нет» или «по умолчанию» (4 мм уже в макете). "
                + `PDF сохранён: ${result.pdf_path}.`
                + warningText
            );
        } catch (error) {
            console.error(error);
            setStatus("Не удалось сформировать PDF.");
        }
    });

    if (loadHistoryBtn) {
        loadHistoryBtn.addEventListener("click", async () => {
            await loadHistoryByCardNumber(cardNumberInput.value.trim(), { keepCurrentPatient: true });
        });
    }

    clearFormBtn.addEventListener("click", async () => {
        restoreFormState({
            card_number: "",
            patient_name: "",
            birth_date: "",
            doctor_name: recipeDoctorInput.value,
            drugs: [],
        });
        setStatus("Форма очищена.");
        await saveAutosaveState();
    });

    restoreAutosaveBtn.addEventListener("click", async () => {
        await restoreAutosaveState();
    });

    saveTemplateBtn.addEventListener("click", async () => {
        const templateName = window.prompt("Введите имя шаблона:");
        if (!templateName) {
            return;
        }

        try {
            await window.eel.save_template(templateName, getFormState())();
            await refreshTemplates();
            templateSelect.value = templateName;
            setStatus("Шаблон сохранен.");
        } catch (error) {
            console.error(error);
            setStatus("Не удалось сохранить шаблон.");
        }
    });

    loadTemplateBtn.addEventListener("click", async () => {
        const templateName = templateSelect.value;
        const loaded = await loadTemplateIntoForm(templateName);
        if (loaded && templateManagerSelect) {
            templateManagerSelect.value = templateName;
            if (templateManagerName) {
                templateManagerName.value = templateName;
            }
            await renderTemplateManagerPreview(templateName);
        }
    });

    if (showSchemeBtn) {
        showSchemeBtn.addEventListener("click", async () => {
            const drugs = getFormState().drugs.filter((drug) => drug.mnn);
            if (!drugs.length) {
                setStatus("Нет заполненных препаратов для копирования схемы.");
                return;
            }

            const lines = buildSchemeClipboardText(drugs);
            const missingScheme = drugs.filter((drug) => !String(drug.selectedScheme || "").trim()).length;

            try {
                const copied = await copyTextToClipboard(lines.join("\n"));
                if (!copied) {
                    setStatus("Не удалось скопировать схему в буфер обмена.");
                    return;
                }
                if (missingScheme) {
                    setStatus(`Схема скопирована (${lines.length} строк). У ${missingScheme} препарата схема не указана.`);
                } else {
                    setStatus(`Схема скопирована в буфер обмена (${lines.length}).`);
                }
            } catch (error) {
                console.error(error);
                setStatus("Не удалось скопировать схему в буфер обмена.");
            }
        });
    }
}

async function initPrototype() {
    initDoctorModal();
    bindDoctorControls();
    bindGlobalDrugSearch();
    bindUpdateControls();
    await loadPrintBlankCss();
    await loadCatalogFromBackend();
    await loadSettingsFromBackend();
    await refreshTemplates();
    await bindTemplateManagerControls();
    await renderTemplateManagerPreview("");
    renderDirectoryTable();
    await loadArchivedDrugsFromBackend();
    const startupUpdateStatus = await refreshUpdateStatus({ silent: true });
    await maybeAutoApplyStartupUpdate(startupUpdateStatus);

    const refreshAvailabilityBtn = document.getElementById("refreshAvailabilityBtn");
    if (refreshAvailabilityBtn) {
        refreshAvailabilityBtn.addEventListener("click", () => {
            refreshAvailabilityTable();
        });
    }

    await bindFormActions();
    bindTreatmentParseControls();
    initAgeField();
    await restoreAutosaveState();

    if (!drugRowsContainer.children.length) {
        setStatus("Введите препарат в поиск и нажмите Enter.");
    }

    globalDrugSearch.focus();
}

function renderUpdateStatus(status) {
    latestUpdateStatus = status || null;
    const version = status?.app_version || status?.version || "—";
    if (appVersionLabel) {
        appVersionLabel.textContent = version;
    }
    if (topbarVersion) {
        topbarVersion.textContent = `v${version}`;
        topbarVersion.classList.toggle("update-available", Boolean(status?.update_available));
    }
    if (appUpdateStatus) {
        appUpdateStatus.textContent = status?.message || "Нет данных об обновлениях";
        appUpdateStatus.classList.toggle("text-warning", Boolean(status?.update_available));
        appUpdateStatus.classList.toggle("text-danger", status && status.ok === false);
        appUpdateStatus.classList.toggle("text-muted", !status?.update_available && status?.ok !== false);
    }
    if (applyUpdateBtn) {
        applyUpdateBtn.disabled = !status?.update_available;
    }
    if (restartAppBtn) {
        restartAppBtn.disabled = false;
    }
}

async function refreshUpdateStatus(options = {}) {
    if (!window.eel || typeof window.eel.check_app_updates !== "function") {
        if (appVersionLabel) {
            appVersionLabel.textContent = "локально";
        }
        return null;
    }
    try {
        const status = await window.eel.check_app_updates()();
        renderUpdateStatus(status);
        if (!options.silent) {
            setStatus(status.message || "Проверка обновлений завершена.");
        } else if (status.update_available) {
            setStatus(`Доступно обновление приложения (${status.remote_version || status.remote_commit?.slice(0, 7) || "новая версия"}).`);
        }
        return status;
    } catch (error) {
        console.error(error);
        renderUpdateStatus({
            ok: false,
            app_version: appVersionLabel?.textContent || "—",
            update_available: false,
            message: "Не удалось проверить обновления.",
        });
        if (!options.silent) {
            setStatus("Не удалось проверить обновления.");
        }
        return null;
    }
}

function setUpdateControlsBusy(isBusy) {
    if (checkUpdateBtn) {
        checkUpdateBtn.disabled = isBusy;
    }
    if (applyUpdateBtn) {
        applyUpdateBtn.disabled = isBusy || !latestUpdateStatus?.update_available;
    }
    if (restartAppBtn) {
        restartAppBtn.disabled = isBusy;
    }
}

async function applyUpdateFlow(options = {}) {
    const interactive = options.interactive !== false;
    if (!latestUpdateStatus?.update_available) {
        if (interactive) {
            setStatus("Обновление не требуется.");
        }
        return null;
    }
    if (interactive) {
        const confirmed = window.confirm(
            "Обновить приложение с GitHub?\n\nЛокальные настройки, история и база пациентов сохранятся. После обновления нужно перезапустить программу.",
        );
        if (!confirmed) {
            return null;
        }
    }

    setUpdateControlsBusy(true);
    setStatus(options.startMessage || "Скачиваю и устанавливаю обновление…");
    try {
        const result = await window.eel.update_application()();
        renderUpdateStatus(result.status || {
            ok: result.ok,
            app_version: result.app_version,
            update_available: false,
            message: result.message,
        });
        if (result.updated && result.needs_restart) {
            const suffix = interactive
                ? " Нажмите «Перезагрузить приложение»."
                : " Обновление установлено автоматически, нажмите «Перезагрузить приложение».";
            setStatus(`${result.message || "Обновление установлено."}${suffix}`);
        } else {
            setStatus(result.message || "Готово.");
        }
        return result;
    } catch (error) {
        console.error(error);
        setStatus("Ошибка при обновлении приложения.");
        return null;
    } finally {
        setUpdateControlsBusy(false);
    }
}

async function maybeAutoApplyStartupUpdate(status) {
    if (autoUpdateStarted || !status?.update_available || !window.eel || typeof window.eel.update_application !== "function") {
        return null;
    }
    autoUpdateStarted = true;
    return applyUpdateFlow({
        interactive: false,
        startMessage: `Найдено обновление ${status.remote_version || ""}. Устанавливаю автоматически…`.trim(),
    });
}

function bindUpdateControls() {
    if (checkUpdateBtn && !checkUpdateBtn.dataset.bound) {
        checkUpdateBtn.addEventListener("click", async () => {
            setUpdateControlsBusy(true);
            setStatus("Проверяю обновления на GitHub…");
            await refreshUpdateStatus();
            setUpdateControlsBusy(false);
        });
        checkUpdateBtn.dataset.bound = "true";
    }

    if (applyUpdateBtn && !applyUpdateBtn.dataset.bound) {
        applyUpdateBtn.addEventListener("click", async () => {
            await applyUpdateFlow({ interactive: true });
        });
        applyUpdateBtn.dataset.bound = "true";
    }

    if (restartAppBtn && !restartAppBtn.dataset.bound) {
        restartAppBtn.addEventListener("click", async () => {
            if (!window.eel || typeof window.eel.restart_application !== "function") {
                window.location.reload();
                return;
            }
            restartAppBtn.disabled = true;
            setStatus("Перезапускаю приложение…");
            try {
                const result = await window.eel.restart_application()();
                if (!result?.ok) {
                    restartAppBtn.disabled = false;
                    setStatus(result?.message || "Не удалось перезапустить приложение.");
                }
            } catch (error) {
                console.error(error);
                restartAppBtn.disabled = false;
                setStatus("Не удалось перезапустить приложение.");
            }
        });
        restartAppBtn.dataset.bound = "true";
    }

    if (openRepoBtn && !openRepoBtn.dataset.bound) {
        openRepoBtn.addEventListener("click", async () => {
            try {
                if (window.eel && typeof window.eel.open_github_repo === "function") {
                    await window.eel.open_github_repo()();
                } else {
                    window.open("https://github.com/DocKavetski/recipie", "_blank");
                }
            } catch (error) {
                console.error(error);
                window.open("https://github.com/DocKavetski/recipie", "_blank");
            }
        });
        openRepoBtn.dataset.bound = "true";
    }
}

document.addEventListener("DOMContentLoaded", initPrototype);
