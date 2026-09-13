# Button Rush DSi Builder - compilador NDS
# O devkitARM fica dentro do container; não precisa ser instalado no servidor.
FROM devkitpro/devkitarm:latest

WORKDIR /app

# Ferramentas do DS + Python para o Builder web.
RUN pacman -Sy --noconfirm nds-dev python python-pip \
    && pacman -Scc --noconfirm

COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --break-system-packages -r /tmp/requirements.txt

COPY . /app

ENV DEVKITPRO=/opt/devkitpro
ENV DEVKITARM=/opt/devkitpro/devkitARM
ENV PYTHONUNBUFFERED=1
ENV PORT=10000

EXPOSE 10000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 1 --timeout 360 app:app"]
