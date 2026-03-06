

upgrade = """
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

depends = [("core", "version001")]