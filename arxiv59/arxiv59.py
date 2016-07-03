#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" arxiv59 -- missed it by --> <-- that much! """

from __future__ import (division, print_function, absolute_import,
                        unicode_literals)

import datetime
import logging
import os
import sqlite3 as sql
import sys
import time
from collections import OrderedDict

import google
import requests
import tweepy
import xmltodict
import yaml

__all__ = ["tweet_article", "format_tweet", "get_article_details"]

# SETUP SEARCH QUERIES TO EXECUTE AND TWEET FORMATTING.
DEFAULT_TWEET = u"{truncated_title}, by {authors} ({published}) {url}"

# Posts from today^ take priority.
# Note that 'today' means posted today but the arXiv date will be yesterday.
posted = datetime.date.fromordinal(datetime.date.today().toordinal() - 1)

TODAY_QUERY = posted.strftime("\"[v1] %a, %-d %b %Y 20:59:59\" site:arxiv.org")
TODAY_TWEET = " ".join([u"[NEW TODAY]", DEFAULT_TWEET])

QUERIES = [
    (TODAY_QUERY, TODAY_TWEET),
    ("20:59:59 site:arxiv.org", DEFAULT_TWEET),
    ("20:59:58 site:arxiv.org", DEFAULT_TWEET),
    ("20:59:57 site:arxiv.org", DEFAULT_TWEET)
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


def get_article_details(arxiv_url):
    """
    Fetch an article using the arXiv API.

    :param arxiv_url:
        The URL of the paper.

    :returns:
        A three-length tuple containing the article title, the authors, and
        the published time.
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

    if ":59:" not in published: # V-nth; mega fail.
        published = "{} on update!".format(
            feed["entry"]["updated"].split("T")[1].rstrip("Z"))
    

    authors = " ".join([first_author, suffix])

    return (title, authors, published)


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
    twitter = tweepy.API(auth)

    cursor = database.cursor()

    for i, (query, tweet_template) in enumerate(QUERIES):

        logging.info("Querying: {}".format(query))

        for url in google.search(query):
            
            # Clean up the url to remove 'v2' at the end.
            url = url[:-2] if url[-2] == "v" else url
            url = url.replace("https://", "http://")

            logging.info("Checking for URL {}".format(url))

            # Is this in the database?
            result = cursor.execute(
                "SELECT * FROM articles WHERE url = ?", (url, )).fetchone()

            if result is not None:
                continue

            # Fetch the article.
            title, authors, published = get_article_details(url)

            # Tweet it!
            status = format_tweet(tweet_template, title=title, authors=authors,
                url=url, published=published)

            logging.info(u"Updating status: {}".format(status))

            '''
            try:
                r = twitter.update_status(status)
        
            except tweepy.TweepError:
                logging.exception("Failed to send tweet:")
                continue

            else:
                created_at = r.created_at

            cursor.execute(
                """ INSERT INTO articles 
                        (url, title, authors, published, tweeted) 
                    VALUES (?, ?, ?, ?, ?);""",
                (url, title, authors, published, created_at))
            '''

            cursor.close()
            database.commit()

            return True

    cursor.close()

    return False

