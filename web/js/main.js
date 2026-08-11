const fallbackCatalog = [];

const drugRowsContainer = document.getElementById("drugRows");
const rowTemplate = document.getElementById("drugRowTemplate");
const birthDateInput = document.getElementById("birthDate");
const ageValue = document.getElementById("ageValue");
const statusText = document.getElementById("statusText");
const directoryTableBody = document.getElementById("directoryTableBody");
const schemeEditorSearch = document.getElementById("schemeEditorSearch");
const schemeEditorTableBody = document.getElementById("schemeEditorTableBody");
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
const showSchemeBtn = document.getElementById("showSchemeBtn");
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
            const title = drug.russian_name || drug.mnn;
            const head = [drug.drug_form, title, drug.dosage].filter(Boolean).join(" ").trim();
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
    if (parsed.card_number) {
        cardNumberInput.value = parsed.card_number;
    }

    const parts = [];
    if (parsed.card_number || cardNumberInput.value.trim()) {
        parts.push(`карта ${parsed.card_number || cardNumberInput.value.trim()}`);
    }
    if (parsed.patient_name) {
        parts.push(parsed.patient_name);
    }
    if (parsed.birth_date) {
        parts.push(parsed.birth_date);
    }
    if (ageValue.value) {
        parts.push(`${ageValue.value} лет`);
    }

    if (patientParsedHint) {
        if (parts.length) {
            patientParsedHint.textContent = parts.join(" · ");
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
            parsed.card_number || cardNumberInput.value,
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

function schemeEditorMatches(drug, query) {
    const normalizedQuery = normalizeText(query);
    if (!normalizedQuery) {
        return true;
    }
    const candidates = [
        drug.mnn,
        drug.russian_name,
        drug.latin_name,
        ...(drug.trade_names || []),
        ...(drug.search_aliases || []),
    ];
    return candidates.some((candidate) => normalizeText(candidate).includes(normalizedQuery));
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

async function saveSchemeEditorRow(mnn, textarea, statusCell) {
    const schemes = normalizeSchemeLines(String(textarea.value || "").split("\n"));
    if (!schemes.length) {
        setStatus("Введите хотя бы одну схему лечения.");
        statusCell.textContent = "Пусто";
        return;
    }
    try {
        const result = await window.eel.save_drug_schemes(mnn, schemes)();
        updateCatalogDrugSchemes(mnn, result.scheme_options || schemes, true);
        textarea.value = (result.scheme_options || schemes).join("\n");
        statusCell.textContent = "Сохранено";
        setStatus(`Схемы для ${mnn} сохранены.`);
    } catch (error) {
        console.error(error);
        statusCell.textContent = "Ошибка";
        setStatus("Не удалось сохранить схемы лечения.");
    }
}

async function resetSchemeEditorRow(drug, textarea, statusCell) {
    try {
        await window.eel.reset_drug_schemes(drug.mnn)();
        const refreshed = await window.eel.search_catalog_drugs(drug.mnn)();
        const current = Array.isArray(refreshed) ? refreshed.find((item) => item.mnn === drug.mnn) : null;
        const fallbackSchemes = current?.scheme_options || drug.scheme_options || [];
        updateCatalogDrugSchemes(drug.mnn, fallbackSchemes, false);
        textarea.value = fallbackSchemes.join("\n");
        statusCell.textContent = "По умолчанию";
        setStatus(`Схемы для ${drug.mnn} сброшены к каталогу.`);
        renderSchemeEditorTable();
    } catch (error) {
        console.error(error);
        statusCell.textContent = "Ошибка";
        setStatus("Не удалось сбросить схемы лечения.");
    }
}

function renderSchemeEditorTable() {
    if (!schemeEditorTableBody) {
        return;
    }
    schemeEditorTableBody.innerHTML = "";
    const query = schemeEditorSearch?.value || "";
    const filtered = catalogDrugs.filter((drug) => schemeEditorMatches(drug, query));
    if (!filtered.length) {
        const row = document.createElement("tr");
        row.innerHTML = `<td colspan="5" class="text-muted">Ничего не найдено.</td>`;
        schemeEditorTableBody.appendChild(row);
        return;
    }

    for (const drug of filtered) {
        const row = document.createElement("tr");
        const schemes = normalizeSchemeLines(drug.scheme_options || []);
        row.innerHTML = `
            <td>
                <div class="fw-semibold">${escapeHtml(drug.russian_name)}</div>
                <div class="text-muted small">${escapeHtml(drug.mnn)}</div>
            </td>
            <td>${escapeHtml(drug.category)}</td>
            <td>
                <textarea class="form-control form-control-sm scheme-editor-textarea" rows="4" placeholder="Каждая схема с новой строки">${escapeHtml(schemes.join("\n"))}</textarea>
            </td>
            <td class="small scheme-editor-status">${drug.has_custom_scheme ? "Пользовательская" : "Каталог"}</td>
            <td class="text-end">
                <div class="d-flex gap-2 justify-content-end">
                    <button class="btn btn-sm btn-primary scheme-save-btn" type="button">Сохранить</button>
                    <button class="btn btn-sm btn-outline-secondary scheme-reset-btn" type="button">Сбросить</button>
                </div>
            </td>
        `;
        const textarea = row.querySelector(".scheme-editor-textarea");
        const statusCell = row.querySelector(".scheme-editor-status");
        row.querySelector(".scheme-save-btn").addEventListener("click", () => saveSchemeEditorRow(drug.mnn, textarea, statusCell));
        row.querySelector(".scheme-reset-btn").addEventListener("click", () => resetSchemeEditorRow(drug, textarea, statusCell));
        schemeEditorTableBody.appendChild(row);
    }
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
    const persistScheme = () => {
        const value = schemeInput.value.trim();
        if (value) {
            const list = row.querySelector(".drug-scheme-datalist");
            const exists = Array.from(list.options).some((option) => option.value === value);
            if (!exists) {
                const option = document.createElement("option");
                option.value = value;
                list.appendChild(option);
            }
            setStatus("Схема приёма сохранена.");
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
    const baseDispenseQty = options.dispenseQty || drug.dispense_qty || extractDefaultDispenseQty(drug.packaging);
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
    if (selectedDetails) {
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
        availability: "none",
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
    setAvailabilityBadge(row, options.availability || "none");

    drugRowsContainer.appendChild(row);
    refreshDrugsEmptyState();
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
                availability: availabilityFromLabel(drug.availability),
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

    try {
        const templates = await window.eel.list_templates()();
        for (const template of templates) {
            const option = document.createElement("option");
            option.value = template.name;
            option.textContent = template.name;
            templateSelect.appendChild(option);
        }
    } catch (error) {
        console.error(error);
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

    loadHistoryBtn.addEventListener("click", async () => {
        const cardNumber = cardNumberInput.value.trim();
        if (!cardNumber) {
            setStatus("Введите номер карты для загрузки истории.");
            return;
        }

        try {
            const state = await window.eel.load_last_history_entry(cardNumber)();
            if (!state) {
                setStatus("История по этому номеру карты не найдена.");
                return;
            }

            restoreFormState(state);
            setStatus("Последняя запись по номеру карты загружена.");
        } catch (error) {
            console.error(error);
            setStatus("Не удалось загрузить историю.");
        }
    });

    clearFormBtn.addEventListener("click", async () => {
        const currentCard = cardNumberInput.value;
        restoreFormState({ card_number: currentCard, patient_name: "", birth_date: "", doctor_name: recipeDoctorInput.value, drugs: [] });
        cardNumberInput.value = currentCard;
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
        if (!templateName) {
            setStatus("Выберите шаблон для загрузки.");
            return;
        }

        try {
            const state = await window.eel.load_template(templateName)();
            if (!state) {
                setStatus("Шаблон не найден.");
                return;
            }

            restoreFormState(state, { keepCardNumber: true });
            setStatus("Шаблон загружен.");
        } catch (error) {
            console.error(error);
            setStatus("Не удалось загрузить шаблон.");
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
    bindSchemeEditorControls();
    bindUpdateControls();
    await loadPrintBlankCss();
    await loadCatalogFromBackend();
    await loadSettingsFromBackend();
    await refreshTemplates();
    renderDirectoryTable();
    renderSchemeEditorTable();
    const startupUpdateStatus = await refreshUpdateStatus({ silent: true });
    await maybeAutoApplyStartupUpdate(startupUpdateStatus);

    const refreshAvailabilityBtn = document.getElementById("refreshAvailabilityBtn");
    if (refreshAvailabilityBtn) {
        refreshAvailabilityBtn.addEventListener("click", () => {
            refreshAvailabilityTable();
        });
    }

    await bindFormActions();
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

function bindSchemeEditorControls() {
    if (!schemeEditorSearch || schemeEditorSearch.dataset.bound) {
        return;
    }
    schemeEditorSearch.addEventListener("input", () => renderSchemeEditorTable());
    schemeEditorSearch.dataset.bound = "true";
}

document.addEventListener("DOMContentLoaded", initPrototype);
