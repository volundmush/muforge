// ============================================================================
// Terra MUD - Main JavaScript
// Three-layer architecture: Connection -> Event -> UI
// ============================================================================

// ----------------------------------------------------------------------------
// 1. CENTRAL APP STATE
// ----------------------------------------------------------------------------
const state = {
    connection: {
        protocol: 'http', // 'http' | 'webtransport' | 'websocket'
        status: 'connecting', // 'connecting' | 'connected' | 'error' | 'disconnected'
        sessionId: null,
    },
    player: {
        hp: null,
        maxHp: null,
        name: null,
        level: null,
        xp: null,
        xpToNext: null,
        credits: null,
        currentLocation: null,
    },
    combat: {
        inCombat: false,
        enemy: null, // { name, hp, maxHp, level, id }
        enemies: [], // Array of enemies
    },
    inventory: {
        items: [], // [ { id, name, quantity } ]
    },
    log: [],
    location: {
        name: null,
        desc: null,
        exits: {},
        grid: {},
    },
    loot: [],
};

// Action debouncing
let actionInProgress = false;

// API URL
const API_URL = window.location.origin + "/api";

// ----- Global client state (for new API integration) -----
let sessionId = null;
let gameState = null;

// Generic POST helper
async function apiPost(path, body = {}) {
    const res = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: Object.keys(body).length ? JSON.stringify(body) : null
    });
    if (!res.ok) {
        console.error("API error", res.status, res.statusText);
        throw new Error(`API error: ${res.status}`);
    }
    return res.json();
}

// ----------------------------------------------------------------------------
// 2. CONNECTION LAYER
// ----------------------------------------------------------------------------
let transport = null;

/**
 * Initialize connection - currently uses HTTP, but structured for future WebTransport/WebSocket
 */
async function connect() {
    try {
        setConnectionStatus('connecting', 'http');
        await setupHTTP();
    } catch (error) {
        console.error('Connection error:', error);
        setConnectionStatus('error', 'http');
        addLogMessage(`Error: Connection failed - ${error.message}`);
    }
}

/**
 * Setup HTTP connection (current implementation)
 */
async function setupHTTP() {
    // Start game session
    const res = await fetch(`${API_URL}/game/start`, { method: "POST" });
    if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    const data = await res.json();
    state.connection.sessionId = data.session_id;
    state.connection.status = 'connected';
    setConnectionStatus('connected', 'http');
    addLogMessage("System initialized. Welcome to Terra MUD.");
    
    // Load initial game state
    await loadGameState();
}

/**
 * Send message to server (HTTP implementation)
 */
async function sendMessage(obj) {
    if (!state.connection.sessionId) {
        console.error('No session ID available');
        return null;
    }

    try {
        const { channel, type, payload } = obj;
        
        // Route to appropriate HTTP endpoint
        if (channel === 'combat' && type === 'command') {
            if (payload.action === 'attack') {
                const res = await fetch(`${API_URL}/game/attack?session_id=${state.connection.sessionId}&enemy_id=${payload.enemyId}`, {
                    method: "POST"
                });
                return await res.json();
            } else if (payload.action === 'run') {
                // TODO: implement run
                return { success: false, message: "Run not implemented" };
            }
        } else if (channel === 'inventory' && type === 'request') {
            // Refresh inventory by reloading game state
            await loadGameState();
            return { success: true };
        } else if (channel === 'game' && type === 'command') {
            const res = await fetch(`${API_URL}/game/command`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    session_id: state.connection.sessionId,
                    command: payload.command,
                    args: payload.args || []
                })
            });
            return await res.json();
        } else if (channel === 'game' && type === 'adventure') {
            const res = await fetch(`${API_URL}/game/adventure?session_id=${state.connection.sessionId}`, {
                method: "POST"
            });
            return await res.json();
        } else if (channel === 'game' && type === 'heal') {
            const res = await fetch(`${API_URL}/game/heal?session_id=${state.connection.sessionId}`, {
                method: "POST"
            });
            return await res.json();
        } else if (channel === 'game' && type === 'claimLoot') {
            const res = await fetch(`${API_URL}/game/loot/claim?session_id=${state.connection.sessionId}`, {
                method: "POST"
            });
            return await res.json();
        }
        
        return null;
    } catch (error) {
        console.error('sendMessage error:', error);
        addLogMessage(`Error: ${error.message}`);
        return null;
    }
}

/**
 * Load game state from server
 */
