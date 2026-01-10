FROM ubuntu:24.04

RUN apt-get update && \
    apt-get install -y \
    bash \
    apache2 \
    python3

RUN \
    a2enmod cgi && \
    a2enmod headers

    WORKDIR /var/www/projects.apache.org

RUN echo "ServerName projects.local" > /etc/apache2/conf-enabled/servername.conf

COPY docker-config/25-projects.conf /etc/apache2/sites-enabled/000-default.conf

EXPOSE 80

CMD ["apache2ctl", "-DFOREGROUND"]