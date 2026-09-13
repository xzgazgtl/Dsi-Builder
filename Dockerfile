FROM devkitpro/devkitarm:latest

WORKDIR /app

# Instala os pacotes Nintendo DS e as ferramentas Python
RUN dkp-pacman -Sy --noconfirm nds-dev \
    && apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip \
    && rm -rf /var/lib/apt/lists/* \
    && dkp-pacman -Scc --noconfirm

COPY requirements.txt /tmp/requirements.txt

RUN python3 -m pip install --no-cache-dir --break-system-packages -r /tmp/requirements.txt

COPY . /app

ENV DEVKITPRO=/opt/devkitpro
ENV DEVKITARM=/opt/devkitpro/devkitARM
ENV PYTHONUNBUFFERED=1
ENV PORT=10000

EXPOSE 10000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 1 --timeout 360 app:app"]
