import { ApiClient } from "./api.js";
import { EventSwitchboard, CharacterEventStream } from "./events.js";
import {
    appendEventLine,
    hideModal,
    lockForm,
    renderCharacterList,
    setCommandAvailability,
    setConnectionState,
    setHint,
    showModal,
} from "./ui.js";

const api = new ApiClient("");
const switchboard = new EventSwitchboard();

const dom = {
    authModal: document.getElementById("authModal"),
    characterModal: document.getElementById("characterModal"),
    loginForm: document.getElementById("loginForm"),
    registerForm: document.getElementById("registerForm"),
    authTabs: document.querySelectorAll("[data-auth-tab]"),
    authHint: document.getElementById("authHint"),
    characterHint: document.getElementById("characterHint"),
    characterList: document.getElementById("characterList"),
    characterForm: document.getElementById("characterForm"),
    commandForm: document.getElementById("commandForm"),
    logoutBtn: document.getElementById("logoutBtn"),
};

const state = {
    characters: [],
    activeCharacter: null,
    stream: null,
};

function init() {
    wireAuthTabs();
    wireAuthForms();
    wireCharacterSelection();
    wireCharacterCreation();
    wireCommandForm();
    wireLogout();
    registerSwitchboardHandlers();

    setCommandAvailability(false);

    if (api.hasTokens()) {
        handleAuthenticated();
    } else {
        showAuthModal("Sign in to continue.");
    }
}

document.addEventListener("DOMContentLoaded", init);

function wireAuthTabs() {
    dom.authTabs.forEach((tab) => {
        tab.addEventListener("click", () => {
            dom.authTabs.forEach((btn) => btn.classList.toggle("active", btn === tab));
            const mode = tab.dataset.authTab;
            dom.loginForm.classList.toggle("hidden", mode !== "login");
            dom.registerForm.classList.toggle("hidden", mode !== "register");
        });
    });
}

function wireAuthForms() {
    [dom.loginForm, dom.registerForm].forEach((form) => {
        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            const mode = form.dataset.authForm;
            const formData = new FormData(form);
            const email = String(formData.get("email")).trim();
            const password = String(formData.get("password"));
            if (!email || !password) {
                setHint(dom.authHint, "Email and password are required.", "error");
                return;
            }
            lockForm(form, true);
            setHint(dom.authHint, mode === "login" ? "Signing in..." : "Creating account...", "info");
            try {
                if (mode === "login") {
                    await api.login(email, password);
                } else {
                    await api.register(email, password);
                }
                form.reset();
                await handleAuthenticated();
            } catch (error) {
                setHint(dom.authHint, error.message, "error");
            } finally {
                lockForm(form, false);
            }
        });
    });
}

function wireCharacterSelection() {
    dom.characterList.addEventListener("click", (event) => {
        const button = event.target.closest("[data-character-id]");
        if (!button) {
            return;
        }
        const characterId = button.dataset.characterId;
        const character = state.characters.find((entry) => entry.id === characterId);
        if (character) {
            activateCharacter(character);
        }
    });
}

function wireCharacterCreation() {
    dom.characterForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        const name = String(data.get("name")).trim();
        if (!name) {
            setHint(dom.characterHint, "Name is required.", "error");
            return;
        }
        lockForm(dom.characterForm, true);
        setHint(dom.characterHint, "Forging character...", "info");
        try {
            const created = await api.createCharacter(name);
            state.characters = [...state.characters, created];
            renderCharacterList(dom.characterList, state.characters, created.id);
            setHint(dom.characterHint, `Created ${created.name}. Launching session...`, "success");
            dom.characterForm.reset();
            await activateCharacter(created);
        } catch (error) {
            setHint(dom.characterHint, error.message, "error");
        } finally {
            lockForm(dom.characterForm, false);
        }
    });
}

function wireCommandForm() {
    dom.commandForm.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!state.activeCharacter) {
            appendEventLine("Select a character before sending commands.", "error");
            return;
        }
        const input = event.currentTarget.command;
        const command = input.value.trim();
        if (!command) {
            return;
        }
        appendEventLine(`> ${command}`, "command");
        input.value = "";
        try {
            await api.sendCommand(state.activeCharacter.id, command);
        } catch (error) {
            appendEventLine(error.message, "error");
        }
    });
}

