/** Общие утилиты для дозировок и фасовки. */

function extractDefaultDispenseQty(packaging) {
    const match = String(packaging || "").match(/\d+/);
    return match ? Number(match[0]) : 1;
}

function normalizeTreatmentDose(value) {
    const raw = String(value || "").trim().toLowerCase().replace(/ё/g, "е").replace(/,/g, ".");
    // Без lookbehind — совместимее со встроенным Chromium в Eel.
    const match = raw.match(/(^|[^\d])(\d+(?:\.\d+)?)\s*(мг|mg|мкг|mcg|г|g)\.?/);
    if (!match) {
        return raw;
    }
    let amount = match[2].replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "");
    const unitMap = { mg: "мг", mcg: "мкг", g: "г" };
    const unit = unitMap[match[3]] || match[3];
    return `${amount} ${unit}`;
}
