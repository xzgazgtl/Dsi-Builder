FROM devkitpro/devkitarm:latest

WORKDIR /app

ENV DEVKITPRO=/opt/devkitpro
ENV DEVKITARM=/opt/devkitpro/devkitARM

ENV PATH=/opt/devkitpro/devkitARM/bin:/opt/devkitpro/tools/bin:/opt/devkitpro/pacman/bin:/opt/devkitpro/portlibs/nds/bin:/usr/local/bin:/usr/bin:/bin

ENV PYTHONUNBUFFERED=1
ENV PORT=10000

# ============================================================
# Nintendo DS - libnds + Calico + ferramentas
# ============================================================

RUN dkp-pacman -Sy --noconfirm \
        nds-dev \
        ndstool \
    && dkp-pacman -Scc --noconfirm

# ============================================================
# Verificação das bibliotecas do Nintendo DS
# ============================================================

RUN echo "=== VERIFICANDO LIBNDS ===" \
    && ls -la /opt/devkitpro/libnds/include/ \
    && ls -la /opt/devkitpro/libnds/lib/ \
    && test -f /opt/devkitpro/libnds/lib/libnds9.a \
    && echo "LIBNDS9 ENCONTRADO!"

RUN echo "=== PROCURANDO CALICO ===" \
    && find /opt/devkitpro -name calico.h -print \
    && echo "CALICO.H ENCONTRADO!"

# ============================================================
# Python e pip
# ============================================================

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt

RUN python3 -m pip install \
    --no-cache-dir \
    --break-system-packages \
    -r /tmp/requirements.txt

# ============================================================
# Código do Builder
# ============================================================

COPY . /app

# ============================================================
# Verificação final
# ============================================================

RUN echo "=== VERIFICANDO FERRAMENTAS ===" \
    && which arm-none-eabi-gcc \
    && arm-none-eabi-gcc --version \
    && which make \
    && make --version \
    && which ndstool \
    && echo "=== BUILDER PRONTO ==="

EXPOSE 10000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 1 --timeout 360 app:app"]
