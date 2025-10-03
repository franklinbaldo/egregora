# WhatsApp Integration Testing Plan for Egregora

## Overview

This document outlines the comprehensive testing strategy for integrating WhatsApp conversation exports with egregora's pipeline. The testing framework validates all components using real WhatsApp data (`Conversa do WhatsApp com Teste.zip`).

## Test Structure

### Test Framework Components

```
tests/
├── test_framework/           # Shared testing utilities
│   ├── conftest.py          # Pytest fixtures and configuration
│   ├── helpers.py           # Helper functions and test data generators
│   └── __init__.py
├── test_core_pipeline.py    # Core pipeline functionality tests
├── test_enrichment_simple.py # URL extraction and regex pattern tests
├── test_rag_integration.py  # RAG system component tests
├── test_newsletter_simple.py # Newsletter generation tests
├── test_whatsapp_integration.py # Original WhatsApp format tests
└── data/                    # Test data
    ├── Conversa do WhatsApp com Teste.zip
    ├── Conversa do WhatsApp com Teste.txt
    └── IMG-20251002-WA0004.jpg
```

## Test Categories

### 1. Core Pipeline Tests (`test_core_pipeline.py`)

**Purpose**: Validate fundamental pipeline operations with WhatsApp data

**Key Tests**:
- ✅ **Zip Processing**: Extract and read WhatsApp zip files
- ✅ **Date Recognition**: Parse dates from file names (YYYY-MM-DD format)
- ✅ **Anonymization**: Convert "Franklin" → "Member-E9F3" format
- ✅ **Message Type Preservation**: Maintain emojis, URLs, attachments
- ✅ **Multi-day Processing**: Handle multiple conversation days
- ✅ **Anonymization Consistency**: Same person gets same anonymized name
- ✅ **Edge Cases**: Handle special characters, long messages, empty content

**WhatsApp-Specific Validations**:
- Date format: `DD/MM/YYYY HH:MM - Author: Message`
- Special characters: Emojis (🐱), attachments (arquivo anexado)
- URLs: YouTube links with parameters
- System messages: Group creation, member changes

### 2. Enrichment Tests (`test_enrichment_simple.py`)

**Purpose**: Validate URL extraction and content enrichment patterns

**Key Tests**:
- ✅ **URL Extraction**: Find YouTube and HTTP links in conversations
- ✅ **Message Parsing**: Parse WhatsApp HH:MM format (enrichment expects this)
- ✅ **Media Detection**: Identify `<mídia oculta>` placeholders
- ✅ **Pattern Recognition**: Handle complex conversations with multiple URLs
- ✅ **Edge Cases**: Process long content, special characters, multiple protocols

**Note**: Full enrichment tests require Gemini API integration. These tests focus on regex patterns and core functionality.

### 3. RAG System Tests (`test_rag_integration.py`)

**Purpose**: Validate RAG components for conversation indexing and search

**Key Tests**:
- ✅ **Query Generation**: Tokenization and keyword extraction from WhatsApp content
- ✅ **Date Detection**: Newsletter file date parsing (YYYY-MM-DD format)
- ✅ **Configuration**: RAG settings validation (similarity thresholds, context limits)
- ✅ **Search Patterns**: Query processing and result structure
- ✅ **Context Preparation**: Multi-day conversation context building
- ✅ **Text Hashing**: Content change detection for caching
- ✅ **Performance**: Large dataset handling and optimization

### 4. Newsletter Generation Tests (`test_newsletter_simple.py`)

**Purpose**: Validate newsletter creation from WhatsApp conversations

**Key Tests**:
- ✅ **Transcript Preparation**: Convert WhatsApp format with anonymization
- ✅ **Previous Context**: Load previous newsletters for continuity
- ✅ **Multi-day Processing**: Handle conversations across multiple days
- ✅ **File Management**: Date-based naming, directory structure
- ✅ **Content Validation**: Required sections, proper formatting
- ✅ **Configuration**: Anonymization settings, group names
- ✅ **Error Handling**: Missing files, invalid configurations

**Newsletter Structure Validation**:
- Required sections: Resumo Executivo, Tópicos Principais
- Date formatting: DD/MM/YYYY
- File naming: YYYY-MM-DD.md
- Content preservation with anonymization

## WhatsApp Data Integration

### Test Data Structure

The test suite uses real WhatsApp export data:

```
Conversa do WhatsApp com Teste.zip
├── Conversa do WhatsApp com Teste.txt (conversation text)
└── IMG-20251002-WA0004.jpg (example attachment)
```

