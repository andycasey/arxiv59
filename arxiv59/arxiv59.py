#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" arxiv59 -- missed it by --> <-- that much! """

from __future__ import (division, print_function, absolute_import,
                        unicode_literals)

import datetime
import logging
import os

import google
import requests
import tweepy
import xmltodict

__all__ = ["tweet_article", "format_tweet", "get_article_details"]

# SETUP SEARCH QUERIES TO EXECUTE AND TWEET FORMATTING.
DEFAULT_TWEET = u"{truncated_title}, by {authors} ({published}) {url}"

# Posts from today^ take priority.
# Note that 'today' means posted today but the arXiv date will be yesterday.
posted = datetime.date.fromordinal(datetime.date.today().toordinal() - 1)

TODAY_QUERY = posted.strftime("\"[v1] %a, %-d %b %Y 20:59:59\" site:arxiv.org")
TODAY_MUST_BE_PUBLISHED = lambda t: t == posted.strftime("%Y-%m-%dT20:59:59Z")
TODAY_TWEET = " ".join([u"[NEW TODAY]", DEFAULT_TWEET])

QUERIES = [
    (TODAY_QUERY, TODAY_MUST_BE_PUBLISHED, TODAY_TWEET),
    ("20:59:59 site:arxiv.org", lambda t: t.endswith("T20:59:59Z"), DEFAULT_TWEET),
    ("20:59:58 site:arxiv.org", lambda t: t.endswith("T20:59:58Z"), DEFAULT_TWEET),
    ("20:59:57 site:arxiv.org", lambda t: t.endswith("T20:59:57Z"), DEFAULT_TWEET)
]


def format_tweet(template, **kwargs):
    """
    Format a Tweet using the `TWEET` template, but limit the title such that the
    total length of the Tweet is 140 characters or less.
    """

    kwds = {}
    kwds.update(kwargs)
    kwds["truncated_title"] = kwds["title"]

    tweet = template.format(**kwds)
    N = len(tweet) - 140

    if N > 0:
        M = len(kwds["truncated_title"])
        kwds["truncated_title"] \
            = kwds["truncated_title"][:M - N - 3].strip() + "..."

        tweet = template.format(**kwds)

    assert 140 >= len(tweet)
    return tweet


def get_article_details(arxiv_url, published_or_updated=None):
    """
    Fetch an article using the arXiv API.

    :param arxiv_url:
        The URL of the paper.

    :param published_or_updated: [optional]
        A function that must return True for either the published or updated
        entry of the arXiv article for it to be considered valid.
        Helps avoid Google's "did you mean?" results.

    :returns:
        A four-length tuple containing the article title, the authors, the
        published time, and whether the article is valid (e.g., tweet it?).
    """

    if  not arxiv_url.startswith("http://arxiv.org/") \
    and not arxiv_url.startswith("https://arxiv.org/"):
        logging.info("Invalid URL: {}".format(arxiv_url))
        return (None, None, None, False)


    is_valid = True # unless otherwise found.

    number = arxiv_url.split("/")[-1].split("v")[0]
    context = arxiv_url.split("/")[-2]
    identifier = number if context == "abs" else "/".join([context, number])

    r = requests.get(
        "http://export.arxiv.org/api/query?search_query={}".format(identifier))

    feed = xmltodict.parse(r.text)["feed"]
    title = feed["entry"]["title"].replace("\n", "")
    N_authors = 1   if isinstance(feed["entry"]["author"], dict) \
                    else len(feed["entry"]["author"])
    
    if N_authors > 1:
        first_author = feed["entry"]["author"][0]["name"]
        if N_authors == 2:
            suffix = u"& {}".format(feed["entry"]["author"][1]["name"])
        else:
            suffix = "et al."

    else:
        first_author, suffix = (feed["entry"]["author"]["name"], "")

    published = feed["entry"]["published"].split("T")[1].rstrip("Z")

    if ":59:" not in published: # V-nth; mega fail.
        published = "{} on update!".format(
            feed["entry"]["updated"].split("T")[1].rstrip("Z"))
    
    authors = " ".join([first_author, suffix])

    if published_or_updated is not None:

        is_valid_updated = False
        is_valid_published = published_or_updated(feed["entry"]["published"])
        if "updated" in feed["entry"] and not is_valid_published:
            is_valid_updated = published_or_updated(feed["entry"]["updated"])

        is_valid = is_valid_published or is_valid_updated
        logging.debug("Validity for {} ({}): {} / {}".format(arxiv_url,
            "updated" in feed["entry"], is_valid_published, is_valid_updated))

    return (title, authors, published, is_valid)


def tweet_article(database):
    """
    Search for a new arXiv59 winner, and tweet it.

    :param database:
        A database connection to search for previous tweets and store new ones.
    """

    # Authenticate with Twitter.
    logging.info("Authenticating with Twitter..")
    auth = tweepy.OAuthHandler(
        os.environ["TWITTER_CONSUMER_KEY"],
        os.environ["TWITTER_CONSUMER_SECRET"]
    )
    auth.set_access_token(
        os.environ["TWITTER_ACCESS_TOKEN"],
        os.environ["TWITTER_ACCESS_SECRET"]
    )
    twitter, twitter_failures = (tweepy.API(auth), 0)
    
    cursor = database.cursor()

    for i, (query, published_or_updated, tweet_template) in enumerate(QUERIES):

        logging.info("Querying: {}".format(query))

        for j, url in enumerate(google.search(query)):
            
            # Clean up the url to remove 'v2' at the end.
            url = url[:-2] if url[-2] == "v" else url
            url = url.replace("https://", "http://")

            logging.info("Checking for URL {}".format(url))

            # Is this in the database?
            cursor.execute(
                "SELECT * FROM articles WHERE url = %s", (url, ))
            if cursor.rowcount:
                logging.info("Already tweeted that article. Moving on..")
                continue

            # Fetch the (new) article.
            title, authors, published, is_valid = get_article_details(url,
                published_or_updated=published_or_updated)

            if not is_valid:
                logging.info("This article is not valid! Moving on..")

                # Special exception for if it is the first query, because
                # Google is probably giving us 'Did you mean?' results..
                if i == 0 and j == 0:
                    logging.info("Special break because Google hates us.")
                    break

                continue

            # Tweet it!
            status = format_tweet(tweet_template, title=title, authors=authors,
                url=url, published=published)

            logging.info(u"Updating status: {}".format(status))

            try:
                r = twitter.update_status(status)
        
            except tweepy.TweepError:
                logging.exception("Failed to send tweet:")
                twitter_failures += 1

                if twitter_failures >= 3:
                    logging.warn("Is something wrong with Twitter?")
                    cursor.close()
                    return False

                continue

            else:
                created_at = r.created_at

            cursor.execute(
                """ INSERT INTO articles 
                        (url, title, authors, published, tweeted) 
                    VALUES (%s, %s, %s, %s, %s);""",
                (url, title, authors, published, created_at))

            cursor.close()
            database.commit()

            return True

    cursor.close()

    return False

