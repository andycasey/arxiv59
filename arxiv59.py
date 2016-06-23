import google
import logging
import os
import requests
import sqlite3 as sql
import tweepy
import xmltodict
import yaml


QUERIES = [
    "20:59:59 site:arxiv.org",
    "20:59:58 site:arxiv.org",
    "20:59:57 site:arxiv.org"
]
DATABASE = "arxiv59.db"
TWEET = u"{title}, by {authors} ({published}) {url}"

# Load necessary credentials, either from a file or environment.
secret_keys = (
    "TWITTER_CONSUMER_KEY", "TWITTER_CONSUMER_SECRET",
    "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_SECRET")
secrets = dict(zip(secret_keys, [os.getenv(k) for k in secret_keys]))

credentials_path = "credentials.yaml"
if os.path.exists(credentials_path):
    with open(credentials_path, "r") as fp:
        secrets.update(yaml.load(fp))

else:
    # We are on Heroku. Only dispatch tweets when I allow.
    import sys
    print(sys.argv)
    raise a

def initialize(force=False):
    """
    Initialize the databse if it does not exist already.

    :param force: [optional]
        Force an initialization even if the database already exists.
    """

    if os.path.exists(DATABASE) and not force:
        return None

    connection = sql.connect(DATABASE)
    cursor = connection.cursor()

    # Create table.
    cursor.execute(
        "CREATE TABLE articles "\
        "(id INTEGER PRIMARY KEY, url, title, authors, published, tweeted);")

    connection.commit()
    connection.close()

    return True


def format_tweet(**kwargs):
    """
    Format a Tweet using the `TWEET` template, but limit the title such that the
    total length of the Tweet is 140 characters or less.
    """

    kwds = {}
    kwds.update(kwargs)

    tweet = TWEET.format(**kwds)
    N = len(tweet) - 140

    if N > 0:
        M = len(kwds["title"])
        kwds["title"] = kwds["title"][:M - N - 3].strip() + "..."

        tweet = TWEET.format(**kwds)

    assert 140 >= len(tweet)
    return tweet


def get_article_details(arxiv_url):
    """
    Fetch an article using the arXiv API.

    :param arxiv_url:
        The URL of the paper.
    """

    identifier = arxiv_url.split("/")[-1].split("v")[0]
    if "." not in identifier:
        identifier = "astro-ph/{}".format(identifier)

    r = requests.get(
        "http://export.arxiv.org/api/query?search_query={}".format(identifier))

    feed = xmltodict.parse(r.text)["feed"]
    title = feed["entry"]["title"].replace("\n", "")
    N_authors = len(feed["entry"]["author"])
    print("N_authors", N_authors, feed["entry"]["author"])
    
    if N_authors > 1:
        first_author = feed["entry"]["author"][0]["name"]
        if N_authors == 2:
            suffix = u"& {}".format(feed["entry"]["author"][1]["name"])
        else:
            suffix = "et al."

    else:
        first_author, suffix = (feed["entry"]["author"]["name"], "")

    published = feed["entry"]["published"].split("T")[1].rstrip("Z")

    if ":59:" not in published: # V2; mega fail.
        published = "{} on update!".format(
            feed["entry"]["updated"].split("T")[1].rstrip("Z"))
    

    authors = " ".join([first_author, suffix])

    return (title, authors, published)


def perform_search():
    """
    Search for a new arXiv59 winner. If one is found, tweet them then relax in
    happiness.
    """

    connection = sql.connect(DATABASE)
    cursor = connection.cursor()

    auth = tweepy.OAuthHandler(
        secrets["TWITTER_CONSUMER_KEY"], secrets["TWITTER_CONSUMER_SECRET"])
    auth.set_access_token(
        secrets["TWITTER_ACCESS_TOKEN"], secrets["TWITTER_ACCESS_SECRET"])

    twitter = tweepy.API(auth)

    for query in QUERIES:

        print("Querying: {}".format(query))

        for url in google.search(query):
            
            # Clean up the url to remove 'v2' at the end.
            url = url[:-2] if url[-2] == "v" else url
            url = url.replace("https://", "http://")

            print("Checking for URL {}".format(url))

            # Is this in the database?
            result = cursor.execute("SELECT * FROM articles WHERE url = ?", 
                (url, )).fetchone()

            if result is None:
                # Fetch the article.
                title, authors, published = get_article_details(url)

                # Tweet it!
                tweet = format_tweet(title=title, authors=authors, url=url,
                    published=published)
                print(u"Updating status: {}".format(tweet))

                try:
                    r = twitter.update_status(tweet)
            
                except tweepy.TweepError:
                    logging.exception("Failed to send tweet:")
                    created_at = -1

                else:
                    created_at = r.created_at

                cursor.execute(
                    """ INSERT INTO articles 
                            (url, title, authors, published, tweeted) 
                        VALUES (?, ?, ?, ?, ?);""",
                    (url, title, authors, published, created_at))
                cursor.close()

                connection.commit()
                connection.close()

                return True

    return False



if __name__ == "__main__":


    initialize()
    perform_search()
