upgrade = """
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

"""

depends = [("core", "version001")]