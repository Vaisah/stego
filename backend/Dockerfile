FROM debian:bullseye-slim

# bullseye is EOL (removed from deb.debian.org): repoint apt at the archive so
# packages still resolve, and stop apt rejecting the archived (expired) index.
RUN set -eux; \
    sed -i 's|deb.debian.org|archive.debian.org|g; s|security.debian.org|archive.debian.org|g' \
           /etc/apt/sources.list; \
    sed -i '/bullseye-updates/d' /etc/apt/sources.list; \
    echo 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/10no-check-valid-until


# bullseye is oldstable: keep apt-get update in the same layer as install so the
# package index matches the (rotating) security pool, and retry transient fetches.
RUN apt-get update -y \
    && apt-get install -y --fix-missing -o Acquire::Retries=5 \
       procps gcc make openssl git wget ca-certificates unzip p7zip ruby ruby-etc perl ruby-dev libz-dev
#&& apk add build-base gcc musl-dev make openssl git wget jpeg-dev zlib-dev p7zip ruby ruby-etc perl \
#&& apk add --virtual .build-dependencies ruby-dev


#
# Python
#
RUN echo "**** install Python ****" \
    && apt install python3 python3-pip -y

#
# ZSteg
#
RUN echo "**** install zsteg ****" \
    && gem install zsteg

#
# Steghide
#
RUN echo "**** install Steghide ****" \
    && apt install steghide -y

#
# Outguess
#
RUN echo "**** install Outguess ****" \
    && apt install outguess -y

#
# ExifTool
#
RUN echo "**** install ExifTools ****" \
    && apt install libimage-exiftool-perl -y

#
# Binwalk
#
RUN echo "**** install Binwalk ****" \
    && apt install binwalk -y

#
# Foremost
#
RUN echo "**** install Foremost ****" \
    && apt install foremost -y

#
# PCRT
#
RUN echo "**** install PCRT ****" \
    && cd /usr/bin \
    && wget https://raw.githubusercontent.com/Zeecka/PCRT/AperiSolve/PCRT.py \
    && mv PCRT.py PCRT \
    && chmod +x PCRT

#
# PngCheck
#
RUN echo "**** install PngCheck ****" \
    && cd /tmp \
    && wget http://libpng.org/pub/png/src/pngcheck-3.0.3.zip \
    && unzip pngcheck-3.0.3.zip \
    && mv Makefile.unx Makefile \
    && make \
    && mv pngcheck /usr/bin/

#
# StegExpose
#
# Java
# RUN apt install -y openjdk-17-jre

# # Install stegexpose script wrapper
# COPY StegExpose.jar /opt/stegexpose/stegexpose.jar
# RUN ln -s /opt/stegexpose/stegexpose.jar /usr/bin/stegexpose.jar \
#     && echo -e '#!/bin/sh\nexec java -jar /usr/bin/stegexpose.jar "$@"' > /usr/bin/stegexpose \
#     && chmod +x /usr/bin/stegexpose

# John the Ripper & Hashcat
ENV PATH="/usr/sbin:/usr/bin:${PATH}"
RUN apt-get install -y john hashcat

# Core john (1.8) cannot crack raw-* hashes and hashcat 6.1.1 segfaults in this
# EOL base image, so build John Jumbo (CPU-only) as the real cracking engine.
RUN apt-get install -y -o Acquire::Retries=5 libssl-dev zlib1g-dev \
    && git clone --depth 1 https://github.com/openwall/john /opt/john \
    && cd /opt/john/src \
    && ./configure \
    && make -s -j"$(nproc)" \
    && rm -rf /opt/john/.git
ENV JOHN_BIN=/opt/john/run/john




# hashid is provided by pip (see requirements.txt); it is only an optional
# fallback for hash-type detection, which is primarily regex-based.

# Default wordlist (rockyou) for the hash cracker. Prefer the packaged wordlist,
# falling back to a download; if both fail the worker reports it and the UI warns.
RUN mkdir -p /usr/share/wordlists \
    && (apt-get install -y wordlists || true) \
    && if [ -f /usr/share/wordlists/rockyou.txt.gz ]; then \
         gunzip -kf /usr/share/wordlists/rockyou.txt.gz; \
       fi \
    && if [ ! -f /usr/share/wordlists/rockyou.txt ]; then \
         wget -q -O /usr/share/wordlists/rockyou.txt \
           https://github.com/brannondorsey/naive-hashcat/releases/download/data/rockyou.txt \
           || echo "rockyou provisioning failed; upload a wordlist in the UI"; \
       fi

# Shared hand-off dir with the web container for custom wordlist uploads.
RUN mkdir -p /app/hashjobs


WORKDIR /app
COPY . .
# Normalize line endings (host may check out CRLF via git autocrlf) and ensure
# the shebang-executed workers are runnable.
RUN find /app -type f \( -name '*.sh' -o -name '*.py' \) -exec sed -i 's/\r$//' {} + \
    && chmod +x /app/start.sh /app/modules/*.py
RUN pip install -r requirements.txt
CMD ["./start.sh"]
