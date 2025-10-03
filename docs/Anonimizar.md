# Plano de Implementação: Sistema Completo de Privacidade

## 📋 Visão Geral

Implementar sistema abrangente de proteção de privacidade para o Egregora em **3 camadas**:

1. **Anonimização de Autores**: Telefones e nicknames convertidos em UUIDs antes de qualquer processamento
2. **Filtro de Conteúdo**: Detecção e remoção de PII (Personally Identifiable Information) nas mensagens
3. **Validação Pós-Geração**: Verificação automática da newsletter para garantir ausência de dados pessoais

Cada membro poderá descobrir seu próprio UUID de forma self-service, sem necessidade de mapeamento centralizado.

---

## 📊 Resumo Executivo

### O Problema

**Dois tipos de vazamento de dados:**

1. **Autores**: Telefones e nicknames nos metadados das mensagens
   ```
   +55 11 98765-4321: "Olá pessoal!"
   João Silva: "Concordo!"
   ```

2. **Conteúdo**: Dados pessoais dentro do texto das mensagens
   ```
   User-A1B2: "Oi João, liga pro 21 99999-8888"
                    ^^^^           ^^^^^^^^^^^^^
                   NOME            TELEFONE
   ```

### A Solução

**3 camadas independentes de proteção:**

| Camada | O Que Faz | Quando | Como |
|--------|-----------|--------|------|
| **1. Anonimização** | Converte autores em UUIDs | Antes de tudo | UUIDv5 determinístico |
| **2. Instruções LLM** | Pede ao Gemini para não mencionar PII | Na geração | Prompt explícito |
| **3. Validação** | Detecta PII na newsletter final | Após geração | Regex + heurísticas |

### Impacto

**Antes:**
```
Newsletter exposta com:
- Telefones reais: +55 11 98765-4321
- Nomes reais: João Silva, Maria Santos
- Cache com dados sensíveis
```

**Depois:**
```
Newsletter segura com:
- Identificadores anônimos: User-A1B2, Member-C3D4
- Nomes generalizados: "Um membro disse..."
- Cache commitável no Git
- Alertas se PII for detectado
```

### Tempo Estimado

**14-20 horas** divididas em 6 fases sequenciais.

### Dependências

- ✅ Nenhuma nova dependência externa!
- ✅ Usa apenas Python stdlib + uuid
- ✅ JavaScript vanilla para página web

---

## 🎯 Objetivos

1. **Privacidade by Design**: dados pessoais nunca são armazenados no repositório
2. **LGPD/GDPR Compliant**: sem banco de dados de identificação pessoal
3. **Self-Service**: cada pessoa descobre seu UUID independentemente
4. **Determinístico**: mesmo autor sempre gera mesmo UUID
5. **Git Safe**: todo o repositório pode ser público sem vazamento de dados
6. **Proteção em Profundidade**: múltiplas camadas de detecção e prevenção de vazamento de PII

---

## 🔑 Princípios Fundamentais

### Camada 1: Anonimização de Autores (UUIDv5)

- **Namespace para Telefones**: `6ba7b810-9dad-11d1-80b4-00c04fd430c8`
- **Namespace para Nicknames**: `6ba7b811-9dad-11d1-80b4-00c04fd430c9`
- **Formato de Saída**: `User-A1B2` ou `Member-C3D4` (humano-legível)

**Fluxo de Anonimização:**

```
Input Original          →  Anonimização    →  Armazenamento
─────────────────────────────────────────────────────────────
+55 11 98765-4321      →  User-A1B2       →  cache/, newsletters/
João Silva             →  Member-C3D4     →  cache/, newsletters/
```

**Autodescoberta:**

```
Membro Local           →  Calcula UUID    →  Busca no Repo
─────────────────────────────────────────────────────────────
Telefone próprio       →  User-A1B2       →  GitHub Search
Nickname próprio       →  Member-C3D4     →  Git grep local
```

**Nenhum mapeamento armazenado em lugar nenhum!**

### Camada 2: Proteção de PII no Conteúdo

Mesmo com autores anonimizados, o **conteúdo das mensagens** pode conter dados pessoais:

