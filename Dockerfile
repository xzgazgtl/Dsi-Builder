FROM devkitpro/devkitarm:latest

WORKDIR /app

ENV DEVKITPRO=/opt/devkitpro
ENV DEVKITARM=/opt/devkitpro/devkitARM
ENV PATH=/opt/devkitpro/devkitARM/bin:/opt/devkitpro/tools/bin:/opt/devkitpro/pacman/bin:/opt/devkitpro/portlibs/nds/bin:/usr/local/bin:/usr/bin:/bin

ENV PYTHONUNBUFFERED=1
ENV PORT=10000

# Instala as ferramentas e bibliotecas necessárias para Nintendo DS
RUN dkp-pacman -Sy --noconfirm nds-dev \
    && dkp-pacman -S --noconfirm ndstool \
    && echo "=== VERIFICANDO LIBNDS ===" \
    && find /opt/devkitpro -name "libnds9.a" -print \
    && test -f /opt/devkitpro/libnds/lib/libnds9.a \
    && echo "libnds9.a OK" \
    && dkp-pacman -Scc --noconfirm

# Garante que o ndstool esteja disponível no PATH
RUN find /opt/devkitpro -type f -name ndstool \
    -exec ln -sf {} /usr/local/bin/ndstool \; || true

# Python
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt

RUN python3 -m pip install \
    --no-cache-dir \
    --break-system-packages \
    -r /tmp/requirements.txt

COPY . /app

# Verificação final do ambiente
RUN echo "=== VERIFICANDO FERRAMENTAS ===" \
    && which arm-none-eabi-gcc \
    && arm-none-eabi-gcc --version \
    && which make \
    && make --version \
    && which ndstool \
    && ndstool --version || true

RUN echo "=== VERIFICANDO LIBNDS ===" \
    && test -f /opt/devkitpro/libnds/lib/libnds9.a \
    && echo "libnds9.a encontrado!"

EXPOSE 10000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 1 --timeout 360 app:app"]