**Conversation Content**:
```
03/10/2025 09:45 - Franklin: Teste de grupo
03/10/2025 09:45 - Franklin: 🐱
03/10/2025 09:46 - Franklin: ‎IMG-20251002-WA0004.jpg (arquivo anexado)
03/10/2025 09:46 - Franklin: https://youtu.be/Nkhp-mb6FRc?si=HFXbG4Kke-1Ec1XT
03/10/2025 09:46 - Franklin: Legal esse vídeo
```

### Processing Pipeline Validation

1. **Zip Extraction**: `read_zip_texts()` processes zip files
2. **Format Recognition**: New regex pattern handles DD/MM/YYYY format
3. **Anonymization**: Authors converted to Member-XXXX format
4. **Content Preservation**: Messages, emojis, URLs, attachments maintained
5. **File Output**: Processed content ready for newsletter generation

## Test Execution

### Running Individual Test Suites

```bash
# Core pipeline functionality
python3 tests/test_core_pipeline.py

# URL extraction and patterns
python3 tests/test_enrichment_simple.py

# RAG system components
python3 tests/test_rag_integration.py

# Newsletter generation
python3 tests/test_newsletter_simple.py

# Original WhatsApp integration
python3 tests/test_whatsapp_integration.py
```

### Running All Tests

```bash
# Run all tests in sequence
for test in tests/test_*.py; do
    echo "Running $test..."
    python3 "$test"
done
```

### Test Environment Setup

Tests are designed to be self-contained:
- Use temporary directories for isolation
- Mock external dependencies (Gemini API, web requests)
- Include real WhatsApp data for authentic testing
- Reset state between test functions

## Success Criteria

### ✅ All Tests Passing

Current status: **ALL TESTS PASSING** ✨

- **Core Pipeline**: 8/8 tests passing
- **Enrichment**: 7/7 tests passing  
- **RAG Integration**: 9/9 tests passing
- **Newsletter Generation**: 9/9 tests passing
- **WhatsApp Integration**: 3/3 tests passing

### Functional Validation

1. **WhatsApp Format Support**: DD/MM/YYYY HH:MM format recognized
2. **Anonymization Working**: Franklin → Member-E9F3 conversion
3. **Content Preservation**: Emojis, URLs, attachments maintained
4. **End-to-End Processing**: Zip → Anonymized Content → Newsletter structure

### MCP Server Tests (`test_mcp_server.py`)

**Status**: ⚠️ Pending — MCP server disponível, cobertura automatizada em andamento.

**Objetivo**: Verificar se o servidor MCP expõe o RAG de forma consistente para Claude e outras ferramentas compatíveis.

**Escopo planejado:**

- Inicialização e carregamento preguiçoso do índice (`NewsletterRAG.load_index`).
- Registro das tools MCP (`search_newsletters`, `list_newsletters`, `get_newsletter`).
- Processamento de queries com embeddings do Gemini (`--use-gemini-embeddings`) e fallback para TF-IDF.
- Formatação de respostas segundo o protocolo MCP (JSON-RPC + content parts).
- Tratamento de erros: timeouts, newsletters ausentes, índice sem cache.

**Prioridade**: Alta — requisito para liberar o MCP em produção com suporte oficial.

### Performance Benchmarks

- **URL Extraction**: < 1 second for 100 URLs
- **Anonymization**: Processes multi-day conversations efficiently
- **Memory Usage**: Handles large conversation datasets
- **File Processing**: Supports various zip file structures

## Future Enhancements

### Planned Test Additions

1. **MCP Server Testing**: Integration tests for MCP server functionality
2. **End-to-End Workflows**: Complete pipeline tests with real API calls
3. **Performance Benchmarking**: Detailed performance and memory usage tests
4. **Load Testing**: Large-scale conversation processing validation

### Integration Testing

1. **API Integration**: Tests with real Gemini API (optional)
2. **File System**: Tests with various file structures and permissions
3. **Error Recovery**: Comprehensive error handling validation
4. **Configuration**: Advanced configuration scenario testing

## Conclusion

The WhatsApp integration testing framework provides comprehensive coverage of egregora's functionality with real conversation data. All core components are validated, ensuring reliable processing of WhatsApp exports with proper anonymization and content preservation.

The test suite serves as both validation and documentation, demonstrating how egregora processes WhatsApp conversations into newsletter-ready content while maintaining privacy and data integrity.