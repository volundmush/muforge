upgrade = """
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
    member_permissions    JSONB NOT NULL DEFAULT '[]'::jsonb,
    data JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX ux_organizations__name_not_deleted ON organizations (namespace, name) WHERE deleted_at IS NULL;
CREATE INDEX idx_organizations__abbreviation ON organizations (namespace, abbreviation);

CREATE TABLE organization_ranks (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    value INT NOT NULL,
    name TEXT NULL,
    permissions    JSONB NOT NULL DEFAULT '[]'::jsonb,
    data JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX ux_organization_ranks__organization_id_value ON organization_ranks (organization_id, value);
CREATE INDEX idx_organization_ranks__organization_id ON organization_ranks (organization_id);

CREATE TABLE organization_members (
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    pc_id UUID NOT NULL REFERENCES pcs(id) ON DELETE RESTRICT,
    rank_id UUID NOT NULL REFERENCES organization_ranks(id) ON DELETE RESTRICT,
    permissions JSONB NOT NULL DEFAULT '[]'::jsonb,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    title TEXT NULL,
    PRIMARY KEY (organization_id, pc_id)
);

CREATE INDEX idx_organization_members__pc_id ON organization_members (pc_id);
CREATE INDEX idx_organization_members__rank_id ON organization_members (rank_id);

"""

downgrade = None

depends = list()
