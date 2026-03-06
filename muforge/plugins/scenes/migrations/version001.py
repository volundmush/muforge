upgrade = """
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

"""