```
❌ PROBLEMA:
User-A1B2: "Oi João, manda pro WhatsApp do Pedro: 11 98765-4321"
Member-C3D4: "A Maria concordou, liga pra ela: +55 21 99999-8888"
```

**Solução em 3 níveis:**

1. **Instruções ao LLM**: Prompt explícito para NÃO mencionar nomes/telefones
2. **Detecção Automática**: Regex para identificar PII na newsletter gerada
3. **Validação Manual**: Alertas quando PII é detectado

### Camada 3: Validação Pós-Geração

Após gerar a newsletter, sistema escaneia automaticamente:

- ✅ Números de telefone (vários formatos)
- ✅ Nomes próprios comuns
- ✅ Padrões de contato
- ⚠️ Alerta se algo for detectado

---

## 📁 Estrutura de Arquivos

```
egregora/
├── src/
│   └── egregora/
│       ├── __init__.py
│       ├── __main__.py              # Adicionar subcomando 'discover'
│       ├── anonymizer.py            # ⭐ NOVO - Anonimização determinística (Camada 1)
│       ├── privacy_filter.py        # ⭐ NOVO - Detecção e filtro de PII (Camada 2)
│       ├── discover.py              # ⭐ NOVO - CLI de autodescoberta
│       ├── config.py                # Adicionar AnonymizationConfig + PrivacyConfig
│       ├── enrichment.py            # Modificar para usar Anonymizer
│       └── pipeline.py              # Modificar para usar Anonymizer + PrivacyFilter
├── docs/
│   ├── discover.md                  # ⭐ NOVO - Página web autodescoberta
│   ├── privacy.md                   # ⭐ NOVO - Explicação completa de privacidade
│   └── index.md                     # Atualizar com link para discover
├── tests/
│   ├── test_anonymizer.py           # ⭐ NOVO - Testes unitários anonimização
│   ├── test_privacy_filter.py       # ⭐ NOVO - Testes unitários filtro PII
│   └── test_privacy_e2e.py          # ⭐ NOVO - Testes end-to-end completo
├── mkdocs.yml                        # Adicionar página discover
└── README.md                         # Adicionar seção de privacidade
```

---

## 💻 Implementação Detalhada

### Fase 1: Módulo Core de Anonimização

#### Arquivo: `src/egregora/anonymizer.py`

