/** Редактор шаблонов: таблица препаратов и действия. */

const templateDrugRowsContainer = document.getElementById("templateDrugRows");
const templateManagerNewBtn = document.getElementById("templateManagerNewBtn");
const templateManagerImportBtn = document.getElementById("templateManagerImportBtn");
const templateManagerDuplicateBtn = document.getElementById("templateManagerDuplicateBtn");
const templateManagerMeta = document.getElementById("templateManagerMeta");
const templateDrugSearch = document.getElementById("templateDrugSearch");
const templateDrugSearchDropdown = document.getElementById("templateDrugSearchDropdown");
const templateAddManualBtn = document.getElementById("templateAddManualBtn");

let templateSearchMatches = [];
let templateSearchActiveIndex = 0;
let templateCreatedAtMap = {};

function getDrugsFromContainer(container) {
    return Array.from(container.querySelectorAll(".drug-row")).map(getRowState);
}

function stripDrugForTemplate(drug) {
    const copy = { ...drug };
    delete copy.availability;
    return copy;
}

function getTemplatePayload(drugs) {
    return {
        drugs: (Array.isArray(drugs) ? drugs : [])
            .map(stripDrugForTemplate)
            .filter((drug) => drug.mnn || drug.russian_name),
    };
}

function getTemplatePayloadFromForm() {
    return getTemplatePayload(getDrugsFromContainer(drugRowsContainer));
}

function getTemplateEditorPayload() {
    return getTemplatePayload(getDrugsFromContainer(templateDrugRowsContainer));
}

