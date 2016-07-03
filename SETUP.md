Setup Guide
===========

0.  Login to heroku:

    `heroku login`

1.  Clone this repository:

    ````
    git clone git@github.com:andycasey/arxiv59.git arxiv59
    cd arxiv59/
    ````

2.  Create a Heroku app:

    `heroku create`

4.  Set the required Twitter keys/tokens as environment variables on Heroku.

    ````
    heroku config:set TWITTER_CONSUMER_KEY=<twitter_consumer_key>
    heroku config:set TWITTER_CONSUMER_SECRET=<twitter_consumer_secret>
    heroku config:set TWITTER_ACCESS_TOKEN=<twitter_access_token>
    heroku config:set TWITTER_ACCESS_SECRET=<twitter_access_secret>
    ````

5.  Create a `SECRET` environment variable on Heroku, which we will send with our cron job to trigger a new tweet.
  
    ````
    heroku config:set SECRET=gandalf
    ````

6. Set up a Heroku Postgres addon, and initialise the database with our schema.

    ````
    heroku addons:create heroku-postgresql:hobby-basic
    heroku config -s | grep DATABASE_URL | sed 's:.*DATABASE_URL=::' | awk '{ print "psql", $1, "-f schema.sql" }' | sh
    ````

7.  Push a new commit to Heroku to trigger a build.

    ````
    touch tmp
    git add tmp
    git commit -m "Trigger Heroku build"
    git push heroku master
    ````

8. Create a cron job on a different computer to ping the Heroku app with the right `SECRET` on weekdays.

    ````
    crontab -e
    ```

    Then enter:

    ````
    0 11 * * 1,2,3,4,5 curl https://arxiv59.herokuapp.com?SECRET=gandalf >/dev/null 2>&1
    ````
