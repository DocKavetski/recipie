/** Группировка схем: поддержка / начало / отмена (общий модуль для рецепта и вкладки «Схемы»). */

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

function schemeLineGroup(line) {
    const text = String(line || "").trim().toLowerCase();
    if (text.startsWith("начало:")) {
        return "start";
    }
    if (text.startsWith("отмена:")) {
        return "stop";
    }
    return "support";
}

function splitSchemeGroups(lines) {
    const groups = { support: [], start: [], stop: [] };
    for (const line of normalizeSchemeLines(lines)) {
        const group = schemeLineGroup(line);
        if (group === "start") {
            const body = line.replace(/^начало:\s*/i, "").trim();
            if (body) {
                groups.start.push(body);
            }
            continue;
        }
        if (group === "stop") {
            const body = line.replace(/^отмена:\s*/i, "").trim();
            if (body) {
                groups.stop.push(body);
            }
            continue;
        }
        groups.support.push(line);
    }
    return groups;
}

function joinSchemeGroups(groups) {
    const support = normalizeSchemeLines(groups?.support || []);
    const start = normalizeSchemeLines(groups?.start || []).map((line) => {
        const body = String(line).replace(/^начало:\s*/i, "").trim();
        return body ? `начало: ${body}` : "";
    }).filter(Boolean);
    const stop = normalizeSchemeLines(groups?.stop || []).map((line) => {
        const body = String(line).replace(/^отмена:\s*/i, "").trim();
        return body ? `отмена: ${body}` : "";
    }).filter(Boolean);
    return normalizeSchemeLines([...support, ...start, ...stop]);
}

function sortSchemesByGroup(lines) {
    const groups = { support: [], start: [], stop: [] };
    for (const line of normalizeSchemeLines(lines)) {
        groups[schemeLineGroup(line)].push(line);
    }
    return [...groups.support, ...groups.start, ...groups.stop];
}