function formatTemplateCreatedAt(value) {
    const raw = String(value || "").trim();
    if (!raw) {
        return "";
    }
    const parsed = new Date(raw.includes("T") ? raw : `${raw.replace(" ", "T")}Z`);
    if (Number.isNaN(parsed.getTime())) {
        return raw;
    }
    return parsed.toLocaleString("ru-RU", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function updateTemplateManagerMeta(name = "", createdAt = "") {
    if (!templateManagerMeta) {
        return;
    }
    const templateName = String(name || "").trim();
    if (!templateName) {
        templateManagerMeta.textContent = "Новый шаблон";
        return;
    }
    const formatted = formatTemplateCreatedAt(createdAt);
    templateManagerMeta.textContent = formatted
        ? `«${templateName}» · сохранён ${formatted}`
        : `«${templateName}»`;
}

function mergeDrugWithCatalog(drug) {
    const catalogMatch = catalogDrugs.find((item) => item.mnn === drug.mnn) || {};
    return {
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
    };
}

function drugRowOptionsFromState(drug) {
    const rawQty = drug.dispenseQty ?? drug.dispense_qty;
    const hasQty = rawQty !== undefined && rawQty !== null && String(rawQty).trim() !== "";
    const options = {
        mode: drug.mode || (drug.selectedTrade ? "trade" : "mnn"),
        selectedTrade: drug.selectedTrade || "",
        drug_form: drug.drug_form,
        dosage: drug.dosage,
        selectedScheme: drug.selectedScheme || "",
        availability: "unknown",
    };
    // Не подставляем 1: иначе после разбора схемы без № ломается фасовка и шаг 10/14.
    if (hasQty) {
        options.dispenseQty = rawQty;
    }
    return options;
}

function restoreDrugsToContainer(drugs, container, options = {}) {
    clearDrugRows(container);
    for (const drug of Array.isArray(drugs) ? drugs : []) {
        if (!drug?.mnn && !drug?.russian_name) {
            continue;
        }
        addDrugRow(mergeDrugWithCatalog(drug), drugRowOptionsFromState(drug), container);
    }
    if (options.refreshAvailability && container === drugRowsContainer) {
        Array.from(container.querySelectorAll(".drug-row")).forEach((row) => {
            refreshRowAvailability(row);
        });
    }
}

async function loadTemplateIntoEditor(templateName) {
    const name = String(templateName || "").trim();
    if (!name) {
        clearDrugRows(templateDrugRowsContainer);
        updateTemplateManagerMeta("");
        return false;
    }
    if (!window.eel || typeof window.eel.load_template !== "function") {
        setStatus("Backend недоступен.");
        return false;
    }
    try {
        const state = await window.eel.load_template(name)();
        if (!state) {
            setStatus("Шаблон не найден.");
            return false;
        }
        restoreDrugsToContainer(state.drugs, templateDrugRowsContainer);
        if (templateManagerName) {
            templateManagerName.value = name;
        }
        updateTemplateManagerMeta(name, templateCreatedAtMap[name] || "");
        return true;
    } catch (error) {
        console.error(error);
        setStatus("Не удалось загрузить шаблон в редактор.");
        return false;
    }
}

function clearTemplateEditor() {
    clearDrugRows(templateDrugRowsContainer);
    if (templateManagerSelect) {
        templateManagerSelect.value = "";
    }
    if (templateManagerName) {
        templateManagerName.value = "";
    }
    updateTemplateManagerMeta("");
}

async function saveTemplateByName(name, payload) {
    const templateName = String(name || "").trim();
    if (!templateName) {
        setStatus("Введите имя шаблона.");
        return false;
    }
    const drugs = Array.isArray(payload?.drugs) ? payload.drugs : [];
    if (!drugs.length) {
        setStatus("Шаблон пуст — добавьте хотя бы один препарат.");
        return false;
    }
    try {
        await window.eel.save_template(templateName, payload)();
        await refreshTemplates();
        templateSelect.value = templateName;
        if (templateManagerSelect) {
            templateManagerSelect.value = templateName;
        }
        if (templateManagerName) {
            templateManagerName.value = templateName;
        }
        updateTemplateManagerMeta(templateName, templateCreatedAtMap[templateName] || new Date().toISOString());
        return true;
    } catch (error) {
        console.error(error);
        setStatus("Не удалось сохранить шаблон.");
        return false;
    }
}

function makeDuplicateTemplateName(baseName) {
    const trimmed = String(baseName || "").trim() || "Шаблон";
    const existing = new Set(Object.keys(templateCreatedAtMap));
    let candidate = `${trimmed} (копия)`;
    let index = 2;
    while (existing.has(candidate)) {
        candidate = `${trimmed} (копия ${index})`;
        index += 1;
    }
    return candidate;
}

function applyTemplateEditorToRecipe() {
    const drugs = getDrugsFromContainer(templateDrugRowsContainer);
    if (!drugs.length) {
        setStatus("В шаблоне нет препаратов.");
        return false;
    }
    restoreFormState({ drugs }, { keepCardNumber: true, keepPatient: true, keepDoctor: true, drugsOnly: true });
    setStatus(`В рецепт загружено ${drugs.length} препарат(ов) из редактора шаблона.`);
    return true;
}

function hideTemplateSearchDropdown() {
    if (!templateDrugSearchDropdown) {
        return;
    }
    templateDrugSearchDropdown.hidden = true;
    templateDrugSearchDropdown.innerHTML = "";
    templateSearchMatches = [];
    templateSearchActiveIndex = 0;
}

function renderTemplateSearchDropdown(matches, activeIndex = 0) {
    if (!templateDrugSearchDropdown) {
        return;
    }
    templateSearchMatches = matches;
    templateSearchActiveIndex = matches.length ? Math.max(0, Math.min(activeIndex, matches.length - 1)) : 0;
    templateDrugSearchDropdown.innerHTML = "";
    if (!matches.length) {
        hideTemplateSearchDropdown();
        return;
    }
    matches.forEach((drug, index) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `drug-search-item${index === templateSearchActiveIndex ? " is-active" : ""}`;
        button.innerHTML = `
            <div class="drug-search-item-title">${escapeHtml(drug.russian_name)} · ${escapeHtml(drug.mnn)}</div>
            <div class="drug-search-item-meta">${escapeHtml((drug.form_options || [drug.drug_form]).join("/"))}</div>
        `;
        button.addEventListener("mousedown", (event) => {
            event.preventDefault();
            addDrugFromTemplateSearch(drug);
        });
        templateDrugSearchDropdown.appendChild(button);
    });
    templateDrugSearchDropdown.hidden = false;
}

function addDrugFromTemplateSearch(drug) {
    if (!drug || !templateDrugRowsContainer) {
        return;
    }
    addDrugRow(drug, {
        mode: "mnn",
        availability: "unknown",
        drug_form: drug.drug_form,
        dosage: drug.dosage,
    }, templateDrugRowsContainer);
    if (templateDrugSearch) {
        templateDrugSearch.value = "";
    }
    hideTemplateSearchDropdown();
    setStatus(`В шаблон добавлен: ${optionLabel(drug.russian_name) || optionLabel(drug.mnn) || "препарат"}.`);
    templateDrugSearch?.focus();
}

function bindTemplateDrugSearch() {
    if (!templateDrugSearch || templateDrugSearch.dataset.bound) {
        return;
    }
    templateDrugSearch.addEventListener("input", () => {
        renderTemplateSearchDropdown(findDrugsByQuery(templateDrugSearch.value), 0);
    });
    templateDrugSearch.addEventListener("keydown", (event) => {
        if (event.key === "ArrowDown" && templateSearchMatches.length) {
            event.preventDefault();
            renderTemplateSearchDropdown(templateSearchMatches, templateSearchActiveIndex + 1);
            return;
        }
        if (event.key === "ArrowUp" && templateSearchMatches.length) {
            event.preventDefault();
            renderTemplateSearchDropdown(templateSearchMatches, templateSearchActiveIndex - 1);
            return;
        }
        if (event.key === "Escape") {
            hideTemplateSearchDropdown();
            return;
        }
        if (event.key === "Enter") {
            event.preventDefault();
            const matches = templateSearchMatches.length
                ? templateSearchMatches
                : findDrugsByQuery(templateDrugSearch.value);
            if (!matches.length) {
                setStatus("Ничего не найдено.");
                return;
            }
            addDrugFromTemplateSearch(matches[Math.max(0, Math.min(templateSearchActiveIndex, matches.length - 1))]);
        }
    });
    templateDrugSearch.addEventListener("blur", () => {
        window.setTimeout(() => hideTemplateSearchDropdown(), 150);
    });
    templateDrugSearch.dataset.bound = "true";
}
