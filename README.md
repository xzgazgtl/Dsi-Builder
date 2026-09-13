# Button Rush DSi Builder V3.2

Versão preparada para upload pelo GitHub Mobile: **todos os arquivos ficam na raiz**. Não existem pastas `templates/` ou `static/`.

## Estrutura

- `app.py` — servidor Flask e interface web inteira
- `Dockerfile` — ambiente devkitARM + nds-dev
- `requirements.txt` — dependências Python
- `render.yaml` — configuração do Render

## Fluxo

1. Publique estes arquivos na raiz de um repositório GitHub.
2. No Render, crie um Web Service usando esse repositório.
3. Escolha Docker como runtime (o `render.yaml` já indica isso).
4. Abra a URL pública.
5. Envie um ZIP contendo um projeto Nintendo DS/DSi em C com `Makefile`.
6. O Builder executa `make` e procura o `.nds` gerado.

O ambiente de compilação fica dentro do container. O celular não precisa ter devkitARM instalado.

## Importante

Este Builder **não converte HTML/CSS/JS diretamente para NDS**. Ele compila um projeto C que já foi preparado para Nintendo DS/DSi.
