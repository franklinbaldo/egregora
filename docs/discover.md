# 🔍 Autodescoberta de Identificadores Anônimos

Cada pessoa pode descobrir seu próprio identificador a partir do telefone ou apelido usado
nas conversas, sem consultar nenhum arquivo sensível. O identificador é derivado
com UUIDv5 determinístico, portanto o mesmo input sempre gera o mesmo resultado.

## Como usar

```bash
uv run egregora discover "+55 11 91234-5678"
```

Saída típica:

```
📛 Autodescoberta de identificador anônimo
• Entrada original: +55 11 91234-5678
• Tipo detectado: phone
• Forma normalizada: +5511912345678
• Identificadores disponíveis:
  → human: User-1A2B
  · short: 1a2b3c4d
  · full: 1a2b3c4d-e5f6-7890-ab12-cdef34567890
• Formato preferido (human): User-1A2B
```

### Somente o identificador

Use `--quiet` para imprimir apenas o identificador em um formato específico:

```bash
uv run egregora discover "+55 11 91234-5678" --format short --quiet
```

Também é possível descobrir identificadores a partir de apelidos:

```bash
uv run egregora discover "João Silva"
```

O sistema detecta automaticamente se a entrada é um telefone ou um apelido e aplica a
normalização apropriada.

## Segurança

- Nenhum mapeamento é salvo em disco ou no repositório.
- Todo o cálculo é feito localmente, evitando vazamentos de dados pessoais.
- Como o algoritmo é determinístico, qualquer pessoa pode repetir o processo e obter o mesmo resultado.
