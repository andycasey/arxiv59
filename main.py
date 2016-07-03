#!/usr/bin/env python
# -*- coding: utf-8 -*-

""" arxiv59 -- missed it by --> <-- that much! """

from __future__ import (division, print_function, absolute_import,
                        unicode_literals)

import os
import psycopg2 as pg
import urlparse
from flask import Flask, g, request

import arxiv59

app = Flask(__name__)

def get_database():
    """ Get a database connection for the application, if there is context. """

    database = getattr(g, "_database", None)
    if database is None:
        urlparse.uses_netloc.append("postgres")
        url = urlparse.urlparse(os.environ["DATABASE_URL"])
        database = g._database = pg.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
    return database


@app.teardown_appcontext
def close_connection(exception):
    """
    Close any existing connection to the database.

    :param exception:
        An exception that is triggering the application teardown.
    """

    database = getattr(g, "_database", None)
    if database is not None:
        database.close()

    return None


@app.route("/")
def index():
    """ If we get sent the secret password, then tweet! """

    if  os.environ.get("SECRET", None) is not None \
    and request.args.get("SECRET", None) == os.environ.get("SECRET", None):
        arxiv59.tweet_article(get_database())

    # Everything is going to be 200 OK.
    return ("<code>OK</code>", 200)