async function loadGameState() {
    try {
        const res = await fetch(`${API_URL}/game/state?session_id=${state.connection.sessionId}`);
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }
        const data = await res.json();
        
        // Update state
        if (data.player) {
            state.player.hp = data.player.health;
            state.player.maxHp = data.player.max_health;
            state.player.name = data.player.name;
            state.player.level = data.player.level;
            state.player.xp = data.player.xp;
            state.player.xpToNext = data.player.xp_to_next;
            state.player.credits = data.player.credits;
            state.player.currentLocation = data.player.current_node_id;
            
            // Update inventory
            state.inventory.items = (data.player.inventory || []).map((item, idx) => ({
                id: idx,
                name: item.name,
                quantity: item.qty || item.count || 1
            }));
        }
        
        if (data.node) {
            state.location.name = data.node.name;
            state.location.desc = data.node.desc;
            state.location.exits = data.node.exits || {};
            state.location.grid = data.node.grid || {};
        }
        
        if (data.combat) {
            state.combat.inCombat = true;
            state.combat.enemies = (data.combat.enemies || []).map((e, idx) => ({
                id: idx,
                name: e.name,
                hp: e.health,
                maxHp: e.max_health,
                level: e.level
            }));
            if (state.combat.enemies.length > 0) {
                state.combat.enemy = state.combat.enemies[0];
            }
        } else {
            state.combat.inCombat = false;
            state.combat.enemies = [];
            state.combat.enemy = null;
        }
        
        if (data.loot) {
            state.loot = data.loot;
        }
        
        // Trigger UI updates
        handleEvent({ channel: 'system', type: 'state-update', payload: data });
        
    } catch (error) {
        console.error('loadGameState error:', error);
        addLogMessage(`Error loading game state: ${error.message}`);
    }
}

/**
 * Handle raw message from connection (for future WebTransport/WebSocket)
 */
function onRawMessage(msg) {
    let data;
    try {
        data = typeof msg === 'string' ? JSON.parse(msg) : msg;
    } catch (e) {
        console.error('Invalid JSON message', msg);
        return;
    }
    handleEvent(data);
}

// ----------------------------------------------------------------------------
// 3. EVENT LAYER
// ----------------------------------------------------------------------------

/**
 * Central event handler - routes by channel and type
 */
function handleEvent(evt) {
    const { channel, type, payload } = evt;
    
    switch (channel) {
        case 'combat':
            handleCombatEvent(type, payload);
            break;
        case 'inventory':
            handleInventoryEvent(type, payload);
            break;
        case 'log':
            handleLogEvent(type, payload);
            break;
        case 'system':
            handleSystemEvent(type, payload);
            break;
        default:
            console.warn('Unknown event channel', channel, evt);
    }
}

/**
 * Handle combat events
 */
function handleCombatEvent(type, payload) {
    if (type === 'state') {
        state.combat = {
            inCombat: payload.inCombat !== false,
            enemy: payload.enemy,
            enemies: payload.enemies || [],
        };
        if (payload.playerHp !== undefined) {
            state.player.hp = payload.playerHp;
        }
    } else if (type === 'update') {
        // Update from attack response
        if (payload.enemies !== undefined) {
            state.combat.enemies = payload.enemies.map((e, idx) => ({
                id: idx,
                name: e.name,
                hp: e.health,
                maxHp: e.max_health,
                level: e.level
            }));
            state.combat.enemy = state.combat.enemies[0] || null;
            state.combat.inCombat = state.combat.enemies.length > 0;
        }
        if (payload.player) {
            state.player.hp = payload.player.health;
            state.player.maxHp = payload.player.max_health;
        }
        if (payload.events) {
            payload.events.forEach(msg => addLogMessage(msg, 'combat'));
        }
        if (payload.combat_won) {
            state.combat.inCombat = false;
            state.combat.enemies = [];
            state.combat.enemy = null;
            if (payload.loot) {
                state.loot = payload.loot;
            }
        }
    }
    
    renderCombat();
    renderPlayerBar();
}

/**
 * Handle inventory events
 */
function handleInventoryEvent(type, payload) {
    if (type === 'full-state') {
        state.inventory.items = (payload.items || []).map((item, idx) => ({
            id: idx,
            name: item.name,
            quantity: item.qty || item.count || 1
        }));
    } else if (type === 'update') {
        // Merge updates
        if (payload.items) {
            state.inventory.items = payload.items.map((item, idx) => ({
                id: idx,
                name: item.name,
                quantity: item.qty || item.count || 1
            }));
        }
    }
    
    renderInventory();
}

/**
 * Handle log events
 */
function handleLogEvent(type, payload) {
    if (type === 'message') {
        addLogMessage(payload.text, payload.category || '');
    }
}

/**
 * Handle system events
 */
