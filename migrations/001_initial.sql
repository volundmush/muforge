BEGIN TRANSACTION;

CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS ltree;

-- auth section for users

CREATE TABLE users
(
    id                  UUID PRIMARY KEY   DEFAULT gen_random_uuid(),
    username            CITEXT NOT NULL,
    admin_level         INT       NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at          TIMESTAMPTZ NULL,
    current_password_id INT       NULL
);

CREATE UNIQUE INDEX ux_users__username_not_deleted ON users (username) WHERE deleted_at IS NULL;
CREATE INDEX idx_users__current_password_id ON users (current_password_id);

CREATE TABLE emails (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email CITEXT NOT NULL,
    verified_at TIMESTAMPTZ NULL,
    provider TEXT NOT NULL DEFAULT 'standard',
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
);

CREATE UNIQUE INDEX ux_emails__user_id_email_provider ON emails (user_id, email, provider);
CREATE INDEX idx_emails__user_id ON emails (user_id);
CREATE INDEX idx_emails__email ON emails (email);

ALTER TABLE emails
    ADD CONSTRAINT valid_email CHECK (
        email ~* '^[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}$'
        );

CREATE TABLE user_components (
    user_id         UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    component_name  VARCHAR(100) NOT NULL,
    data            JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (user_id, component_name)
);

CREATE INDEX idx_user_components__component_name ON user_components (component_name);

