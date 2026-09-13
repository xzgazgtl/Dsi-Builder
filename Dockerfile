FROM devkitpro/devkitarm:latest

WORKDIR /app

ENV DEVKITPRO=/opt/devkitpro
ENV DEVKITARM=/opt/devkitpro/devkitARM

ENV PATH=/opt/devkitpro/devkitARM/bin:/opt/devkitpro/tools/bin:/opt/devkitpro/pacman/bin:/opt/devkitpro/portlibs/nds/bin:/usr/local/bin:/usr/bin:/bin

ENV PYTHONUNBUFFERED=1
ENV PORT=10000

# Instala explicitamente as bibliotecas e ferramentas do Nintendo DS
RUN dkp-pacman -Sy --noconfirm \
        libnds \
        ndstool \
    && dkp-pacman -Scc --noconfirm

# Confirma que a biblioteca necessária para -lnds9 realmente existe
RUN echo "=== VERIFICANDO LIBNDS ===" \
    && ls -la /opt/devkitpro/libnds/lib/ \
    && test -f /opt/devkitpro/libnds/lib/libnds9.a \
    && echo "=== LIBNDS9 ENCONTRADO! ==="

# Python e pip
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt

RUN python3 -m pip install \
    --no-cache-dir \
    --break-system-packages \
    -r /tmp/requirements.txt

COPY . /app

# Verificação final das ferramentas
RUN echo "=== VERIFICANDO FERRAMENTAS ===" \
    && which arm-none-eabi-gcc \
    && arm-none-eabi-gcc --version \
    && which make \
    && make --version \
    && (which ndstool || true) \
    && (ndstool --version || true) \
    && echo "=== BUILDER PRONTO ==="

EXPOSE 10000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 1 --timeout 360 app:app"]
