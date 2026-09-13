FROM devkitpro/devkitarm:latest

WORKDIR /app

ENV DEVKITPRO=/opt/devkitpro
ENV DEVKITARM=/opt/devkitpro/devkitARM
ENV PATH=/opt/devkitpro/devkitARM/bin:/opt/devkitpro/tools/bin:/opt/devkitpro/pacman/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PORT=10000

RUN dkp-pacman -Sy --noconfirm \
    nds-dev \
    general-tools \
    dstools \
    ndstool \
    && dkp-pacman -Scc --noconfirm

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt

RUN python3 -m pip install \
    --no-cache-dir \
    --break-system-packages \
    -r /tmp/requirements.txt

COPY . /app

EXPOSE 10000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 1 --timeout 360 app:app"]