CREATE TABLE passwords
(
    id         SERIAL PRIMARY KEY,
    user_id    UUID      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    password_hash   TEXT      NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_passwords__user_id ON passwords (user_id);

ALTER TABLE users
    ADD CONSTRAINT fk_current_password
        FOREIGN KEY (current_password_id) REFERENCES passwords (id) ON DELETE SET NULL;

CREATE VIEW user_passwords AS
SELECT u.*,
       p.id         AS password_id,
       p.password_hash,
       p.created_at AS password_created_at
FROM users u
         LEFT JOIN passwords p ON u.current_password_id = p.id;

CREATE TABLE loginrecords
(
    id         BIGSERIAL PRIMARY KEY,
    user_id    UUID      NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_address INET      NOT NULL,
    user_agent VARCHAR(100) NOT NULL,
    success    BOOLEAN   NOT NULL
);

CREATE INDEX idx_loginrecords__user_id ON loginrecords (user_id);
CREATE INDEX idx_loginrecords__created_at ON loginrecords (created_at);

CREATE VIEW loginrecords_with_user AS
SELECT l.id,
       l.user_id,
       l.created_at,
       l.ip_address,
       l.user_agent,
       l.success,
       u.username
FROM loginrecords l
         JOIN users u ON l.user_id = u.id;

CREATE TABLE pcs (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID      NOT NULL REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
    name CITEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at     TIMESTAMPTZ NULL DEFAULT NULL,
    last_active_at TIMESTAMPTZ NULL DEFAULT NULL,
    approved_at TIMESTAMPTZ NULL,
    data JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX ux_pcs__name_not_deleted ON pcs (name) WHERE deleted_at IS NULL;
CREATE INDEX idx_pcs__user_id ON pcs (user_id);
CREATE INDEX idx_pcs__approved_at ON pcs (approved_at);
CREATE INDEX idx_pcs__last_active_at ON pcs (last_active_at);

CREATE TABLE pc_components (
    pc_id    UUID        NOT NULL REFERENCES pcs(id) ON DELETE CASCADE ON UPDATE CASCADE,
    component_name  VARCHAR(100) NOT NULL,
    data            JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (pc_id, component_name)
);

CREATE INDEX idx_pc_components__component_name ON pc_components (component_name);

CREATE TABLE pc_sessions (
    pc_id UUID NOT NULL PRIMARY KEY REFERENCES pcs(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE VIEW pcs_active AS
SELECT p.*,s.created_at as active_at FROM pc_sessions AS s LEFT JOIN pcs AS p ON s.pc_id=p.id;

CREATE TABLE pc_events (
    event_id BIGSERIAL NOT NULL PRIMARY KEY,
    pc_id UUID NOT NULL REFERENCES pcs(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    event_type LTREE NOT NULL,
    data JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_pc_events__pc_id ON pc_events (pc_id);
CREATE INDEX idx_pc_events__event_type ON pc_events (event_type);
CREATE INDEX idx_pc_events__event_type_gist ON pc_events USING GIST (event_type);
CREATE INDEX idx_pc_events__created_at ON pc_events (created_at);

CREATE TABLE actduo (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    pc_id UUID NULL REFERENCES pcs(id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX ux_actduo__user_id_pc_id ON actduo (user_id, pc_id) WHERE pc_id IS NOT NULL;
CREATE UNIQUE INDEX ux_actduo__user_id_null_pc ON actduo (user_id) WHERE pc_id IS NULL;
CREATE INDEX idx_actduo__user_id ON actduo (user_id);
CREATE INDEX idx_actduo__pc_id ON actduo (pc_id);

CREATE TABLE actname (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    actduo_id UUID NOT NULL REFERENCES actduo(id) ON DELETE RESTRICT,
    name VARCHAR(150) NOT NULL
);

CREATE UNIQUE INDEX ux_actname__actduo_id_name ON actname (actduo_id, name);
CREATE INDEX idx_actname__actduo_id ON actname (actduo_id);

-- The organization system. Namespaces are used to group them by system, such as factions or themes.
CREATE TABLE organizations (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    namespace VARCHAR(100) NOT NULL,
    name CITEXT NOT NULL,
    category VARCHAR(100) DEFAULT 'Uncategorized',
    abbreviation CITEXT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at     TIMESTAMPTZ NULL DEFAULT NULL,
    approved_at    TIMESTAMPTZ NUL DEFAULT NULL,
    hidden         BOOLEAN NOT NULL DEFAULT TRUE,
    private        BOOLEAN NOT NULL DEFAULT TRUE,
    member_permissions    JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE UNIQUE INDEX ux_organizations__name_not_deleted ON organizations (namespace, name) WHERE deleted_at IS NULL;
CREATE INDEX idx_organizations__abbreviation ON organizations (namespace, abbreviation);

CREATE TABLE organization_ranks (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    value INT NOT NULL,
    name TEXT NULL,
    permissions    JSONB NOT NULL DEFAULT '[]'::jsonb
);

CREATE UNIQUE INDEX ux_organization_ranks__organization_id_value ON organization_ranks (organization_id, value);
CREATE INDEX idx_organization_ranks__organization_id ON organization_ranks (organization_id);

CREATE TABLE organization_members (
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    pc_id UUID NOT NULL REFERENCES pcs(id) ON DELETE RESTRICT,
    rank_id UUID NOT NULL REFERENCES organization_ranks(id) ON DELETE RESTRICT,
    permissions JSONB NOT NULL DEFAULT '[]'::jsonb,
    title TEXT NULL,
    PRIMARY KEY (organization_id, pc_id)
);

CREATE INDEX idx_organization_members__pc_id ON organization_members (pc_id);
CREATE INDEX idx_organization_members__rank_id ON organization_members (rank_id);

--- Message Resource
CREATE TABLE msg_resource_category (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NULL REFERENCES organizations(id) ON DELETE RESTRICT,
    ic BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE UNIQUE INDEX ux_msg_resource_category__organization_id_ic
    ON msg_resource_category (organization_id, ic)
    WHERE organization_id IS NOT NULL;

CREATE UNIQUE INDEX ux_msg_resource_category__ic_public
    ON msg_resource_category (ic)
    WHERE organization_id IS NULL;

CREATE INDEX idx_msg_resource_category__organization_id ON msg_resource_category (organization_id);

-- BB System
CREATE TABLE bbs_boards (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_category_id UUID NOT NULL REFERENCES msg_resource_category(id) ON DELETE RESTRICT,
    category VARCHAR(100) NOT NULL DEFAULT 'Uncategorized',
    name TEXT NOT NULL,
    number INT NOT NULL,
    locks    JSONB NOT NULL DEFAULT '{}'::jsonb,
    next_post_num INT NOT NULL DEFAULT 1
);

CREATE UNIQUE INDEX ux_bbs_boards__resource_category_id_number
    ON bbs_boards (resource_category_id, number);

CREATE TABLE bbs_posts (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    board_id UUID NOT NULL REFERENCES bbs_boards(id) ON DELETE CASCADE,
    num INT NOT NULL,
    comment_num INT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    author_id UUID NOT NULL REFERENCES actname(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX ux_bbs_posts__board_id_num_comment_num ON bbs_posts (board_id, num, comment_num);
CREATE INDEX idx_bbs_posts__board_id ON bbs_posts (board_id);
CREATE INDEX idx_bbs_posts__author_id ON bbs_posts (author_id);
CREATE INDEX idx_bbs_posts__created_at ON bbs_posts (created_at);

CREATE TABLE bbs_read (
    post_id UUID NOT NULL REFERENCES bbs_posts(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    read_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (post_id, user_id)
);

CREATE INDEX idx_bbs_read__user_id ON bbs_read (user_id);

-- Location System
CREATE TABLE locations (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    parent_id UUID NULL REFERENCES locations(id) ON DELETE CASCADE,
    name CITEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL,
    slug TEXT NOT NULL,
    path LTREE NOT NULL UNIQUE,
    locks JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX ux_locations__root_name ON locations (parent_id, name) WHERE deleted_at IS NULL AND parent_id IS NULL;
CREATE UNIQUE INDEX ux_locations__child_name ON locations (parent_id, name) WHERE deleted_at IS NULL AND parent_id IS NOT NULL;
CREATE UNIQUE INDEX ux_locations__root_slug ON locations (parent_id, slug) WHERE deleted_at IS NULL AND parent_id IS NULL;
CREATE UNIQUE INDEX ux_locations__child_slug ON locations (parent_id, slug) WHERE deleted_at IS NULL AND parent_id IS NOT NULL;
CREATE INDEX idx_locations__parent_id ON locations (parent_id);
CREATE INDEX idx_locations__path_gist ON locations USING GIST (path);

CREATE TABLE location_instances (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES locations(id) ON DELETE CASCADE
);

CREATE INDEX idx_location_instances__location_id ON location_instances (location_id);

CREATE TABLE pc_locations (
    pc_id UUID NOT NULL PRIMARY KEY REFERENCES pcs(id) ON DELETE CASCADE,
    instance_id UUID NOT NULL REFERENCES location_instances(id) ON DELETE CASCADE
);

CREATE INDEX idx_pc_locations__instance_id ON pc_locations (instance_id);

CREATE TABLE location_actions (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    instance_id UUID NOT NULL REFERENCES location_instances(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    author_id UUID NOT NULL REFERENCES actname(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL,
    ic BOOLEAN NOT NULL DEFAULT FALSE,
    system VARCHAR(10) NOT NULL DEFAULT '',
    data JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_location_actions__instance_id ON location_actions (instance_id);
CREATE INDEX idx_location_actions__author_id ON location_actions (author_id);
CREATE INDEX idx_location_actions__created_at ON location_actions (created_at);

-- Channel System
CREATE TABLE channel (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_category_id UUID NOT NULL REFERENCES msg_resource_category(id) ON DELETE RESTRICT,
    category VARCHAR(100) DEFAULT 'Uncategorized',
    name CITEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL,
    locks JSONB NOT NULL DEFAULT '{}'::jsonb,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    uses_character BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE UNIQUE INDEX ux_channel__resource_category_id_name ON channel (resource_category_id, name) WHERE deleted_at IS NULL;
CREATE INDEX idx_channel__resource_category_id ON channel (resource_category_id);

CREATE TABLE channel_message (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID NOT NULL REFERENCES channel(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    author_id UUID NOT NULL REFERENCES actname(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL,
    locks JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_channel_message__channel_id ON channel_message (channel_id);
CREATE INDEX idx_channel_message__author_id ON channel_message (author_id);
CREATE INDEX idx_channel_message__created_at ON channel_message (created_at);

CREATE TABLE channel_subscription (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID NOT NULL REFERENCES channel(id) ON DELETE CASCADE,
    subscriber_id UUID NOT NULL REFERENCES actduo(id) ON DELETE CASCADE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    gagged BOOLEAN NOT NULL DEFAULT FALSE,
    data JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX ux_channel_subscription__channel_id_subscriber_id ON channel_subscription (channel_id, subscriber_id);

-- Plot System
CREATE TABLE plot (
    id BIGSERIAL NOT NULL PRIMARY KEY,
    name CITEXT NOT NULL,
    category VARCHAR(100) DEFAULT 'Uncategorized',
    description TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL,
    data JSONB NOT NULL DEFAULT '{}'::JSONB
);

CREATE UNIQUE INDEX ux_plot__name_not_deleted ON plot (name) WHERE deleted_at IS NULL;

CREATE TABLE plot_members (
    plot_id BIGINT NOT NULL REFERENCES plot(id) ON DELETE CASCADE,
    actor_id UUID NOT NULL REFERENCES actduo(id) ON DELETE CASCADE,
    member_type INT NOT NULL DEFAULT 0,
    PRIMARY KEY (plot_id, actor_id)
);

CREATE INDEX idx_plot_members__actor_id ON plot_members (actor_id);

-- Scene System
CREATE TABLE scene (
    id BIGSERIAL NOT NULL PRIMARY KEY,
    name CITEXT NOT NULL,
    pitch TEXT NULL,
    outcome TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL,
    data JSONB NOT NULL DEFAULT '{}'::JSONB,
    status INT NOT NULL DEFAULT 0,
    scheduled_at TIMESTAMPTZ NULL,
    started_at TIMESTAMPTZ NULL,
    ended_at TIMESTAMPTZ NULL
);

CREATE UNIQUE INDEX ux_scene__name_not_deleted ON scene (name) WHERE deleted_at IS NULL;
CREATE INDEX idx_scene__status ON scene (status);
CREATE INDEX idx_scene__deleted_at ON scene (deleted_at);
CREATE INDEX idx_scene__scheduled_at ON scene (scheduled_at);

CREATE TABLE scene_members (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    scene_id BIGINT NOT NULL REFERENCES scene(id) ON DELETE CASCADE,
    actor_id UUID NOT NULL REFERENCES actduo(id) ON DELETE CASCADE,
    member_type INT NOT NULL DEFAULT 0
);

CREATE UNIQUE INDEX ux_scene_members__scene_id_actor_id ON scene_members (scene_id, actor_id);
CREATE INDEX idx_scene_members__actor_id ON scene_members (actor_id);

CREATE TABLE scene_actions (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    scene_id BIGINT NOT NULL REFERENCES scene(id) ON DELETE CASCADE,
    action_type VARCHAR(10) NOT NULL,
    target_id UUID NOT NULL, -- channel, location action, etc.
    data JSONB NOT NULL DEFAULT '{}'::JSONB,
    -- the time slice
    began_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ NULL,
    -- Below are fields regarding the timeslice.
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL
);

CREATE INDEX idx_scene_actions__scene_id ON scene_actions (scene_id);
CREATE INDEX idx_scene_actions__target_id ON scene_actions (target_id);
CREATE INDEX idx_scene_actions__began_at ON scene_actions (began_at);

CREATE TABLE scene_plots (
    scene_id BIGINT NOT NULL REFERENCES scene(id) ON DELETE CASCADE,
    plot_id BIGINT NOT NULL REFERENCES plot(id) ON DELETE CASCADE,
    PRIMARY KEY (scene_id, plot_id)
);

CREATE INDEX idx_scene_plots__plot_id ON scene_plots (plot_id);

-- Text file system
CREATE TABLE text_category (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    thing_id UUID NOT NULL,
    thing_type VARCHAR(10) NOT NULL,
    name VARCHAR(20) NOT NULL
);

CREATE UNIQUE INDEX ux_text_category__thing_id_name ON text_category (thing_id, name);
CREATE INDEX idx_text_category__thing_id ON text_category (thing_id);
CREATE INDEX idx_text_category__thing_type ON text_category (thing_type);

CREATE TABLE text_file (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id UUID NOT NULL REFERENCES text_category(id) ON DELETE CASCADE,
    name VARCHAR(30) NOT NULL,
    content TEXT NOT NULL,
    author_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL,
    data JSONB NOT NULL DEFAULT '{}'::JSONB
);

CREATE UNIQUE INDEX ux_text_file__category_id_name_not_deleted ON text_file (category_id, name) WHERE deleted_at IS NULL;
CREATE INDEX idx_text_file__category_id ON text_file (category_id);
CREATE INDEX idx_text_file__author_id ON text_file (author_id);
CREATE INDEX idx_text_file__deleted_at ON text_file (deleted_at);

COMMIT;