function handleSystemEvent(type, payload) {
    if (type === 'state-update') {
        // Full state update - re-render everything
        renderCombat();
        renderInventory();
        renderLocation();
        renderExits();
        renderPlayerBar();
        renderGrid();
        updateLocationVisual();
    } else if (type === 'connection-change') {
        setConnectionStatus(payload.status, payload.protocol);
    }
}

// ----------------------------------------------------------------------------
// 4. UI LAYER
// ----------------------------------------------------------------------------

/**
 * Render combat UI
 */
function renderCombat() {
    const container = document.getElementById('combat');
    if (!container) return;
    
    if (!state.combat.inCombat || state.combat.enemies.length === 0) {
        container.style.display = 'none';
        const combatView = document.getElementById('combatView');
        if (combatView) {
            combatView.classList.remove('active');
        }
        const locationView = document.getElementById('locationView');
        if (locationView) {
            locationView.style.display = 'block';
        }
        return;
    }
    
    container.style.display = 'block';
    const combatView = document.getElementById('combatView');
    if (combatView) {
        combatView.classList.add('active');
    }
    const locationView = document.getElementById('locationView');
    if (locationView) {
        locationView.style.display = 'none';
    }
    
    const enemiesContainer = document.getElementById('enemiesContainer');
    if (!enemiesContainer) return;
    
    enemiesContainer.innerHTML = '';
    
    state.combat.enemies.forEach((enemy, idx) => {
        const hpPercent = (enemy.hp / enemy.maxHp) * 100;
        
        const card = document.createElement('div');
        card.className = 'enemy-card';
        card.id = `enemy-${idx}`;
        
        card.innerHTML = `
            <div class="enemy-avatar">👾</div>
            <div class="enemy-name">${enemy.name}</div>
            <div class="enemy-level">LV ${enemy.level}</div>
            <div class="enemy-stats">
                <span>❤ ${enemy.hp} / ${enemy.maxHp} HP</span>
            </div>
            <div class="enemy-hp-bar">
                <div class="enemy-hp-fill" style="width: ${hpPercent}%"></div>
            </div>
            <button id="btn-attack-${idx}" class="attack-btn">⚔ ATTACK</button>
            <button id="btn-run-${idx}" class="attack-btn secondary" style="margin-top: 10px;">🏃 RUN</button>
        `;
        
        enemiesContainer.appendChild(card);
        
        // Attach event listeners
        const attackBtn = document.getElementById(`btn-attack-${idx}`);
        if (attackBtn) {
            attackBtn.onclick = () => onAttackClick(idx);
        }
        
        const runBtn = document.getElementById(`btn-run-${idx}`);
        if (runBtn) {
            runBtn.onclick = onRunClick;
        }
    });
}

/**
 * Render inventory UI
 */
function renderInventory() {
    const container = document.getElementById('inventory');
    if (!container) return;
    
    const content = document.getElementById('inventory-content');
    if (!content) return;
    
    const items = state.inventory.items;
    let html = '';
    
    if (!items.length) {
        html = '<p>(Empty)</p>';
    } else {
        html = '<ul id="inventory-list">';
        for (const it of items) {
            html += `<li>${it.name} (x${it.quantity || 1})</li>`;
        }
        html += '</ul>';
    }
    
    content.innerHTML = html;
    
    // Also update legacy inventory slots
    const slots = document.getElementById('inventorySlots');
    if (slots) {
        for (let i = 0; i < slots.children.length; i++) {
            const slot = slots.children[i];
            const item = items[i];
            
            if (item) {
                const amount = item.quantity || 1;
                slot.className = 'inv-slot filled';
                slot.innerHTML = `
                    <div class="inv-icon">${getItemIcon(item.name)}</div>
                    <div class="inv-name">${item.name}</div>
                    <span class="count">×${amount}</span>
                `;
                slot.title = item.name;
            } else {
                slot.className = 'inv-slot';
                slot.innerHTML = '';
                slot.title = '';
            }
        }
    }
}

/**
 * Render location UI
 */
function renderLocation() {
    const title = document.getElementById("locationName");
    const desc = document.getElementById("locationDesc");
    const locationEl = document.getElementById("currentLocation");
    
    if (title && state.location.name) {
        title.textContent = state.location.name.toUpperCase();
    }
    if (desc && state.location.desc) {
        desc.innerHTML = state.location.desc;
    }
    if (locationEl && state.player.currentLocation) {
        locationEl.textContent = state.player.currentLocation;
    }
}

/**
 * Render exits
 */
function renderExits() {
    const exitsPanel = document.getElementById("exitsList");
    if (!exitsPanel) return;
    exitsPanel.innerHTML = "";
    
    const exits = state.location.exits || {};
    Object.entries(exits).forEach(([label, target]) => {
        const btn = document.createElement("button");
        btn.className = "exit-btn";
        btn.innerHTML = `<span class="exit-icon">→</span> ${label.replace(/_/g, " ")}`;
        btn.onclick = () => visitExit(label);
        exitsPanel.appendChild(btn);
    });
}

