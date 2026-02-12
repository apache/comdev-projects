# Local testing using Docker

## Build

```docker compose build```

## Set up data

```docker-config/setup-data.sh```

## Start application

```docker compose up```

Browse to ```http://localhost/```

Logs will appear under ```docker-data/logs```

## Start shell in running container

```docker compose exec projects bash```

## Start container with shell instead of webserver

```docker compose run -rm -P projects bash```

To start the server:

```apache2ctl -DFOREGROUND```
