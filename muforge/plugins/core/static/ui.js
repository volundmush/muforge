const overlay = document.getElementById("overlay");
const eventStream = document.getElementById("eventStream");
const commandInput = document.getElementById("commandInput");
const commandButton = document.querySelector("#commandForm button[type=submit]");
const connectionStatus = document.getElementById("connectionStatus");

export function showModal(modal) {
    modal.classList.remove("hidden");
    overlay.classList.remove("hidden");
    modal.setAttribute("aria-hidden", "false");
}

export function hideModal(modal) {
    modal.classList.add("hidden");
    overlay.classList.add("hidden");
    modal.setAttribute("aria-hidden", "true");
}

export function appendEventLine(text, variant = "system") {
    const line = document.createElement("div");
    line.className = `event-line ${variant}`;
    line.textContent = text;
    eventStream.appendChild(line);
    eventStream.scrollTop = eventStream.scrollHeight;
}

export function setConnectionState(state) {
    connectionStatus.classList.remove("online", "offline", "connecting");
    if (state === "online") {
        connectionStatus.classList.add("online");
        connectionStatus.textContent = "Online";
    } else if (state === "connecting") {
        connectionStatus.classList.add("connecting");
        connectionStatus.textContent = "Connecting";
    } else {
        connectionStatus.classList.add("offline");
        connectionStatus.textContent = "Offline";
    }
}

export function setCommandAvailability(enabled) {
    commandInput.disabled = !enabled;
    commandButton.disabled = !enabled;
    if (enabled) {
        commandInput.focus();
    } else {
        commandInput.value = "";
    }
}

export function renderCharacterList(target, characters, activeId) {
    target.innerHTML = "";
    if (!characters.length) {
        target.innerHTML = '<p class="form-hint">No characters yet. Create one below.</p>';
        return;
    }
    const template = document.getElementById("characterRowTemplate");
    characters.forEach((character) => {
        const node = template.content.firstElementChild.cloneNode(true);
        node.dataset.characterId = character.id;
        node.querySelector(".character-name").textContent = character.name;
        node.querySelector(".character-meta").textContent = character.created_at
            ? new Date(character.created_at).toLocaleString()
            : "Playable";
        if (character.id === activeId) {
            node.classList.add("active");
        }
        target.appendChild(node);
    });
}

export function setHint(element, message, variant = "info") {
    element.textContent = message ?? "";
    element.dataset.variant = variant;
}

export function lockForm(form, locked) {
    Array.from(form.elements).forEach((el) => {
        el.disabled = locked;
    });
}