/**
 * Render player bar (HP, credits, etc.)
 */
function renderPlayerBar() {
    const hpBar = document.getElementById("hpBar");
    const hpText = document.getElementById("hpText");
    const creditsEl = document.getElementById("credits");
    
    if (hpBar && hpText && state.player.hp !== null && state.player.maxHp !== null) {
        const pct = (state.player.hp / state.player.maxHp) * 100;
        hpBar.style.width = pct + "%";
        hpText.textContent = `${state.player.hp} / ${state.player.maxHp}`;
    }
    if (creditsEl && state.player.credits !== null) {
        creditsEl.textContent = state.player.credits;
    }
}

/**
 * Render grid map
 */
function renderGrid() {
    const gridMap = document.getElementById('gridMap');
    if (!gridMap) return;
    gridMap.innerHTML = '';
    
    const grid = state.location.grid || {};
    const gridX = grid.x || 0;
    const gridY = grid.y || 0;
    
    for (let y = -2; y <= 2; y++) {
        for (let x = -2; x <= 2; x++) {
            const tile = document.createElement('div');
            tile.className = 'grid-tile';
            
            if (x === gridX && y === gridY) {
                tile.className += ' current';
                tile.textContent = '◈';
            } else {
                tile.textContent = `${x},${y}`;
            }
            
            gridMap.appendChild(tile);
        }
    }
}

/**
 * Update location visual
 */
function updateLocationVisual() {
    const visual = document.getElementById('locationVisual');
    if (!visual) return;
    // Keep existing visual logic for now
}

/**
 * Add log message
 */
function addLogMessage(text, category = '') {
    state.log.push({ text, category, timestamp: Date.now() });
    
    const logDiv = document.getElementById('game-log-content');
    if (logDiv) {
        const p = document.createElement('div');
        p.className = 'message ' + category;
        p.textContent = text;
        logDiv.appendChild(p);
        logDiv.scrollTop = logDiv.scrollHeight;
        
        // Limit log size
        if (logDiv.children.length > 50) {
            logDiv.removeChild(logDiv.firstChild);
        }
    }
    
    // Also update legacy message log
    appendMessages([{ text, category }]);
    
    // Console log for debugging
    console.log(`[${category || 'log'}] ${text}`);
}

/**
 * Apply game state from backend (new simplified version)
 */
function applyGameState(state) {
    if (!state) return;
    gameState = state;

    if (state.session_id) {
        sessionId = state.session_id;
    }

    const player = state.player || {};

    // --- Health bar ---
    const hpBar  = document.getElementById("hpBar");
    const hpText = document.getElementById("hpText");

    const hp    = player.health     ?? player.hp     ?? 0;
    const maxHp = player.max_health ?? player.max_hp ?? 100;
    const pct   = Math.max(0, Math.min(100, Math.round((hp / maxHp) * 100)));

    if (hpBar)  hpBar.style.width = pct + "%";
    if (hpText) hpText.textContent = `${hp}/${maxHp}`;

    // --- Credits ---
    const creditsEl = document.getElementById("credits");
    if (creditsEl) {
        creditsEl.textContent = `${player.credits ?? 0}₡`;
    }

    // --- Location labels ---
    const currentLocationEl = document.getElementById("currentLocation");
    const locationNameEl    = document.getElementById("locationName");
    const locationDescEl    = document.getElementById("locationDesc");

    if (currentLocationEl) currentLocationEl.textContent = player.location_name || "Unknown Sector";
    if (locationNameEl)    locationNameEl.textContent    = player.location_name || "Unknown Sector";
    if (locationDescEl && state.location_description) {
        locationDescEl.innerHTML = state.location_description;
    }

    // --- Map nodes ---
    if (Array.isArray(state.locations)) {
        state.locations.forEach(loc => {
            const el = document.querySelector(`[data-location-id="${loc.id}"]`);
            if (!el) return;

            const locked = !!loc.locked;
            const cost   = loc.unlock_cost ?? 0;

            el.classList.toggle("location-locked", locked);
            el.classList.toggle("location-unlocked", !locked);
            el.classList.toggle("location-current", loc.id === player.location_id);

            if (locked && cost > 0) {
                el.setAttribute("data-cost", `${cost}₡`);
            } else {
                el.removeAttribute("data-cost");
            }
        });
    }

    // --- Inventory (your new renderer) ---
    renderInventoryNew(player.inventory || []);

    // --- Messages ---
    if (Array.isArray(state.messages)) {
        appendMessages(state.messages);
    }
}