function wireLogout() {
    dom.logoutBtn.addEventListener("click", () => {
        api.clearTokens();
        state.activeCharacter = null;
        state.stream?.stop();
        state.stream = null;
        state.characters = [];
        renderCharacterList(dom.characterList, [], null);
        setCommandAvailability(false);
        setConnectionState("offline");
        dom.logoutBtn.hidden = true;
        appendEventLine("Signed out.", "system");
        showAuthModal("Session cleared. Please sign in again.");
    });
}

async function handleAuthenticated() {
    dom.logoutBtn.hidden = false;
    hideModal(dom.authModal);
    await loadCharacters();
    if (state.characters.length) {
        setHint(dom.characterHint, "Select a character to continue.", "info");
    }
    showModal(dom.characterModal);
}

function showAuthModal(message) {
    setHint(dom.authHint, message, "info");
    showModal(dom.authModal);
}

async function loadCharacters() {
    setHint(dom.characterHint, "Loading characters...", "info");
    try {
        state.characters = await api.getCharacters();
        renderCharacterList(dom.characterList, state.characters, state.activeCharacter?.id ?? null);
        if (!state.characters.length) {
            setHint(dom.characterHint, "Create your first character to begin.", "info");
        } else {
            setHint(dom.characterHint, "Choose a character or build a new one.", "info");
        }
    } catch (error) {
        setHint(dom.characterHint, error.message, "error");
        appendEventLine(error.message, "error");
    }
}

async function activateCharacter(character) {
    state.activeCharacter = character;
    renderCharacterList(dom.characterList, state.characters, character.id);
    hideModal(dom.characterModal);
    appendEventLine(`Now controlling ${character.name}.`, "system");
    setCommandAvailability(true);
    connectEventStream();
}

function connectEventStream() {
    state.stream?.stop();
    if (!state.activeCharacter) {
        return;
    }
    const url = `/characters/${state.activeCharacter.id}/events`;
    state.stream = new CharacterEventStream({
        url,
        tokenProvider: () => api.accessToken,
        dispatcher: switchboard,
        onStatus: handleStreamStatus,
    });
    state.stream.start();
}

function handleStreamStatus(status, error) {
    if (status === "open") {
        setConnectionState("online");
        return;
    }
    if (status === "connecting") {
        setConnectionState("connecting");
        return;
    }
    if (status === "error") {
        setConnectionState("connecting");
        if (error) {
            appendEventLine(`Stream error: ${error.message ?? error}`, "error");
        }
        return;
    }
    if (status === "closed") {
        setConnectionState(state.activeCharacter ? "connecting" : "offline");
        return;
    }
    if (status === "offline") {
        setConnectionState("offline");
    }
}

function registerSwitchboardHandlers() {
    const narrativeHandlers = [
        "Text",
        "Line",
        "SayMessage",
    ];
    narrativeHandlers.forEach((eventName) => {
        switchboard.on(eventName, ({ type, payload }) => {
            if (!payload) {
                return;
            }
            if (type === "SayMessage" && payload.entity_name && payload.message) {
                appendEventLine(`${payload.entity_name} says, "${payload.message}"`, "system");
                return;
            }
            if (payload.message) {
                appendEventLine(payload.message, "system");
            }
        });
    });

    switchboard.on("*", ({ type, payload }) => {
        if (narrativeHandlers.includes(type)) {
            return;
        }
        const rendered = formatPayload(type, payload);
        if (rendered) {
            appendEventLine(rendered, "system");
        }
    });
}

function formatPayload(type, payload) {
    if (!payload) {
        return `[${type}]`;
    }
    if (typeof payload === "string") {
        return `[${type}] ${payload}`;
    }
    if (payload.message) {
        return `[${type}] ${payload.message}`;
    }
    try {
        return `[${type}] ${JSON.stringify(payload)}`;
    } catch (error) {
        return `[${type}]`;
    }
}
