upgrade = """
-- Channel System
CREATE TABLE channel (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    namespace VARCHAR(100) NOT NULL,
    category VARCHAR(100) DEFAULT 'Uncategorized',
    name CITEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL,
    locks JSONB NOT NULL DEFAULT '{}'::jsonb,
    data JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX ux_channel__namespace_name ON channel (namespace, name) WHERE deleted_at IS NULL;
CREATE INDEX idx_channel__namespace ON channel (namespace);

CREATE TABLE channel_message (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID NOT NULL REFERENCES channel(id) ON DELETE CASCADE,
    content JSONB NOT NULL DEFAULT '{}'::jsonb,
    author_id UUID NOT NULL REFERENCES actname(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ NULL,
    data JSONB NOT NULL DEFAULT '{}'::jsonb
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

"""

depends = [("core", "version001")]