# Omeka S, built here rather than pulled.
#
# The Omeka project publishes no official image, and the community ones are
# either abandoned, amd64-only, or ignore environment configuration. Building
# from the official release zip on the official PHP image keeps this stable,
# multi-arch, and dependent on nobody else's registry.
#
# The release zip is pinned by version and checksum. To move to a new release,
# change both build args together; the build fails if they disagree.

FROM php:8.2-apache

ARG OMEKA_VERSION=4.1.1
ARG OMEKA_SHA256=b53c9eeb5e8479c6991de3c47197abac59be577884e7224f92f87758f2f14f7f

# pdo_mysql, mbstring, xml and fileinfo are what Omeka's composer.json requires;
# mbstring, xml and fileinfo already ship with the PHP image. ImageMagick is the
# thumbnailer Omeka finds on its own; without one, uploads get no derivatives.
RUN apt-get update \
    && apt-get install -y --no-install-recommends imagemagick unzip \
    && docker-php-ext-install pdo_mysql \
    && a2enmod rewrite \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL -o /tmp/omeka.zip \
        "https://github.com/omeka/omeka-s/releases/download/v${OMEKA_VERSION}/omeka-s-${OMEKA_VERSION}.zip" \
    && echo "${OMEKA_SHA256}  /tmp/omeka.zip" | sha256sum -c - \
    && unzip -q /tmp/omeka.zip -d /tmp \
    && rm -rf /var/www/html \
    && mv /tmp/omeka-s /var/www/html \
    && rm /tmp/omeka.zip \
    && chown -R www-data:www-data /var/www/html/files

# Omeka ships a .htaccess that routes everything through index.php; Apache
# ignores it unless overrides are allowed.
RUN sed -i '/<Directory \/var\/www\/>/,/<\/Directory>/ s/AllowOverride None/AllowOverride All/' \
        /etc/apache2/apache2.conf \
    && echo 'ServerName localhost' > /etc/apache2/conf-available/servername.conf \
    && a2enconf servername

COPY docker-entrypoint.sh /usr/local/bin/omeka-entrypoint
RUN chmod +x /usr/local/bin/omeka-entrypoint

ENTRYPOINT ["omeka-entrypoint"]
CMD ["apache2-foreground"]
