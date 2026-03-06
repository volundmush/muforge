upgrade = """

-- BB System
CREATE TABLE bbs_boards (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    namespace VARCHAR(100) NOT NULL,
    category VARCHAR(100) NOT NULL DEFAULT 'Uncategorized',
    slug VARCHAR(100) NOT NULL,
    name TEXT NOT NULL,
    locks    JSONB NOT NULL DEFAULT '{}'::jsonb,
    next_post_num INT NOT NULL DEFAULT 1,
    data JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX ux_bbs_boards__namespace_slug
    ON bbs_boards (namespace, slug);

CREATE TABLE bbs_posts (
    id UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(),
    board_id UUID NOT NULL REFERENCES bbs_boards(id) ON DELETE CASCADE,
    num INT NOT NULL,
    comment_num INT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    author_id UUID NOT NULL REFERENCES actname(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    data JSONB NOT NULL DEFAULT '{}'::jsonb
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

"""

depends = [("core", "version001")]