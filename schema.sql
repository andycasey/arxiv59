
DROP TABLE IF EXISTS articles;
CREATE TABLE articles (
    url char(1024) not null,
    title char(1024) not null,
    authors text not null,
    published text not null,
    tweeted char(30) not null
);
ALTER TABLE articles ADD CONSTRAINT unique_url UNIQUE (url);
