/** Шаг D.t.d., округление и привязка поля количества. */

function dispenseStepByPackaging(packaging) {
    const packQty = extractDefaultDispenseQty(packaging);
    if (!Number.isFinite(packQty) || packQty < 2) {
        return 1;
    }
    if (packQty % 14 === 0) {
        return 14;
    }
    if (packQty % 10 === 0) {
        return 10;
    }
    return 1;
}

function ceilToDispenseStep(value, packaging) {
    const numeric = Number.parseInt(String(value || "").trim(), 10);
    const step = dispenseStepByPackaging(packaging);
    if (!Number.isFinite(numeric) || numeric < 1) {
        return step > 1 ? step : 1;
    }
    if (step <= 1) {
        return numeric;
    }
    return Math.max(step, Math.ceil(numeric / step) * step);
}

function nearestMultiple(value, step) {
    const numeric = Number.parseInt(String(value || "").trim(), 10);
    if (!Number.isFinite(numeric) || numeric < 1) {
        return step;
    }
    if (step <= 1) {
        return numeric;
    }
    return Math.max(step, Math.round(numeric / step) * step);
}

function stepAlignedValue(value, step, direction = 0) {
    const numeric = Number.parseInt(String(value || "").trim(), 10);
    if (!Number.isFinite(numeric) || numeric < 1) {
        return step > 1 ? step : 1;
    }
    if (step <= 1) {
        return Math.max(1, numeric + direction);
    }
    if (direction > 0) {
        return Math.max(step, Math.ceil(numeric / step) * step);
    }
    if (direction < 0) {
        return Math.max(step, Math.floor(numeric / step) * step);
    }
    return nearestMultiple(numeric, step);
}

function roundDispenseForStepChange(value, previousStep, nextStep) {
    const numeric = Number.parseInt(String(value || "").trim(), 10);
    if (!Number.isFinite(numeric) || numeric < 1) {
        return nextStep > 1 ? nextStep : 1;
    }
    if (nextStep <= 1) {
        return Math.max(1, numeric);
    }
    if (previousStep > nextStep) {
        return Math.max(nextStep, Math.ceil(numeric / nextStep) * nextStep);
    }
    if (previousStep < nextStep) {
        return Math.max(nextStep, Math.floor(numeric / nextStep) * nextStep);
    }
    return nearestMultiple(numeric, nextStep);
}

function syncDispenseConstraints(row, options = {}) {
    const packagingInput = row.querySelector(".drug-packaging-input");
    const dispenseInput = row.querySelector(".drug-dispense-input");
    if (!packagingInput || !dispenseInput) {
        return;
    }
    const step = dispenseStepByPackaging(packagingInput.value);
    dispenseInput.dataset.dispenseStep = String(step);
    if (options.stepChange) {
        const previousStep = Number.parseInt(String(options.previousStep || ""), 10) || 1;
        dispenseInput.value = roundDispenseForStepChange(dispenseInput.value, previousStep, step);
    } else if (options.normalizeValue !== false) {
        const raw = String(dispenseInput.value || "").trim();
        if (!raw) {
            dispenseInput.value = String(step > 1 ? step : 1);
        } else {
            dispenseInput.value = nearestMultiple(dispenseInput.value, step);
        }
    }
}

function adjustDispenseByPack(row, direction) {
    const packagingInput = row.querySelector(".drug-packaging-input");
    const dispenseInput = row.querySelector(".drug-dispense-input");
    if (!packagingInput || !dispenseInput) {
        return;
    }
    const packaging = packagingInput.value;
    const packQty = extractDefaultDispenseQty(packaging);
    const step = dispenseStepByPackaging(packaging);
    const delta = (Number.isFinite(packQty) && packQty > 0 ? packQty : (step > 1 ? step : 1));
    const current = Number.parseInt(String(dispenseInput.value || "").trim(), 10);
    const base = Number.isFinite(current) && current > 0 ? current : 0;
    const minimum = delta;
    if (direction > 0) {
        dispenseInput.value = String(ceilToDispenseStep(base + delta, packaging));
    } else {
        const raw = base - delta;
        const floored = step > 1
            ? Math.max(step, Math.floor(raw / step) * step)
            : Math.max(1, raw);
        dispenseInput.value = String(Math.max(minimum, floored));
    }
    dispenseInput.dataset.prevDispenseValue = String(dispenseInput.value);
    syncDispenseConstraints(row, { normalizeValue: false });
    if (typeof scheduleAutosave === "function") {
        scheduleAutosave();
    }
}

function bindDispenseConstraints(row) {
    const packagingInput = row.querySelector(".drug-packaging-input");
    const dispenseInput = row.querySelector(".drug-dispense-input");
    if (!packagingInput || !dispenseInput || dispenseInput.dataset.dispenseBound) {
        return;
    }
    const minusBtn = row.querySelector(".dispense-minus-btn");
    const plusBtn = row.querySelector(".dispense-plus-btn");
    if (minusBtn && !minusBtn.dataset.dispenseBound) {
        minusBtn.addEventListener("click", () => adjustDispenseByPack(row, -1));
        minusBtn.dataset.dispenseBound = "true";
    }
    if (plusBtn && !plusBtn.dataset.dispenseBound) {
        plusBtn.addEventListener("click", () => adjustDispenseByPack(row, 1));
        plusBtn.dataset.dispenseBound = "true";
    }
    packagingInput.addEventListener("change", () => {
        const previousStep = Number.parseInt(dispenseInput.dataset.dispenseStep || "1", 10) || 1;
        syncDispenseConstraints(row, { stepChange: true, previousStep });
        scheduleAutosave();
    });
    dispenseInput.addEventListener("focus", () => {
        dispenseInput.dataset.prevDispenseValue = String(dispenseInput.value || "");
    });
    dispenseInput.addEventListener("change", () => {
        syncDispenseConstraints(row);
        dispenseInput.dataset.prevDispenseValue = String(dispenseInput.value || "");
        scheduleAutosave();
    });
    dispenseInput.addEventListener("blur", () => {
        syncDispenseConstraints(row);
        dispenseInput.dataset.prevDispenseValue = String(dispenseInput.value || "");
        scheduleAutosave();
    });
    dispenseInput.addEventListener("keydown", (event) => {
        const step = dispenseStepByPackaging(packagingInput.value);
        if (step <= 1) {
            return;
        }
        if (event.key === "ArrowUp") {
            event.preventDefault();
            const base = Number.parseInt(String(dispenseInput.value || "0"), 10) || 0;
            dispenseInput.value = stepAlignedValue(base + step, step, 1);
            dispenseInput.dataset.prevDispenseValue = String(dispenseInput.value);
            scheduleAutosave();
            return;
        }
        if (event.key === "ArrowDown") {
            event.preventDefault();
            const base = Number.parseInt(String(dispenseInput.value || String(step)), 10) || step;
            dispenseInput.value = stepAlignedValue(base - step, step, -1);
            dispenseInput.dataset.prevDispenseValue = String(dispenseInput.value);
            scheduleAutosave();
        }
    });
    dispenseInput.dataset.dispenseBound = "true";
    dispenseInput.dataset.prevDispenseValue = String(dispenseInput.value || "");
}
