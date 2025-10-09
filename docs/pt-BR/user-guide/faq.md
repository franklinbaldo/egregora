# FAQ

## O ZIP precisa seguir algum padrão?

Sim.
Use o formato `Grupo-NNNN-AAAA-MM-DD.zip`.
Evita colisões e garante que o parser encontre a data correta.
Se o arquivo veio com outro nome, renomeie antes de colocar em
`data/whatsapp_zips/`.

## Posso incluir mídia no export?

Recomendamos exportar **sem mídia**.
O pipeline já referencia anexos por nome; incluir arquivos grandes aumenta o
tempo de processamento e o tamanho do repositório.

## O comando `uv run egregora` falhou com erro de rede. E agora?

Rode novamente com `--disable-enrichment` para gerar os posts base e publique
assim mesmo.
Depois repita o processamento com a flag padrão para complementar com links e
contexto.

## Como limpo dados antigos?

Apague a pasta `data/processed/` (se existir) e a subpasta correspondente em
`cache/`.
O pipeline reconstrói tudo automaticamente na próxima execução.

## Qual o limite de dias por execução?

O `--days 1` é ideal para diários.
Para reconstruir históricos, use `--days 7` ou `--since YYYY-MM-DD`.
Execuções muito longas podem atingir limites da API do Gemini;
monitore os logs e prefira rodadas menores.

## Onde reporto bugs ou solicito features?

Abra uma issue com o template “Bug report” ou “Feature request”.
Inclua o trecho do log com erro, versão do `egregora` (`uv pip show egregora`)
e sistema operacional.
