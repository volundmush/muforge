// static/js/events.js
const textDecoder = new TextDecoder();

export class EventSwitchboard {
    constructor() {
        this.handlers = new Map();
    }

    on(eventName, handler) {
        const key = eventName ?? "*";
        if (!this.handlers.has(key)) {
            this.handlers.set(key, new Set());
        }
        this.handlers.get(key).add(handler);
        return () => this.off(key, handler);
    }

    off(eventName, handler) {
        const handlers = this.handlers.get(eventName ?? "*");
        if (handlers) handlers.delete(handler);
    }

    clear() {
        this.handlers.clear();
    }

    dispatch(eventName, payload) {
        const exact = this.handlers.get(eventName);
        const wildcard = this.handlers.get("*");
        const packet = { type: eventName, payload };
        if (exact) exact.forEach((handler) => handler(packet));
        if (wildcard) wildcard.forEach((handler) => handler(packet));
    }
}

export class CharacterEventStream {
    constructor({ url, tokenProvider, dispatcher, onStatus, retryDelay = 2000 }) {
        this.url = url;
        this.tokenProvider = tokenProvider;
        this.dispatcher = dispatcher;
        this.onStatus = onStatus;
        this.retryDelay = retryDelay;
        this.controller = null;
        this.active = false;
        this.reconnectTimer = null;
    }

    start() {
        this.stop();
        this.active = true;
        this.#notify("connecting");
        this.#loop();
    }

    stop() {
        this.active = false;
        if (this.controller) {
            this.controller.abort();
            this.controller = null;
        }
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
    }

    async #loop() {
        if (!this.active) return;
        const token = this.tokenProvider?.();
        if (!token) {
            this.#notify("offline", new Error("Missing token"));
            return;
        }
        this.controller = new AbortController();
        try {
            const response = await fetch(this.url, {
                cache: "no-store",
                headers: {
                    Authorization: `Bearer ${token}`,
                    Accept: "text/event-stream",
                },
                signal: this.controller.signal,
            });
            if (!response.ok) throw new Error(`Stream failed with ${response.status}`);
            this.#notify("open");
            await this.#consume(response.body.getReader());
            this.#notify("closed");
        } catch (error) {
            if (this.controller?.signal.aborted || !this.active) return;
            this.#notify("error", error);
        }
        if (this.active) {
            this.reconnectTimer = setTimeout(() => this.#loop(), this.retryDelay);
            this.#notify("connecting");
        }
    }

    async #consume(reader) {
        let buffer = "";
        while (this.active) {
            const { value, done } = await reader.read();
            if (done) break;
            buffer += textDecoder.decode(value, { stream: true });
            buffer = this.#drainBuffer(buffer);
        }
    }

    #drainBuffer(buffer) {
        const segments = buffer.split("\n\n");
        buffer = segments.pop() ?? "";
        for (const segment of segments) {
            this.#parseEvent(segment);
        }
        return buffer;
    }

    #parseEvent(block) {
        const lines = block.split("\n");
        let eventName = "message";
        const data = [];
        for (const line of lines) {
            if (!line.trim() || line.startsWith(":")) continue;
            if (line.startsWith("event:")) {
                eventName = line.slice(6).trim() || eventName;
            } else if (line.startsWith("data:")) {
                data.push(line.slice(5).trimStart());
            }
        }
        if (!data.length) return;
        const payloadText = data.join("\n");
        let payload = payloadText;
        try {
            payload = JSON.parse(payloadText);
        } catch (error) { /* keep raw text */ }
        this.dispatcher?.dispatch(eventName, payload);
    }

    #notify(state, error) {
        if (typeof this.onStatus === "function") {
            this.onStatus(state, error);
        }
    }
}

