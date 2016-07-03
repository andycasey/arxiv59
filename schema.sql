
DROP TABLE IF EXISTS articles;
CREATE TABLE articles (
    url char(1024) not null,
    authors text not null,
    published text not null,
    tweeted integer not null
);
ALTER TABLE articles ADD COLUMN id BIGSERIAL PRIMARY KEY;