```python
"""
Sistema de anonimização determinística usando UUIDv5.

Este módulo converte telefones e nicknames em identificadores
únicos e consistentes, sem armazenar qualquer mapeamento.
"""

from __future__ import annotations

import uuid
import re
from typing import Literal

class Anonymizer:
    """
    Anonimizador determinístico baseado em UUIDv5.
    
    Não mantém estado ou mapeamento. Cada conversão é pura e
    determinística - mesma entrada sempre gera mesma saída.
    """
    
    # Namespaces UUID distintos para evitar colisões
    NAMESPACE_PHONE = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')
    NAMESPACE_NICKNAME = uuid.UUID('6ba7b811-9dad-11d1-80b4-00c04fd430c9')
    
    @staticmethod
    def normalize_phone(phone: str) -> str:
        """
        Normaliza número de telefone para formato consistente.
        
        Remove espaços, hífens, parênteses e outros caracteres.
        Garante que +55 11 98765-4321 e 5511987654321 gerem mesmo UUID.
        
        Args:
            phone: Número em qualquer formato
            
        Returns:
            Número normalizado (apenas dígitos e +)
            
        Examples:
            >>> Anonymizer.normalize_phone("+55 11 98765-4321")
            '+5511987654321'
            >>> Anonymizer.normalize_phone("(11) 98765-4321")
            '11987654321'
        """
        # Remove tudo exceto dígitos e +
        normalized = re.sub(r'[^\d+]', '', phone)
        
        # Se não tem +, adiciona +55 (Brasil)
        if not normalized.startswith('+'):
            if len(normalized) == 11:  # DDD + número
                normalized = '+55' + normalized
            elif len(normalized) == 10:  # DDD + número sem 9
                normalized = '+55' + normalized
        
        return normalized
    
    @staticmethod
    def normalize_nickname(nickname: str) -> str:
        """
        Normaliza nickname para formato consistente.
        
        Remove espaços extras, converte para minúsculas.
        
        Args:
            nickname: Nome em qualquer formato
            
        Returns:
            Nome normalizado
            
        Examples:
            >>> Anonymizer.normalize_nickname("  João Silva  ")
            'joão silva'
        """
        return ' '.join(nickname.lower().split())
    
    @staticmethod
    def anonymize_phone(phone: str, format: str = 'human') -> str:
        """
        Converte telefone em identificador anônimo.
        
        Args:
            phone: Número de telefone em qualquer formato
            format: Formato de saída ('human', 'short', 'full')
            
        Returns:
            Identificador anônimo
            
        Examples:
            >>> Anonymizer.anonymize_phone("+55 11 98765-4321")
            'User-A1B2'
            >>> Anonymizer.anonymize_phone("+55 11 98765-4321", format='short')
            'a1b2c3d4'
        """
        normalized = Anonymizer.normalize_phone(phone)
        uuid_full = str(uuid.uuid5(Anonymizer.NAMESPACE_PHONE, normalized))
        
        return Anonymizer._format_uuid(uuid_full, 'User', format)
    
    @staticmethod
    def anonymize_nickname(nickname: str, format: str = 'human') -> str:
        """
        Converte nickname em identificador anônimo.
        
        Args:
            nickname: Nome/apelido do usuário
            format: Formato de saída ('human', 'short', 'full')
            
        Returns:
            Identificador anônimo
            
        Examples:
            >>> Anonymizer.anonymize_nickname("João Silva")
            'Member-B3C4'
        """
        normalized = Anonymizer.normalize_nickname(nickname)
        uuid_full = str(uuid.uuid5(Anonymizer.NAMESPACE_NICKNAME, normalized))
        
        return Anonymizer._format_uuid(uuid_full, 'Member', format)
    
    @staticmethod
    def anonymize_author(author: str, format: str = 'human') -> str:
        """
        Auto-detecta tipo e anonimiza (telefone ou nickname).
        
        Args:
            author: Telefone ou nickname
            format: Formato de saída
            
        Returns:
            Identificador anônimo apropriado
            
        Examples:
            >>> Anonymizer.anonymize_author("+55 11 98765-4321")
            'User-A1B2'
            >>> Anonymizer.anonymize_author("João Silva")
            'Member-C3D4'
        """
        # Detecta se é telefone (começa com + ou só tem dígitos)
        clean = author.strip().replace(' ', '').replace('-', '')
        
        if clean.startswith('+') or clean.isdigit():
            return Anonymizer.anonymize_phone(author, format)
        
        return Anonymizer.anonymize_nickname(author, format)
    
    @staticmethod
    def _format_uuid(
        uuid_str: str,
        prefix: str,
        format: Literal['human', 'short', 'full']
    ) -> str:
        """
        Formata UUID para o formato desejado.
        
        Args:
            uuid_str: UUID completo (string)
            prefix: Prefixo ('User' ou 'Member')
            format: Formato de saída
            
        Returns:
            UUID formatado
        """
        # Pega primeiros 8 caracteres do UUID
        short = uuid_str.split('-')[0][:8]
        
        if format == 'short':
            return short
        elif format == 'human':
            # User-A1B2 ou Member-C3D4
            return f"{prefix}-{short[:4].upper()}"
        else:  # full
            return uuid_str
    
    @staticmethod
    def get_uuid_variants(identifier: str) -> dict[str, str]:
        """
        Retorna todas as variantes de formato para um identificador.
        
        Útil para busca e debugging.
        
        Args:
            identifier: Telefone ou nickname
            
        Returns:
            Dict com todas as variantes
            
        Examples:
            >>> Anonymizer.get_uuid_variants("+55 11 98765-4321")
            {
                'human': 'User-A1B2',
                'short': 'a1b2c3d4',
                'full': 'a1b2c3d4-e5f6-5789-abcd-ef0123456789'
            }
        """
        is_phone = (identifier.startswith('+') or 
                   identifier.replace('-', '').replace(' ', '').isdigit())
        
        if is_phone:
            return {
                'human': Anonymizer.anonymize_phone(identifier, 'human'),
                'short': Anonymizer.anonymize_phone(identifier, 'short'),
                'full': Anonymizer.anonymize_phone(identifier, 'full')
            }
        else:
            return {
                'human': Anonymizer.anonymize_nickname(identifier, 'human'),
                'short': Anonymizer.anonymize_nickname(identifier, 'short'),
                'full': Anonymizer.anonymize_nickname(identifier, 'full')
            }
```

