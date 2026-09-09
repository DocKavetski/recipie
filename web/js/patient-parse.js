/** Разбор ФИО / даты рождения / карты из единого поля пациента (чистые функции). */

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
    // Без lookbehind — совместимее со встроенным Chromium в Eel.
    const patterns = [
        /(^|[^\d])№?\s*(\d{3,}\/\d{2})(?!\d)/i,
        /(^|[^\d])№?\s*(\d{5,})(?!\d)/i,
    ];

    for (const pattern of patterns) {
        const match = text.match(pattern);
        if (!match) {
            continue;
        }
        const card = normalizeCardNumber(match[2]);
        const prefixLen = match[1] ? match[1].length : 0;
        const from = match.index + prefixLen;
        const remainder = `${text.slice(0, from)} ${text.slice(match.index + match[0].length)}`;
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
        // Только строчная «г.р.» — иначе инициал отчества Р (И.Р. / Г.Р.) пропадает при печати.
        .replace(/(^|[^A-Za-zА-Яа-яЁё])г\.\s*р\.?(?![A-Za-zА-Яа-яЁё])/g, "$1 ")
        .replace(/(^|[^A-Za-zА-Яа-яЁё])(?:года?)(?![A-Za-zА-Яа-яЁё])/gi, "$1 ")
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
