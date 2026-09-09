/** Вкладка «Схемы»: редактирование схем лечения по препаратам (группы). */

const schemeEditorSearch = document.getElementById("schemeEditorSearch");
const schemeEditorTableBody = document.getElementById("schemeEditorTableBody");

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

function schemeEditorGroupFields(row) {
    return {
        support: row.querySelector(".scheme-editor-support"),
        start: row.querySelector(".scheme-editor-start"),
        stop: row.querySelector(".scheme-editor-stop"),
    };
}

function fillSchemeEditorGroups(row, schemes) {
    const groups = splitSchemeGroups(schemes);
    const fields = schemeEditorGroupFields(row);
    if (fields.support) {
        fields.support.value = groups.support.join("\n");
    }
    if (fields.start) {
        fields.start.value = groups.start.join("\n");
    }
    if (fields.stop) {
        fields.stop.value = groups.stop.join("\n");
    }
}

function collectSchemeEditorGroups(row) {
    const fields = schemeEditorGroupFields(row);
    return joinSchemeGroups({
        support: String(fields.support?.value || "").split("\n"),
        start: String(fields.start?.value || "").split("\n"),
        stop: String(fields.stop?.value || "").split("\n"),
    });
}

async function saveSchemeEditorRow(mnn, row, statusCell) {
    const schemes = collectSchemeEditorGroups(row);
    if (!schemes.length) {
        setStatus("Введите хотя бы одну схему лечения.");
        statusCell.textContent = "Пусто";
        return;
    }
    if (!window.eel || typeof window.eel.save_drug_schemes !== "function") {
        setStatus("Backend недоступен для сохранения схем.");
        statusCell.textContent = "Нет backend";
        return;
    }
    try {
        const result = await window.eel.save_drug_schemes(mnn, schemes)();
        const saved = result.scheme_options || schemes;
        updateCatalogDrugSchemes(mnn, saved, true);
        fillSchemeEditorGroups(row, saved);
        statusCell.textContent = "Пользовательская";
        setStatus(`Схемы для ${mnn} сохранены.`);
    } catch (error) {
        console.error(error);
        statusCell.textContent = "Ошибка";
        setStatus("Не удалось сохранить схемы лечения.");
    }
}

async function resetSchemeEditorRow(drug, row, statusCell) {
    if (!window.eel || typeof window.eel.reset_drug_schemes !== "function") {
        setStatus("Backend недоступен для сброса схем.");
        statusCell.textContent = "Нет backend";
        return;
    }
    try {
        const result = await window.eel.reset_drug_schemes(drug.mnn)();
        let fallbackSchemes = result?.scheme_options;
        if (!Array.isArray(fallbackSchemes)) {
            const refreshed = typeof window.eel.search_catalog_drugs === "function"
                ? await window.eel.search_catalog_drugs(drug.mnn)()
                : [];
            const current = Array.isArray(refreshed)
                ? refreshed.find((item) => item.mnn === drug.mnn)
                : null;
            fallbackSchemes = current?.scheme_options || drug.scheme_options || [];
        }
        updateCatalogDrugSchemes(drug.mnn, fallbackSchemes, false);
        fillSchemeEditorGroups(row, fallbackSchemes);
        statusCell.textContent = "Каталог";
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
    const filtered = (catalogDrugs || []).filter((drug) => schemeEditorMatches(drug, query));
    if (!filtered.length) {
        const row = document.createElement("tr");
        row.innerHTML = `<td colspan="6" class="text-muted">Ничего не найдено.</td>`;
        schemeEditorTableBody.appendChild(row);
        return;
    }

    for (const drug of filtered) {
        const row = document.createElement("tr");
        const schemes = normalizeSchemeLines(drug.scheme_options || []);
        const maxDose = String(drug.max_daily_dose || "по инструкции").trim() || "по инструкции";
        const stopLabel = String(drug.discontinuation_label || "Желательна плавная отмена").trim();
        row.innerHTML = `
            <td>
                <div class="fw-semibold">${escapeHtml(drug.russian_name)}</div>
                <div class="text-muted small">${escapeHtml(drug.mnn)}</div>
            </td>
            <td>${escapeHtml(drug.category || "")}</td>
            <td>
                <div class="scheme-editor-groups">
                    <label class="scheme-editor-group">
                        <span class="scheme-editor-group-label">Поддержка</span>
                        <textarea class="form-control form-control-sm scheme-editor-textarea scheme-editor-support" rows="3" placeholder="по 1 таб. утром"></textarea>
                    </label>
                    <label class="scheme-editor-group">
                        <span class="scheme-editor-group-label">Начало</span>
                        <textarea class="form-control form-control-sm scheme-editor-textarea scheme-editor-start" rows="2" placeholder="по 1/2 таб. 7 дней, далее по 1 таб."></textarea>
                    </label>
                    <label class="scheme-editor-group">
                        <span class="scheme-editor-group-label">Отмена</span>
                        <textarea class="form-control form-control-sm scheme-editor-textarea scheme-editor-stop" rows="2" placeholder="по 1/2 таб. 7–14 дней, затем отменить"></textarea>
                    </label>
                </div>
            </td>
            <td class="small scheme-editor-ref">
                <div><span class="text-muted">Макс.:</span> ${escapeHtml(maxDose)}</div>
                <div class="mt-1">${escapeHtml(stopLabel)}</div>
            </td>
            <td class="small scheme-editor-status">${drug.has_custom_scheme ? "Пользовательская" : "Каталог"}</td>
            <td class="text-end">
                <div class="d-flex gap-2 justify-content-end flex-wrap">
                    <button class="btn btn-sm btn-primary scheme-save-btn" type="button">Сохранить</button>
                    <button class="btn btn-sm btn-outline-secondary scheme-reset-btn" type="button">Сбросить</button>
                </div>
            </td>
        `;
        fillSchemeEditorGroups(row, schemes);
        const statusCell = row.querySelector(".scheme-editor-status");
        row.querySelector(".scheme-save-btn").addEventListener("click", () => {
            saveSchemeEditorRow(drug.mnn, row, statusCell);
        });
        row.querySelector(".scheme-reset-btn").addEventListener("click", () => {
            resetSchemeEditorRow(drug, row, statusCell);
        });
        schemeEditorTableBody.appendChild(row);
    }
}

function bindSchemeEditorControls() {
    if (!schemeEditorSearch || schemeEditorSearch.dataset.bound) {
        return;
    }
    schemeEditorSearch.addEventListener("input", () => renderSchemeEditorTable());
    schemeEditorSearch.dataset.bound = "true";
}