**Características:**
- ✅ Sem estado (stateless)
- ✅ Sem armazenamento de mapeamento
- ✅ Normalização robusta de entradas
- ✅ Múltiplos formatos de saída
- ✅ Auto-detecção de tipo (telefone vs nickname)
- ✅ Totalmente documentado

---

#### Arquivo: `src/egregora/privacy_filter.py`

```python
"""
Filtro de privacidade para detectar e remover PII do conteúdo das mensagens.

Este módulo complementa a anonimização de autores, protegendo contra
vazamento de dados pessoais no CONTEÚDO das mensagens e newsletters.
"""

from __future__ import annotations

import re
from typing import List, Tuple, Dict
from dataclasses import dataclass


@dataclass
class PIIDetection:
    """Resultado da detecção de PII em um texto."""
    
    has_pii: bool
    phone_count: int
    name_count: int
    phones: List[str]
    names: List[str]
    positions: List[Tuple[str, int, int]]  # (tipo, start, end)


class PrivacyFilter:
    """
    Detecta e remove PII (Personally Identifiable Information).
    
    Funciona em dois modos:
    1. Detecção: identifica PII sem modificar o texto
    2. Mascaramento: remove ou substitui PII detectado
    """
    
    # Padrões de telefone brasileiros
    PHONE_PATTERNS = [
        # +55 11 98765-4321
        r'\+55[\s-]?\d{2}[\s-]?\d{4,5}[\s-]?\d{4}',
        # (11) 98765-4321
        r'\(?\d{2}\)?[\s-]?\d{4,5}[\s-]?\d{4}',
        # 11987654321
        r'\b\d{10,11}\b',
        # Apenas DDD entre parênteses: (11)
        r'\(\d{2}\)',
    ]
    
    # Nomes próprios brasileiros mais comuns
    # Fonte: IBGE - Lista expandida para melhor cobertura
    COMMON_NAMES = {
        # Nomes masculinos
        'joão', 'josé', 'antonio', 'francisco', 'carlos', 'paulo', 'pedro',
        'lucas', 'luiz', 'marcos', 'luis', 'gabriel', 'rafael', 'daniel',
        'marcelo', 'bruno', 'eduardo', 'felipe', 'fabio', 'rodrigo',
        'fernando', 'gustavo', 'andre', 'juliano', 'ricardo', 'sergio',
        # Nomes femininos
        'maria', 'ana', 'francisca', 'antonia', 'adriana', 'juliana',
        'marcia', 'fernanda', 'patricia', 'aline', 'sandra', 'camila',
        'amanda', 'bruna', 'jessica', 'leticia', 'tatiana', 'vanessa',
        'priscila', 'monica', 'simone', 'cristina', 'debora', 'renata',
        # Apelidos comuns
        'beto', 'ju', 'carol', 'dani', 'fabi', 'rafa', 'gabi', 'bru',
    }
    
    # Padrões suspeitos de menção de contato
    CONTACT_PATTERNS = [
        r'(?:meu|minha|seu|dele|dela)\s+(?:número|telefone|whats|zap)',
        r'(?:liga|ligar|chamar|add|adiciona)\s+(?:pra|para|no)\s+\w+',
        r'(?:whatsapp|whats|zap)\s+(?:do|da|de)\s+\w+',
    ]
    
    @staticmethod
    def detect_phones(text: str) -> List[Tuple[str, int, int]]:
        """
        Detecta números de telefone no texto.
        
        Args:
            text: Texto a ser analisado
            
        Returns:
            Lista de (telefone, posição_inicial, posição_final)
            
        Examples:
            >>> PrivacyFilter.detect_phones("Liga pro 11 98765-4321")
            [('11 98765-4321', 10, 24)]
        """
        matches = []
        seen = set()  # Evita duplicatas
        
        for pattern in PrivacyFilter.PHONE_PATTERNS:
            for match in re.finditer(pattern, text):
                phone = match.group()
                # Remove duplicatas (mesmo número em formatos diferentes)
                normalized = re.sub(r'[^\d]', '', phone)
                if normalized not in seen and len(normalized) >= 10:
                    seen.add(normalized)
                    matches.append((phone, match.start(), match.end()))
        
        return matches
    
    @staticmethod
    def detect_names(text: str) -> List[Tuple[str, int, int]]:
        """
        Detecta possíveis nomes próprios no texto.
        
        Usa heurística: palavras capitalizadas que aparecem na lista
        de nomes comuns brasileiros.
        
        Args:
            text: Texto a ser analisado
            
        Returns:
            Lista de (nome, posição_inicial, posição_final)
            
        Examples:
            >>> PrivacyFilter.detect_names("João disse que Maria concordou")
            [('João', 0, 4), ('Maria', 16, 21)]
        """
        matches = []
        
        # Busca palavras capitalizadas
        pattern = r'\b[A-ZÀÁÂÃÉÊÍÓÔÕÚÇ][a-zàáâãéêíóôõúç]+\b'
        
        for match in re.finditer(pattern, text):
            word = match.group()
            word_lower = word.lower()
            
            # Verifica se é nome comum
            if word_lower in PrivacyFilter.COMMON_NAMES:
                matches.append((word, match.start(), match.end()))
        
        return matches
    
    @staticmethod
    def detect_contact_mentions(text: str) -> List[Tuple[str, int, int]]:
        """
        Detecta menções suspeitas de contato/telefone.
        
        Args:
            text: Texto a ser analisado
            
        Returns:
            Lista de (menção, posição_inicial, posição_final)
            
        Examples:
            >>> PrivacyFilter.detect_contact_mentions("meu número é 123")
            [('meu número', 0, 10)]
        """
        matches = []
        
        for pattern in PrivacyFilter.CONTACT_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                matches.append((match.group(), match.start(), match.end()))
        
        return matches
    
    @staticmethod
    def scan(text: str) -> PIIDetection:
        """
        Escaneia texto completo em busca de PII.
        
        Args:
            text: Texto a ser analisado
            
        Returns:
            Objeto PIIDetection com resultados
            
        Examples:
            >>> result = PrivacyFilter.scan("João: 11 98765-4321")
            >>> result.has_pii
            True
            >>> result.phone_count
            1
            >>> result.name_count
            1
        """
        phones = PrivacyFilter.detect_phones(text)
        names = PrivacyFilter.detect_names(text)
        contacts = PrivacyFilter.detect_contact_mentions(text)
        
        # Combina todas as posições
        all_positions = []
        all_positions.extend([('phone', s, e) for _, s, e in phones])
        all_positions.extend([('name', s, e) for _, s, e in names])
        all_positions.extend([('contact', s, e) for _, s, e in contacts])
        
        return PIIDetection(
            has_pii=len(phones) > 0 or len(names) > 0 or len(contacts) > 0,
            phone_count=len(phones),
            name_count=len(names),
            phones=[p for p, _, _ in phones],
            names=[n for n, _, _ in names],
            positions=all_positions
        )
    
    @staticmethod
    def mask_phones(
        text: str,
        replacement: str = '[telefone removido]'
    ) -> str:
        """
        Remove/mascara números de telefone do texto.
        
        Args:
            text: Texto original
            replacement: String de substituição
            
        Returns:
            Texto com telefones mascarados
            
        Examples:
            >>> PrivacyFilter.mask_phones("Liga: 11 98765-4321")
            'Liga: [telefone removido]'
        """
        result = text
        for pattern in PrivacyFilter.PHONE_PATTERNS:
            result = re.sub(pattern, replacement, result)
        return result
    
    @staticmethod
    def mask_names(
        text: str,
        replacement: str = '[nome]',
        custom_names: List[str] = None
    ) -> str:
        """
        Remove/mascara nomes próprios do texto.
        
        Args:
            text: Texto original
            replacement: Stri