/**
 * Append messages to message log
 */
function appendMessages(messages) {
    const log = document.getElementById("messageLog");
    if (!log) return;

    messages.forEach(msg => {
        const text = typeof msg === "string" ? msg : (msg.text ?? "");
        const category = typeof msg === "string" ? "" : (msg.category || "");
        if (!text) return;

        const entry = document.createElement("div");
        entry.className = "message-entry message " + category;
        entry.textContent = text;
        log.appendChild(entry);
    });

    // Auto-scroll to bottom
    log.scrollTop = log.scrollHeight;
    
    // Limit log size
    while (log.children.length > 20) {
        log.removeChild(log.firstChild);
    }
}

/**
 * Render inventory (new version with click handlers)
 */
function renderInventoryNew(inventory) {
    const container = document.getElementById("inventorySlots");
    if (!container) return;

    // Clear existing slots
    container.innerHTML = "";

    inventory.forEach((item, idx) => {
        const slot = document.createElement("div");
        slot.className = "inv-slot filled";

        const itemId = item.id || idx;
        const itemName = item.name || "Unknown";
        const quantity = item.quantity || item.count || item.qty || 1;

        slot.innerHTML = `
            <div class="inventory-item" data-item-id="${itemId}">
                <span class="inv-icon">${getItemIcon(itemName)}</span>
                <span class="inv-name">${itemName}</span>
                <span class="count">×${quantity}</span>
            </div>
        `;

        const itemEl = slot.querySelector(".inventory-item");
        if (itemEl) {
            itemEl.title = "Click to use";
            itemEl.style.cursor = "pointer";
            itemEl.addEventListener("click", () => {
                useItem(itemId);
            });
        }

        container.appendChild(slot);
    });
}

/**
 * Use item from inventory
 */
async function useItem(itemId) {
    if (!sessionId) return;
    try {
        const data = await apiPost(`/api/game/use-item?session_id=${encodeURIComponent(sessionId)}`, {
            item_id: itemId
        });
        applyGameState(data);
    } catch (err) {
        console.error("Use item failed", err);
        appendMessages([{ text: `Failed to use item: ${err.message}`, category: "error" }]);
    }
}

/**
 * Use an inventory item by name (via command API)
 */
async function useInventoryItem(itemName) {
    if (!sessionId) return;  // if your game uses sessions

    try {
        const res = await fetch(`${API_URL}/game/command`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id: sessionId,
                command: "use",      // this must match run_player_command(...) expectations
                args: [itemName]     // or "use Medpack" as a single string if your API wants that
            })
        });

        const data = await res.json();
        console.log("use response:", data);

        if (data.error) {
            appendMessages([{ text: data.error, category: "system" }]);
            return;
        }

        const msg = data.message || data.msg || data.result?.msg || `You used ${itemName}.`;
        appendMessages([{ text: msg, category: "system" }]);

        // re-fetch or update gameState so renderInventory() and HP/credits refresh
        await loadGameState();
    } catch (err) {
        console.error("Error using item:", err);
        appendMessages([{ text: "Error using item.", category: "system" }]);
    }
}

/**
 * Start game
 */
async function startGame() {
    try {
        const data = await apiPost("/api/game/start");
        applyGameState(data);
    } catch (err) {
        console.error("Failed to start game", err);
        appendMessages([{ text: `Failed to start game: ${err.message}`, category: "error" }]);
    }
}

/**
 * Do adventure
 */
async function doAdventure() {
    if (!sessionId) {
        console.warn("No session; starting game first.");
        await startGame();
    }
    try {
        const data = await apiPost(`/api/game/adventure?session_id=${encodeURIComponent(sessionId)}`);
        applyGameState(data);
    } catch (err) {
        console.error("Adventure failed", err);
        appendMessages([{ text: `Adventure failed: ${err.message}`, category: "error" }]);
    }
}

/**
 * Do heal
 */
async function doHeal() {
    if (!sessionId) return;
    try {
        const data = await apiPost(`/api/game/heal?session_id=${encodeURIComponent(sessionId)}`);
        applyGameState(data);
    } catch (err) {
        console.error("Heal failed", err);
        appendMessages([{ text: `Heal failed: ${err.message}`, category: "error" }]);
    }
}

/**
 * Do search
 */
async function doSearch() {
    if (!sessionId) return;
    try {
        const data = await apiPost(`/api/game/search?session_id=${encodeURIComponent(sessionId)}`);
        applyGameState(data);
    } catch (err) {
        console.error("Search failed", err);
        appendMessages([{ text: `Search failed: ${err.message}`, category: "error" }]);
    }
}

/**
 * Travel to location
 */
