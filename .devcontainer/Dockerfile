FROM mcr.microsoft.com/devcontainers/universal:2

# Remove the stale Yarn apt source (universal:2 ships it, but the GPG key has expired).
# Install Tesseract 5 via the alex-p PPA — Ubuntu 20.04 (focal) only ships 4.1.1,
# which produces significantly worse OCR quality than 5.x.
RUN rm -f /etc/apt/sources.list.d/yarn.list /etc/apt/sources.list.d/yarn.list.save \
 && find /etc/apt/sources.list.d/ \( -name '*.list' -o -name '*.sources' \) \
      -exec grep -ql 'yarnpkg' {} \; -delete 2>/dev/null; \
    sed -i '/yarnpkg/d' /etc/apt/sources.list 2>/dev/null; \
    apt-get update \
      -o Acquire::AllowInsecureRepositories=true \
      -o Acquire::AllowDowngradeToInsecureRepositories=true \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      software-properties-common \
 && add-apt-repository -y ppa:alex-p/tesseract-ocr5 \
 && apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      poppler-utils \
      tesseract-ocr \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*
