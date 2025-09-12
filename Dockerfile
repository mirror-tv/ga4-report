FROM gcr.io/google.com/cloudsdktool/cloud-sdk:latest

COPY .  /usr/src/app/ga4-report
WORKDIR  /usr/src/app/ga4-report

RUN addgroup user && adduser -h /home/user -D user -G user -s /bin/sh

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        python3-venv python3-dev build-essential \
        libpq-dev libxml2-dev libxslt1-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# 建立 Python venv 以避免 PEP 668（externally-managed-environment）
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt 

ENV LC_ALL="en_US.utf8"

EXPOSE 8080
CMD ["/opt/venv/bin/uwsgi", "--ini", "server.ini"]