async function travelTo(locationId) {
    if (!sessionId) return;
    try {
        const data = await apiPost(`/api/game/travel?session_id=${encodeURIComponent(sessionId)}`, {
            location_id: locationId
        });
        applyGameState(data);
    } catch (err) {
        console.error("Travel failed", err);
        appendMessages([{ text: `Travel failed: ${err.message}`, category: "error" }]);
    }
}

/**
 * Unlock location
 */
async function unlockLocation(locationId, costLabel) {
    if (!sessionId) return;

    const confirmed = confirm(
        costLabel
            ? `Unlock this location for ${costLabel}?`
            : "Unlock this location?"
    );
    if (!confirmed) return;

    try {
        const data = await apiPost(`/api/game/unlock?session_id=${encodeURIComponent(sessionId)}`, {
            location_id: locationId
        });
        applyGameState(data);
    } catch (err) {
        console.error("Unlock failed", err);
        appendMessages([{ text: `Unlock failed: ${err.message}`, category: "error" }]);
    }
}

/**
 * Set connection status
 */
function setConnectionStatus(status, protocol = state.connection.protocol) {
    state.connection.status = status;
    state.connection.protocol = protocol;
    
    const el = document.getElementById('connection-status');
    if (!el) return;
    
    el.textContent = `${status.toUpperCase()} via ${protocol}`;
    el.className = `status-${status}`;
}

// ----------------------------------------------------------------------------
// 5. EVENT HANDLERS
// ----------------------------------------------------------------------------

/**
 * Attack button click handler
 */
async function onAttackClick(enemyId) {
    if (actionInProgress) return;
    actionInProgress = true;
    
    try {
        const response = await sendMessage({
            channel: 'combat',
            type: 'command',
            payload: { action: 'attack', enemyId }
        });
        
        if (response) {
            // Handle response
            handleEvent({
                channel: 'combat',
                type: 'update',
                payload: response
            });
            
            // Update game state
            if (response.player) {
                state.player.hp = response.player.health;
                state.player.maxHp = response.player.max_health;
                if (response.player.inventory) {
                    state.inventory.items = response.player.inventory.map((item, idx) => ({
                        id: idx,
                        name: item.name,
                        quantity: item.qty || item.count || 1
                    }));
                }
            }
            
            if (response.combat_won) {
                if (response.loot && response.loot.length > 0) {
                    state.loot = response.loot;
                    showView('loot');
                    renderLoot();
                } else {
                    showView('location');
                }
            }
            
            // Animation
            const card = document.getElementById(`enemy-${enemyId}`);
            if (card) {
                card.classList.add("hit");
                setTimeout(() => card.classList.remove("hit"), 400);
            }
        }
    } catch (error) {
        console.error('Attack error:', error);
        addLogMessage(`Error: ${error.message}`, 'error');
    } finally {
        setTimeout(() => { actionInProgress = false; }, 300);
    }
}

/**
 * Run button click handler
 */
async function onRunClick() {
    if (actionInProgress) return;
    actionInProgress = true;
    
    try {
        addLogMessage("You attempt to run away...", 'combat');
        // TODO: implement run logic
        state.combat.inCombat = false;
        state.combat.enemies = [];
        state.combat.enemy = null;
        renderCombat();
        showView('location');
    } catch (error) {
        console.error('Run error:', error);
        addLogMessage(`Error: ${error.message}`, 'error');
    } finally {
        setTimeout(() => { actionInProgress = false; }, 300);
    }
}

/**
 * Adventure button click handler
 */
async function onAdventureClick() {
    if (actionInProgress) return;
    actionInProgress = true;
    
    try {
        const response = await sendMessage({
            channel: 'game',
            type: 'adventure',
            payload: {}
        });
        
        if (response) {
            // Show adventure overlay
            const overlay = document.getElementById("adventureOverlay");
            const advText = document.getElementById("advText");
            const advEnemies = document.getElementById("advEnemies");
            
            if (advText) {
                advText.textContent = response.story || "While exploring, you encounter hostiles.";
            }
            
            if (advEnemies) {
                advEnemies.innerHTML = "";
                (response.enemies || []).forEach(e => {
                    const threat = e.threat || estimateThreat(e.level, state.player.level);
                    const p = document.createElement("p");
                    p.innerHTML = `
                        Raider detected: <strong>${e.name}</strong> (Level ${e.level}) —
                        <span style="color:${threatColor(threat)}">Threat: ${threat}</span>
                        ${threat === "intense" ? "<br><small>⚠ This raider can probably one-shot you at this level.</small>" : ""}
                    `;
                    advEnemies.appendChild(p);
                });
            }
            
            if (overlay) overlay.style.display = "flex";
        }
    } catch (error) {
        console.error('Adventure error:', error);
        addLogMessage(`Error: ${error.message}`, 'error');
    } finally {
        setTimeout(() => { actionInProgress = false; }, 300);
    }
}

