/** Сопоставление торгового названия / МНН с фасовкой. */

function isNestedTradeDetails(entry) {
    return Boolean(entry && typeof entry === "object" && !("packaging" in entry) && !("dispense_qty" in entry));
}

function dosagesForTrade(tradeDetails, trade) {
    const tradeName = String(trade || "").trim();
    if (!tradeName || !tradeDetails || typeof tradeDetails !== "object") {
        return [];
    }
    const entry = tradeDetails[tradeName];
    if (!entry || typeof entry !== "object") {
        return [];
    }
    if (isNestedTradeDetails(entry)) {
        return Object.keys(entry).map((key) => String(key).trim()).filter(Boolean);
    }
    const dose = String(entry.dosage || "").trim();
    return dose ? [dose] : [];
}

function dosageFromTradeName(trade, available) {
    const text = String(trade || "");
    const numbers = [];
    const numberRe = /(\d+(?:[.,]\d+)?)/g;
    let match = numberRe.exec(text);
    while (match) {
        numbers.push(match[1].replace(",", "."));
        match = numberRe.exec(text);
    }
    const options = (available || []).map((item) => String(item).trim()).filter(Boolean);
    const byNorm = new Map(options.map((item) => [normalizeTreatmentDose(item), item]));
    for (const number of numbers.slice().reverse()) {
        for (const unit of ["мг", "мкг", "г", "МЕ"]) {
            const key = normalizeTreatmentDose(`${number} ${unit}`);
            if (byNorm.has(key)) {
                return byNorm.get(key);
            }
        }
        for (const [key, original] of byNorm.entries()) {
            if (key.startsWith(number)) {
                return original;
            }
        }
    }
    if (options.length === 1) {
        return options[0];
    }
    if (numbers.length) {
        return normalizeTreatmentDose(`${numbers[numbers.length - 1]} мг`);
    }
    return "";
}

function filterDosagesForTrade(allDosages, tradeDetails, trade) {
    const tradeDoses = dosagesForTrade(tradeDetails, trade);
    if (!tradeDoses.length) {
        return allDosages;
    }
    const tradeNorm = new Set(tradeDoses.map((item) => normalizeTreatmentDose(item)));
    const filtered = (allDosages || []).filter((item) => tradeNorm.has(normalizeTreatmentDose(item)));
    return filtered.length ? filtered : tradeDoses;
}

function resolveTradePackaging(tradeDetails, trade, dosage) {
    const tradeName = String(trade || "").trim();
    if (!tradeName || !tradeDetails || typeof tradeDetails !== "object") {
        return null;
    }
    const entry = tradeDetails[tradeName];
    if (!entry || typeof entry !== "object") {
        return null;
    }
    const dose = String(dosage || "").trim();
    const normalizedDose = dose ? normalizeTreatmentDose(dose) : "";
    if (isNestedTradeDetails(entry)) {
        if (dose && entry[dose]) {
            return entry[dose];
        }
        if (normalizedDose) {
            for (const [key, details] of Object.entries(entry)) {
                if (normalizeTreatmentDose(key) === normalizedDose) {
                    return details;
                }
            }
            return null;
        }
        const inferred = dosageFromTradeName(tradeName, Object.keys(entry));
        if (inferred) {
            const inferredNorm = normalizeTreatmentDose(inferred);
            if (entry[inferred]) {
                return entry[inferred];
            }
            for (const [key, details] of Object.entries(entry)) {
                if (normalizeTreatmentDose(key) === inferredNorm) {
                    return details;
                }
            }
        }
        const onlyKeys = Object.keys(entry);
        if (onlyKeys.length === 1) {
            return entry[onlyKeys[0]];
        }
        return null;
    }
    const entryDose = String(entry.dosage || "").trim();
    if (entryDose && dose && normalizeTreatmentDose(entryDose) !== normalizedDose) {
        return null;
    }
    return entry;
}

function resolveMnnPackaging(tradeDetails, dosage, fallbackPackaging = "") {
    const dose = String(dosage || "").trim();
    const normalizedDose = normalizeTreatmentDose(dose);
    let best = null;
    let bestQty = -1;

    for (const entry of Object.values(tradeDetails || {})) {
        let candidate = null;
        if (isNestedTradeDetails(entry)) {
            if (dose && entry[dose]) {
                candidate = entry[dose];
            } else {
                for (const [key, details] of Object.entries(entry)) {
                    if (normalizeTreatmentDose(key) === normalizedDose) {
                        candidate = details;
                        break;
                    }
                }
            }
        } else if (entry) {
            const entryDose = String(entry.dosage || "").trim();
            if (!entryDose || !dose || normalizeTreatmentDose(entryDose) === normalizedDose) {
                candidate = entry;
            }
        }
        if (!candidate) {
            continue;
        }
        const qty = Number(candidate.dispense_qty) || extractDefaultDispenseQty(candidate.packaging);
        if (qty > bestQty) {
            bestQty = qty;
            best = candidate;
        }
    }

    if (best) {
        return best;
    }
    const fallback = String(fallbackPackaging || "").trim();
    if (!fallback) {
        return null;
    }
    return {
        packaging: fallback,
        dispense_qty: extractDefaultDispenseQty(fallback),
    };
}

function applyPackagingMatchToRow(row, match, options = {}) {
    const packagingInput = row.querySelector(".drug-packaging-input");
    const dispenseInput = row.querySelector(".drug-dispense-input");
    if (!packagingInput || !dispenseInput || !match) {
        return false;
    }
    const previousStep = Number.parseInt(dispenseInput.dataset.dispenseStep || "1", 10) || 1;
    packagingInput.value = match.packaging || packagingInput.value;
    if (!options.keepDispenseQty) {
        dispenseInput.value = match.dispense_qty || extractDefaultDispenseQty(match.packaging);
    }
    syncDispenseConstraints(row, options.stepChange ? { stepChange: true, previousStep } : {});
    return true;
}

function applyTradePackagingToRow(row, options = {}) {
    const tradeSelect = row.querySelector(".drug-trade-select");
    const dosageSelect = row.querySelector(".drug-dosage-select");
    const packagingInput = row.querySelector(".drug-packaging-input");
    const dispenseInput = row.querySelector(".drug-dispense-input");
    if (!tradeSelect || !dosageSelect || !packagingInput || !dispenseInput) {
        return false;
    }
    const tradeDetails = JSON.parse(row.dataset.tradeDetails || "{}");
    const match = resolveTradePackaging(tradeDetails, tradeSelect.value, dosageSelect.value);
    if (!match) {
        return false;
    }
    return applyPackagingMatchToRow(row, match, options);
}

function applyMnnPackagingToRow(row, options = {}) {
    const dosageSelect = row.querySelector(".drug-dosage-select");
    const packagingInput = row.querySelector(".drug-packaging-input");
    if (!dosageSelect || !packagingInput) {
        return false;
    }
    const tradeDetails = JSON.parse(row.dataset.tradeDetails || "{}");
    const fallback = row.dataset.defaultPackaging || packagingInput.value || "";
    const match = resolveMnnPackaging(tradeDetails, dosageSelect.value, fallback);
    if (!match) {
        return false;
    }
    return applyPackagingMatchToRow(row, match, options);
}

function resolvePackagingForDrug(drug, mode, trade, dosage) {
    const tradeDetails = drug?.trade_details || {};
    if (mode === "trade" && trade) {
        return resolveTradePackaging(tradeDetails, trade, dosage);
    }
    return resolveMnnPackaging(tradeDetails, dosage, drug?.packaging || "");
}
