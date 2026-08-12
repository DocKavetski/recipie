/** Сопоставление торгового названия / МНН с фасовкой. */

function isNestedTradeDetails(entry) {
    return Boolean(entry && typeof entry === "object" && !("packaging" in entry) && !("dispense_qty" in entry));
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
    const normalizedDose = normalizeTreatmentDose(dose);
    if (isNestedTradeDetails(entry)) {
        if (dose && entry[dose]) {
            return entry[dose];
        }
        for (const [key, details] of Object.entries(entry)) {
            if (normalizeTreatmentDose(key) === normalizedDose) {
                return details;
            }
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