/**
 * Confirm adventure
 */
async function confirmAdventure() {
    const overlay = document.getElementById("adventureOverlay");
    if (overlay) overlay.style.display = "none";
    
    addLogMessage("You chose to engage the raiders.", "combat");
    await loadGameState(); // Reload to get combat state
    showView("combat");
    renderCombat();
}

/**
 * Cancel adventure
 */
function cancelAdventure() {
    const overlay = document.getElementById("adventureOverlay");
    if (overlay) overlay.style.display = "none";
    addLogMessage("You decided to retreat. No combat started.", "system");
}

/**
 * Visit exit
 */
async function visitExit(exitName) {
    try {
        const response = await sendMessage({
            channel: 'game',
            type: 'command',
            payload: {
                command: 'visit',
                args: [exitName]
            }
        });
        
        if (response && response.message) {
            addLogMessage(response.message, "system");
        }
        
        await loadGameState();
    } catch (error) {
        console.error('Visit exit error:', error);
        addLogMessage(`Error: ${error.message}`, 'error');
    }
}

/**
 * Heal button click
 */
async function onHealClick() {
    if (actionInProgress) return;
    actionInProgress = true;
    
    try {
        const response = await sendMessage({
            channel: 'game',
            type: 'heal',
            payload: {}
        });
        
        if (response && response.player) {
            state.player.hp = response.player.health;
            state.player.maxHp = response.player.max_health;
            renderPlayerBar();
        }
        
        if (response && response.message) {
            addLogMessage(response.message, "system");
        }
    } catch (error) {
        console.error('Heal error:', error);
        addLogMessage(`Error: ${error.message}`, 'error');
    } finally {
        setTimeout(() => { actionInProgress = false; }, 300);
    }
}

/**
 * Search button click
 */
async function onSearchClick() {
    if (actionInProgress) return;
    actionInProgress = true;
    
    try {
        // Simple search implementation - can be enhanced later
        const found = Math.random() > 0.5;
        
        if (found) {
            const creditsFound = Math.floor(Math.random() * 6) + 2;
            state.player.credits += creditsFound;
            addLogMessage(`You found some scrap materials worth ${creditsFound} credits.`, 'system');
            renderPlayerBar();
        } else {
            addLogMessage('You searched the area but found nothing.', 'system');
        }
    } catch (error) {
        console.error('Search error:', error);
        addLogMessage(`Error: ${error.message}`, 'error');
    } finally {
        setTimeout(() => { actionInProgress = false; }, 300);
    }
}

/**
 * Claim loot
 */
async function onClaimLootClick() {
    if (actionInProgress) return;
    actionInProgress = true;
    
    try {
        const response = await sendMessage({
            channel: 'game',
            type: 'claimLoot',
            payload: {}
        });
        
        if (response && response.claimed && response.claimed.length > 0) {
            response.claimed.forEach(item => {
                addLogMessage(`You received: ${item.name} x${item.qty || 1}`, "system");
            });
        }
        
        if (response && response.player) {
            state.player.hp = response.player.health;
            state.player.maxHp = response.player.max_health;
            if (response.player.inventory) {
                state.inventory.items = response.player.inventory.map((item, idx) => ({
                    id: idx,
                    name: item.name,
                    quantity: item.qty || item.count || 1
                }));
            }
        }
        
        state.loot = [];
        showView('location');
        renderInventory();
        renderPlayerBar();
    } catch (error) {
        console.error('Claim loot error:', error);
        addLogMessage(`Error: ${error.message}`, 'error');
    } finally {
        setTimeout(() => { actionInProgress = false; }, 300);
    }
}

/**
 * Refresh inventory button
 */
async function onRefreshInventoryClick() {
    await sendMessage({
        channel: 'inventory',
        type: 'request',
        payload: {}
    });
    await loadGameState();
}

/**
 * Show view helper
 */
function showView(view) {
    const locationView = document.getElementById('locationView');
    const combatView = document.getElementById('combatView');
    const lootView = document.getElementById('lootView');
    
    if (locationView) {
        locationView.style.display = view === 'location' ? 'block' : 'none';
    }
    if (combatView) {
        combatView.classList.toggle('active', view === 'combat');
    }
    if (lootView) {
        lootView.classList.toggle('active', view === 'loot');
    }
}

/**
 * Render loot
 */
