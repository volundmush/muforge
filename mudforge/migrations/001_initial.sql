CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

CREATE OR REPLACE FUNCTION notify_table_change() RETURNS trigger AS $$
BEGIN
    PERFORM pg_notify(
        'table_changes',
        json_build_object(
            'table', TG_TABLE_NAME,
            'operation', TG_OP,
            'id', COALESCE(NEW.id, OLD.id)
        )::text
    );
RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- auth section for users

CREATE TABLE users
(
    id                  UUID PRIMARY KEY   DEFAULT gen_random_uuid(),
    email               CITEXT    NOT NULL UNIQUE,
    email_confirmed_at  TIMESTAMPTZ NULL,
    display_name        CITEXT    NULL,
    admin_level         INT       NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at          TIMESTAMPTZ NULL,
    current_password_id INT       NULL
);

CREATE UNIQUE INDEX unique_display_name ON users (display_name) WHERE display_name IS NOT NULL;

ALTER TABLE users
    ADD CONSTRAINT valid_email CHECK (
        email ~* '^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$'
        );

CREATE TRIGGER users_trigger
    AFTER INSERT OR UPDATE OR DELETE ON users
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

CREATE TABLE passwords
(
    id         SERIAL PRIMARY KEY,
    user_id    UUID      NOT NULL,
    password   TEXT      NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

ALTER TABLE users
    ADD CONSTRAINT fk_current_password
        FOREIGN KEY (current_password_id) REFERENCES passwords (id) ON DELETE SET NULL;

CREATE VIEW user_passwords AS
SELECT u.id         AS user_id,
       u.email,
       u.email_confirmed_at,
       u.display_name,
       u.admin_level,
       p.id         AS password_id,
       p.password,
       p.created_at AS password_created_at
FROM users u
         LEFT JOIN passwords p ON u.current_password_id = p.id;

CREATE TABLE loginrecords
(
    id         BIGSERIAL PRIMARY KEY,
    user_id    UUID      NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_address INET      NOT NULL,
    user_agent TEXT      NOT NULL,
    success    BOOLEAN   NOT NULL,
    CONSTRAINT fk_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE VIEW loginrecords_with_user AS
SELECT l.id,
       l.user_id,
       l.created_at,
       l.ip_address,
       l.user_agent,
       l.success,
       u.email,
       u.display_name
FROM loginrecords l
         JOIN users u ON l.user_id = u.id;

-- characters section
CREATE TABLE characters
(
    id             UUID PRIMARY KEY   DEFAULT gen_random_uuid(),
    user_id        UUID      NOT NULL,
    name           CITEXT    NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_active_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at     TIMESTAMPTZ NULL,
    CONSTRAINT fk_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX unique_character_name ON characters (name) WHERE deleted_at IS NULL;

CREATE TRIGGER characters_trigger
    AFTER INSERT OR UPDATE OR DELETE ON characters
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

CREATE TABLE character_spoofs
(
    id           SERIAL PRIMARY KEY,
    character_id UUID       NOT NULL,
    spoofed_name CITEXT    NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_character
        FOREIGN KEY (character_id) REFERENCES characters (id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX unique_character_spoof ON character_spoofs (character_id, spoofed_name);

CREATE VIEW character_spoofs_view AS
SELECT c.*,
       s.id as spoof_id,
       s.spoofed_name
FROM character_spoofs s
         LEFT JOIN characters c on s.character_id = c.id;

CREATE TABLE characters_active
(
    id          UUID       NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    admin_level INT       NOT NULL DEFAULT 0,
    spoofing_id INT       NOT NULL,
    metadata    JSONB     NOT NULL DEFAULT json_object(),
    CONSTRAINT fk_character
        FOREIGN KEY (id) REFERENCES characters (id) ON DELETE CASCADE,
    CONSTRAINT fk_spoof
        FOREIGN KEY (spoofing_id) REFERENCES character_spoofs (id) ON DELETE RESTRICT
);

CREATE TRIGGER characters_active_trigger
    AFTER INSERT OR UPDATE OR DELETE ON characters_active
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

CREATE VIEW characters_active_view AS
SELECT c.*,
       a.admin_level,
       a.created_at as active_created_at,
       a.metadata,
       a.spoofing_id,
       s.spoofed_name
FROM characters_active a
         LEFT JOIN characters c ON a.id = c.id
         LEFT JOIN character_spoofs s ON a.spoofing_id = s.id;

-- factions section
CREATE TABLE factions
(
    id                 SERIAL PRIMARY KEY,
    name               CITEXT       NOT NULL UNIQUE,
    abbreviation       CITEXT       NOT NULL UNIQUE,
    created_at         TIMESTAMPTZ    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMPTZ    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description        TEXT         NULL,
    category           VARCHAR(255) NOT NULL DEFAULT 'Uncategorized',
    private            BOOLEAN      NOT NULL DEFAULT TRUE,
    hidden             BOOLEAN      NOT NULL DEFAULT TRUE,
    can_leave          BOOLEAN      NOT NULL DEFAULT TRUE,
    kick_rank          INT          NOT NULL DEFAULT 2,
    start_rank         INT          NOT NULL DEFAULT 4,
    title_self         BOOLEAN      NOT NULL DEFAULT TRUE,
    member_permissions TEXT[]       NOT NULL DEFAULT '{}',
    public_permissions TEXT[]       NOT NULL DEFAULT '{}',
    lock_data          JSONB       NOT NULL DEFAULT json_object()
);

CREATE TRIGGER factions_trigger
    AFTER INSERT OR UPDATE OR DELETE ON factions
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

CREATE TABLE faction_ranks
(
    id          SERIAL PRIMARY KEY,
    faction_id  INT       NOT NULL,
    name        TEXT      NOT NULL,
    value       INT       NOT NULL,
    permissions TEXT[]    NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_faction
        FOREIGN KEY (faction_id) REFERENCES factions (id) ON DELETE CASCADE
);

CREATE TRIGGER faction_ranks_trigger
    AFTER INSERT OR UPDATE OR DELETE ON faction_ranks
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

CREATE TABLE faction_members
(
    id           SERIAL PRIMARY KEY,
    faction_id   INT       NOT NULL,
    character_id UUID       NOT NULL,
    rank_id      INT       NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    permissions  TEXT[]    NOT NULL DEFAULT '{}',
    title        TEXT      NULL,
    CONSTRAINT fk_faction
        FOREIGN KEY (faction_id) REFERENCES factions (id) ON DELETE CASCADE,
    CONSTRAINT fk_user
        FOREIGN KEY (character_id) REFERENCES characters (id) ON DELETE CASCADE,
    CONSTRAINT fk_rank
        FOREIGN KEY (rank_id) REFERENCES faction_ranks (id) ON DELETE RESTRICT
);

CREATE TRIGGER faction_members_trigger
    AFTER INSERT OR UPDATE OR DELETE ON faction_members
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

-- Myrddin's BBS section

CREATE TABLE boards
(
    id             SERIAL PRIMARY KEY,
    name           CITEXT    NOT NULL,
    description    TEXT      NULL,
    faction_id     INT       NULL,
    board_order    INT       NOT NULL,
    anonymous_name TEXT      NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    lock_data      JSONB       NOT NULL DEFAULT json_object(),
    CONSTRAINT fk_faction
        FOREIGN KEY (faction_id) REFERENCES factions (id) ON DELETE RESTRICT
);

-- Gimme unique names and orders per faction
CREATE UNIQUE INDEX unique_board_name ON boards (faction_id, name) WHERE faction_id IS NOT NULL;
CREATE UNIQUE INDEX unique_board_order ON boards (faction_id, board_order) WHERE faction_id IS NOT NULL;
-- And without a faction
CREATE UNIQUE INDEX unique_board_name_no_faction ON boards (name) WHERE faction_id IS NULL;
CREATE UNIQUE INDEX unique_board_order_no_faction ON boards (board_order) WHERE faction_id IS NULL;

CREATE TRIGGER boards_trigger
    AFTER INSERT OR UPDATE OR DELETE ON boards
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

CREATE VIEW board_view AS
SELECT b.*,
       CONCAT(COALESCE(f.abbreviation, ''), b.board_order::text) AS board_key,
       f.name                                                    AS faction_name,
       f.abbreviation                                            AS faction_abbreviation
FROM boards b
         LEFT JOIN factions f ON b.faction_id = f.id;

CREATE TABLE board_posts
(
    id         BIGSERIAL PRIMARY KEY,
    board_id   INT       NOT NULL,
    post_order INT       NOT NULL,
    sub_order  INT       NOT NULL,
    spoof_id   INT       NOT NULL,
    title      TEXT      NOT NULL,
    body       TEXT      NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_board
        FOREIGN KEY (board_id) REFERENCES boards (id) ON DELETE CASCADE,
    CONSTRAINT fk_spoof
        FOREIGN KEY (spoof_id) REFERENCES character_spoofs (id) ON DELETE CASCADE
);

-- Gimme unique orders per board
CREATE UNIQUE INDEX unique_post_order ON board_posts (board_id, post_order, sub_order);

CREATE TRIGGER boards_trigger_trigger
    AFTER INSERT OR UPDATE OR DELETE ON board_posts
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

CREATE VIEW board_post_view AS
SELECT p.*,
       CASE
           WHEN p.sub_order = 0 THEN p.post_order::text
           ELSE p.post_order::text || '.' || p.sub_order::text
           END AS post_key
FROM board_posts p;

CREATE VIEW board_post_view_full AS
SELECT p.*,
       s.id      as character_id,
       s.name    as character_name,
       s.spoofed_name,
       s.user_id AS user_id,
       b.board_key,
       b.name    AS board_name,
       b.faction_id,
       b.faction_name,
       b.faction_abbreviation,
       b.anonymous_name
FROM board_post_view p
         LEFT JOIN character_spoofs_view s ON s.spoof_id = p.spoof_id
         LEFT JOIN board_view b ON p.board_id = b.id;

CREATE TABLE board_posts_read
(
    id      BIGSERIAL PRIMARY KEY,
    post_id BIGINT    NOT NULL,
    user_id UUID      NOT NULL,
    read_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_post
        FOREIGN KEY (post_id) REFERENCES board_posts (id) ON DELETE CASCADE,
    CONSTRAINT fk_user
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX unique_post_read ON board_posts_read (user_id, post_id);

-- Channels section

CREATE TABLE channels
(
    id          SERIAL PRIMARY KEY,
    category    VARCHAR(255) NOT NULL DEFAULT 'Uncategorized',
    name        CITEXT       NOT NULL,
    description TEXT         NULL,
    created_at  TIMESTAMPTZ    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMPTZ    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    lock_data   JSONB       NOT NULL DEFAULT json_object()
);

CREATE TRIGGER channels_trigger
    AFTER INSERT OR UPDATE OR DELETE ON channels
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

CREATE TABLE channel_members
(
    id           SERIAL PRIMARY KEY,
    channel_id   INT       NOT NULL,
    character_id UUID       NOT NULL,
    listening    BOOLEAN   NOT NULL DEFAULT TRUE,
    aliases      TEXT[]    NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_channel
        FOREIGN KEY (channel_id) REFERENCES channels (id) ON DELETE CASCADE,
    CONSTRAINT fk_character
        FOREIGN KEY (character_id) REFERENCES characters (id) ON DELETE CASCADE
);

CREATE TRIGGER channel_members_trigger
    AFTER INSERT OR UPDATE OR DELETE ON channel_members
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

CREATE TABLE channel_messages
(
    id           BIGSERIAL PRIMARY KEY,
    channel_id   INT       NOT NULL,
    character_id UUID       NOT NULL,
    message      TEXT      NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_channel
        FOREIGN KEY (channel_id) REFERENCES channels (id) ON DELETE CASCADE,
    CONSTRAINT fk_character
        FOREIGN KEY (character_id) REFERENCES characters (id) ON DELETE CASCADE
);

CREATE TRIGGER channel_messages_trigger
    AFTER INSERT OR UPDATE OR DELETE ON channel_messages
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

-- Radio Frequency section is very much like channels but for roleplaying...

CREATE TABLE frequencies
(
    id          SERIAL PRIMARY KEY,
    category    VARCHAR(255) NOT NULL DEFAULT 'Uncategorized',
    name        CITEXT       NOT NULL,
    description TEXT         NULL,
    created_at  TIMESTAMPTZ    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMPTZ    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    lock_data   JSONB       NOT NULL DEFAULT json_object(),
    owner_id    UUID          NULL,
    CONSTRAINT fk_owner
        FOREIGN KEY (owner_id) REFERENCES characters (id) ON DELETE SET NULL
);

CREATE TRIGGER frequencies_trigger
    AFTER INSERT OR UPDATE OR DELETE ON frequencies
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

CREATE TABLE frequencies_admins
(
    id           SERIAL PRIMARY KEY,
    frequency_id INT       NOT NULL,
    character_id UUID       NOT NULL,
    -- 0 is moderator, 1 is admin.
    admin_type   INT       NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_frequency
        FOREIGN KEY (frequency_id) REFERENCES frequencies (id) ON DELETE CASCADE,
    CONSTRAINT fk_character
        FOREIGN KEY (character_id) REFERENCES characters (id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX unique_frequency_admin ON frequencies_admins (frequency_id, character_id);

CREATE TRIGGER frequencies_admins_trigger
    AFTER INSERT OR UPDATE OR DELETE ON frequencies_admins
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

CREATE TABLE frequency_members
(
    id           SERIAL PRIMARY KEY,
    frequency_id INT       NOT NULL,
    character_id UUID       NOT NULL,
    listening    BOOLEAN   NOT NULL DEFAULT TRUE,
    aliases      TEXT[]    NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_frequency
        FOREIGN KEY (frequency_id) REFERENCES frequencies (id) ON DELETE CASCADE,
    CONSTRAINT fk_character
        FOREIGN KEY (character_id) REFERENCES characters (id) ON DELETE CASCADE
);

CREATE TRIGGER frequency_members_trigger
    AFTER INSERT OR UPDATE OR DELETE ON frequency_members
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

CREATE TABLE frequency_messages
(
    id           BIGSERIAL PRIMARY KEY,
    frequency_id INT       NOT NULL,
    spoof_id     INT       NOT NULL,
    message      TEXT      NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_frequency
        FOREIGN KEY (frequency_id) REFERENCES frequencies (id) ON DELETE CASCADE,
    CONSTRAINT fk_spoof
        FOREIGN KEY (spoof_id) REFERENCES character_spoofs (id) ON DELETE RESTRICT
);

CREATE TRIGGER frequency_messages_trigger
    AFTER INSERT OR UPDATE OR DELETE ON frequency_messages
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

-- Rooms Section

CREATE TABLE regions
(
    id         SERIAL PRIMARY KEY,
    name       CITEXT    NOT NULL,
    parent_id  INT       NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_parent
        FOREIGN KEY (parent_id) REFERENCES regions (id) ON DELETE SET NULL
);

CREATE TRIGGER regions_trigger
    AFTER INSERT OR UPDATE OR DELETE ON regions
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

CREATE TABLE region_rooms
(
    id          SERIAL PRIMARY KEY,
    region_id   INT       NOT NULL,
    name        CITEXT    NOT NULL,
    description TEXT      NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_region
        FOREIGN KEY (region_id) REFERENCES regions (id) ON DELETE RESTRICT
);

CREATE TRIGGER region_rooms_trigger
    AFTER INSERT OR UPDATE OR DELETE ON region_rooms
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

CREATE TABLE room_events
(
    id             BIGSERIAL PRIMARY KEY,
    room_id        INT          NOT NULL,
    -- Nullable, to account for system events.
    spoof_id       INT          NULL,
    event_type     INT          NOT NULL DEFAULT 0,
    event_type_sub VARCHAR(255) NULL,
    event_data     TEXT         NULL,
    created_at     TIMESTAMPTZ    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMPTZ    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_room
        FOREIGN KEY (room_id) REFERENCES region_rooms (id) ON DELETE RESTRICT,
    CONSTRAINT fk_spoof
        FOREIGN KEY (spoof_id) REFERENCES character_spoofs (id) ON DELETE RESTRICT
);

CREATE TRIGGER room_events_trigger
    AFTER INSERT OR UPDATE OR DELETE ON room_events
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

-- Roleplay Logging

CREATE TABLE scenes
(
    id           SERIAL PRIMARY KEY,
    name         CITEXT    NOT NULL UNIQUE,
    description  TEXT      NULL,
    resolution   TEXT      NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    scheduled_at TIMESTAMPTZ NULL,
    started_at   TIMESTAMPTZ NULL,
    ended_at     TIMESTAMPTZ NULL
);

CREATE TRIGGER scenes_trigger
    AFTER INSERT OR UPDATE OR DELETE ON scenes
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

CREATE TABLE scene_participants
(
    id               SERIAL PRIMARY KEY,
    scene_id         INT       NOT NULL,
    character_id     UUID       NOT NULL,
    -- 3 is owner/GM, 2 is co-owner, 1 is tagged for interest, 0 is simply there.
    participant_type INT       NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_scene
        FOREIGN KEY (scene_id) REFERENCES scenes (id) ON DELETE RESTRICT,
    CONSTRAINT fk_character
        FOREIGN KEY (character_id) REFERENCES characters (id) ON DELETE RESTRICT
);

CREATE TRIGGER scene_participants_trigger
    AFTER INSERT OR UPDATE OR DELETE ON scene_participants
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

-- Gimme a unique character_id per scene_participant's scene...
CREATE UNIQUE INDEX unique_scene_participant ON scene_participants (scene_id, character_id);

CREATE TABLE scene_events
(
    id          SERIAL PRIMARY KEY,
    scene_id    INT       NOT NULL,
    room_id     INT       NOT NULL,
    events_from TIMESTAMPTZ NOT NULL,
    events_to   TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_scene
        FOREIGN KEY (scene_id) REFERENCES scenes (id) ON DELETE RESTRICT,
    CONSTRAINT fk_room
        FOREIGN KEY (room_id) REFERENCES region_rooms (id) ON DELETE RESTRICT
);

CREATE TRIGGER scene_events_trigger
    AFTER INSERT OR UPDATE OR DELETE ON scene_events
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

CREATE TABLE scene_frequency_messages
(
    id           BIGSERIAL PRIMARY KEY,
    scene_id     INT       NOT NULL,
    frequency_id INT       NOT NULL,
    events_from  TIMESTAMPTZ NOT NULL,
    events_to    TIMESTAMPTZ NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_scene
        FOREIGN KEY (scene_id) REFERENCES scenes (id) ON DELETE RESTRICT,
    CONSTRAINT fk_frequency
        FOREIGN KEY (frequency_id) REFERENCES frequencies (id) ON DELETE RESTRICT
);

CREATE TRIGGER scene_frequency_messages_trigger
    AFTER INSERT OR UPDATE OR DELETE ON scene_frequency_messages
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

CREATE TABLE plots
(
    id          SERIAL PRIMARY KEY,
    name        CITEXT    NOT NULL UNIQUE,
    description TEXT      NULL,
    resolution  TEXT      NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at  TIMESTAMPTZ NULL,
    ended_at    TIMESTAMPTZ NULL
);

CREATE TRIGGER plots_trigger
    AFTER INSERT OR UPDATE OR DELETE ON plots
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

CREATE TABLE plot_runners
(
    id           SERIAL PRIMARY KEY,
    plot_id      INT       NOT NULL,
    character_id UUID       NOT NULL,
    -- 2 is runner, 1 is co-runner, 0 is helper.
    runner_type  INT       NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_plot
        FOREIGN KEY (plot_id) REFERENCES plots (id) ON DELETE CASCADE,
    CONSTRAINT fk_character
        FOREIGN KEY (character_id) REFERENCES characters (id) ON DELETE CASCADE
);

CREATE TRIGGER plot_runners_trigger
    AFTER INSERT OR UPDATE OR DELETE ON plot_runners
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

-- Gimme a unique character_id per plot_runner's plot...
CREATE UNIQUE INDEX unique_plot_runner ON plot_runners (plot_id, character_id);

-- Info Section
CREATE TABLE info_holders
(
    id          SERIAL PRIMARY KEY,
    -- 0 is characters... more types are possible.
    entity_type INT    NOT NULL,
    entity_id   INT    NOT NULL,
    category    CITEXT NOT NULL
);

CREATE TRIGGER info_holders_trigger
    AFTER INSERT OR UPDATE OR DELETE ON info_holders
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

CREATE UNIQUE INDEX unique_info_holder ON info_holders (entity_type, entity_id, category);

CREATE TABLE info_files
(
    id          SERIAL PRIMARY KEY,
    holder_id   INT       NOT NULL,
    name        CITEXT    NOT NULL,
    description TEXT      NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata    JSONB     NOT NULL DEFAULT json_object(),
    CONSTRAINT fk_holder
        FOREIGN KEY (holder_id) REFERENCES info_holders (id) ON DELETE CASCADE
);

CREATE TRIGGER info_files_trigger
    AFTER INSERT OR UPDATE OR DELETE ON info_files
    FOR EACH ROW EXECUTE FUNCTION notify_table_change();

CREATE UNIQUE INDEX unique_info_name ON info_files (holder_id, name);