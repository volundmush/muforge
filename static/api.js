// static/js/api.js
const STORAGE_KEY = "muforge.tokens";

function safeJsonParse(value) {
    try {
        return JSON.parse(value);
    } catch (error) {
        return null;
    }
}

function decodeJwt(token) {
    if (!token) return null;
    try {
        const [, payload] = token.split(".");
        const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
        const padded = normalized.padEnd(normalized.length + (4 - (normalized.length % 4 || 4)), "=");
        return JSON.parse(atob(padded));
    } catch (error) {
        return null;
    }
}

export class ApiClient {
    constructor(basePath = "") {
        this.basePath = basePath;
        this.tokens = null;
        this.userId = null;
        this.loadTokens();
    }

    loadTokens() {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (!raw) return null;
        const parsed = safeJsonParse(raw);
        if (!parsed) {
            localStorage.removeItem(STORAGE_KEY);
            return null;
        }
        this.tokens = parsed;
        this.userId = decodeJwt(parsed.access_token)?.sub ?? null;
        return this.tokens;
    }

    hasTokens() {
        return Boolean(this.tokens?.access_token);
    }

    setTokens(tokens) {
        this.tokens = tokens;
        localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
        this.userId = decodeJwt(tokens.access_token)?.sub ?? null;
    }

    clearTokens() {
        this.tokens = null;
        this.userId = null;
        localStorage.removeItem(STORAGE_KEY);
    }

    get accessToken() {
        return this.tokens?.access_token ?? null;
    }

    get refreshToken() {
        return this.tokens?.refresh_token ?? null;
    }

    async login(email, password) {
        const body = new URLSearchParams();
        body.set("username", email);
        body.set("password", password);
        body.set("grant_type", "password");
        body.set("scope", "");

        const response = await fetch(`${this.basePath}/auth/login`, {
            method: "POST",
            headers: {
                Accept: "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            body,
        });
        const payload = await this.#parseResponse(response);
        this.setTokens(payload);
        return payload;
    }

    async register(email, password) {
        const payload = await this.request("/auth/register", {
            method: "POST",
            body: { email, password },
        }, { auth: false });
        this.setTokens(payload);
        return payload;
    }

    async refresh() {
        if (!this.refreshToken) return false;
        try {
            const payload = await this.request("/auth/refresh", {
                method: "POST",
                body: { refresh_token: this.refreshToken },
            }, { auth: false });
            this.setTokens(payload);
            return true;
        } catch (error) {
            this.clearTokens();
            return false;
        }
    }

    async request(path, init = {}, options = { auth: true }) {
        const config = {
            method: init.method ?? "GET",
            headers: {
                Accept: "application/json",
                ...(init.headers ?? {}),
            },
        };

        if (init.body !== undefined) {
            if (typeof init.body === "string" || init.body instanceof FormData || init.body instanceof URLSearchParams) {
                config.body = init.body;
            } else {
                config.body = JSON.stringify(init.body);
                if (!config.headers["Content-Type"]) {
                    config.headers["Content-Type"] = "application/json";
                }
            }
        }

        if (options.auth !== false && this.accessToken) {
            config.headers.Authorization = `Bearer ${this.accessToken}`;
        }

        let response = await fetch(`${this.basePath}${path}`, config);
        if (response.status === 401 && options.auth !== false && this.refreshToken) {
            const refreshed = await this.refresh();
            if (refreshed) {
                config.headers.Authorization = `Bearer ${this.accessToken}`;
                response = await fetch(`${this.basePath}${path}`, config);
            }
        }
        return this.#parseResponse(response);
    }

    async getCharacters() {
        if (!this.userId) throw new Error("Missing user id");
        return this.request(`/users/${this.userId}/characters`);
    }

    async createCharacter(name) {
        return this.request("/characters/", {
            method: "POST",
            body: { name },
        });
    }

    async sendCommand(characterId, command) {
        return this.request(`/characters/${characterId}/command`, {
            method: "POST",
            body: { command },
        });
    }

    async #parseResponse(response) {
        const contentType = response.headers.get("content-type") ?? "";
        const isJson = contentType.includes("application/json");
        if (!response.ok) {
            const message = isJson ? await response.json() : await response.text();
            const detail = typeof message === "object" ? message.detail ?? message.error ?? message.msg : message;
            throw new Error(detail || `Request failed with ${response.status}`);
        }
        if (response.status === 204 || !isJson) return null;
        return response.json();
    }
}