function renderLoot() {
    const container = document.getElementById('lootItems');
    if (!container) return;
    container.innerHTML = '';
    
    if (!state.loot || state.loot.length === 0) {
        container.textContent = "No loot available.";
        return;
    }
    
    state.loot.forEach(item => {
        const lootItem = document.createElement('div');
        lootItem.className = 'loot-item';
        lootItem.innerHTML = `
            <div class="loot-item-icon">${getItemIcon(item.name)}</div>
            <div class="loot-item-name">${item.name}</div>
            <div class="loot-item-amount">×${item.qty || 1}</div>
        `;
        container.appendChild(lootItem);
    });
}

/**
 * Get item icon
 */
function getItemIcon(itemName) {
    const icons = {
        'Credits': '💰',
        'Scrap': '🔩',
        'Scrap Alloy': '🔩',
        'Charge Cell': '🔋',
        'Energy Cell': '🔋',
        'Medpack': '💊',
        'Nano Repair Kit': '🔧',
        'Blaster': '🔫',
        'Weapon': '⚔️',
        'Armor': '🛡️'
    };
    
    const key = Object.keys(icons).find(k => k.toLowerCase() === itemName.toLowerCase());
    return icons[key] || '📦';
}

/**
 * Threat estimation helpers
 */
function estimateThreat(enemyLevel, playerLevel) {
    const diff = enemyLevel - playerLevel;
    if (diff <= -2) return "easy";
    if (diff <= 1) return "normal";
    if (diff <= 4) return "hard";
    return "intense";
}

function threatColor(level) {
    switch (level) {
        case "easy": return "#5dff9e";
        case "normal": return "#9eccff";
        case "hard": return "#ffb65d";
        case "intense": return "#ff5d7a";
        default: return "#fff";
    }
}

// ----------------------------------------------------------------------------
// 6. INITIALIZATION
// ----------------------------------------------------------------------------

/**
 * Create animated stars
 */
function createStars() {
    [document.getElementById('stars'), document.getElementById('stars2'), document.getElementById('stars3')].forEach(container => {
        if (!container) return;
        for (let i = 0; i < 50; i++) {
            const star = document.createElement('div');
            star.style.position = 'absolute';
            star.style.width = '2px';
            star.style.height = '2px';
            star.style.background = 'white';
            star.style.borderRadius = '50%';
            star.style.left = Math.random() * 100 + '%';
            star.style.top = Math.random() * 100 + '%';
            star.style.opacity = Math.random() * 0.8 + 0.2;
            container.appendChild(star);
        }
    });
}

/**
 * Initialize application
 */
async function init() {
    createStars();
    
    // Legacy handlers (keep for compatibility)
    const btnAdventureLegacy = document.getElementById('btn-adventure');
    if (btnAdventureLegacy) {
        btnAdventureLegacy.onclick = onAdventureClick;
    }
    
    const btnHealLegacy = document.getElementById('btn-heal');
    if (btnHealLegacy) {
        btnHealLegacy.onclick = onHealClick;
    }
    
    const btnSearchLegacy = document.getElementById('btn-search');
    if (btnSearchLegacy) {
        btnSearchLegacy.onclick = onSearchClick;
    }
    
    const btnRefreshInventory = document.getElementById('btn-refresh-inventory');
    if (btnRefreshInventory) {
        btnRefreshInventory.onclick = onRefreshInventoryClick;
    }
    
    const btnClaimLoot = document.getElementById('btn-claim-loot');
    if (btnClaimLoot) {
        btnClaimLoot.onclick = onClaimLootClick;
    }
    
    const btnConfirmAdventure = document.getElementById('btn-confirm-adventure');
    if (btnConfirmAdventure) {
        btnConfirmAdventure.onclick = confirmAdventure;
    }
    
    const btnCancelAdventure = document.getElementById('btn-cancel-adventure');
    if (btnCancelAdventure) {
        btnCancelAdventure.onclick = cancelAdventure;
    }
    
    // Also connect to server (legacy)
    await connect();
}

// DOMContentLoaded handler (new simplified version)
document.addEventListener("DOMContentLoaded", () => {
    const btnAdventure = document.getElementById("btnAdventure");
    const btnHeal      = document.getElementById("btnHeal");
    const btnSearch    = document.getElementById("btnSearch");

    if (btnAdventure) btnAdventure.addEventListener("click", doAdventure);
    if (btnHeal)      btnHeal.addEventListener("click", doHeal);
    if (btnSearch)    btnSearch.addEventListener("click", doSearch);

    document.querySelectorAll("#galaxyGrid [data-location-id]").forEach(el => {
        el.addEventListener("click", () => {
            const id   = el.getAttribute("data-location-id");
            const cost = el.getAttribute("data-cost");
            if (el.classList.contains("location-locked")) {
                unlockLocation(id, cost);
            } else {
                travelTo(id);
            }
        });
    });

    startGame();
});

