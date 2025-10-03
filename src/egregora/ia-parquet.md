# Plano: Embeddings em Parquet + Internet Archive

## 📋 Visão Geral

Sistema completo para **persistir embeddings** de newsletters em formato **Parquet** e fazer **backup automático** no **Internet Archive**, permitindo:

1. **Backup durável** - Archive.org preserva dados permanentemente
2. **Compartilhamento aberto** - Qualquer pessoa pode baixar e usar
3. **Bootstrap rápido** - Novos usuários não precisam reprocessar tudo
4. **Versionamento** - Histórico completo de mudanças
5. **Open data** - Transparência e auditabilidade total

---

## 🎯 Objetivos

### Funcional
1. **Salvar embeddings em Parquet** - Formato eficiente e portável
2. **Upload automático para Archive.org** - Backup incremental
3. **Download de embeddings** - Bootstrap a partir do Archive
4. **Versionamento** - Rastrear mudanças ao longo do tempo
5. **Metadados completos** - Modelo usado, data, versão, etc

### Técnico
1. **Formato otimizado** - Parquet com compressão
2. **Uploads incrementais** - Apenas dados novos
3. **Particionamento** - Por ano/mês para downloads parciais
4. **Integração MCP** - Tools para upload/download
5. **CLI** - Comandos para gerenciar backups

---

## 🏗️ Arquitetura

### Fluxo Completo

```
┌─────────────────────────────────────────────────────────────┐
│ 1. GERAÇÃO DE EMBEDDINGS                                    │
│    Newsletters → Chunks → Embeddings (Gemini)               │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. CACHE LOCAL (Pickle + JSON)                             │
│    cache/rag/embeddings.pkl                                 │
│    cache/rag/metadata.json                                  │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. EXPORT PARA PARQUET                                      │
│    cache/rag/exports/2025-10.parquet                        │
│    cache/rag/exports/2025-09.parquet                        │
│    cache/rag/exports/manifest.json                          │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. UPLOAD PARA INTERNET ARCHIVE                            │
│    https://archive.org/details/egregora-newsletters-2025    │
│    - embeddings-2025-10.parquet                             │
│    - embeddings-2025-09.parquet                             │
│    - manifest.json                                          │
│    - README.md                                              │
└─────────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. DOWNLOAD E SYNC (OPCIONAL)                              │
│    Novo usuário baixa parquets → Reconstrói cache local    │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Estrutura de Arquivos

```
egregora/
├── cache/
│   └── rag/
│       ├── embeddings.pkl           # Cache local (uso diário)
│       ├── metadata.json            # Metadata local
│       ├── index.json               # Índice de newsletters
│       └── exports/                 # ⭐ NOVO - Exports Parquet
│           ├── manifest.json        # Metadados dos exports
│           ├── 2024-01.parquet
│           ├── 2024-02.parquet
│           ├── ...
│           ├── 2025-09.parquet
│           └── 2025-10.parquet
├── src/
│   └── egregora/
│       ├── rag/
│       │   ├── exporter.py          # ⭐ NOVO - Export para Parquet
│       │   └── archive_sync.py      # ⭐ NOVO - Sync com Archive.org
│       └── mcp_server/
│           └── server.py            # Atualizar: + tools de backup
└── scripts/
    ├── export_embeddings.py         # ⭐ NOVO - Script de export
    └── sync_to_archive.py           # ⭐ NOVO - Upload/download
```

---

## 💻 Implementação Detalhada

### Módulo 1: Export para Parquet

#### Arquivo: `src/egregora/rag/exporter.py`

```python
"""
Export de embeddings para formato Parquet.

Converte cache local (pickle) em arquivos Parquet
particionados por mês, otimizados para compartilhamento.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import date, datetime
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import numpy as np


class EmbeddingsExporter:
    """Exporta embeddings para formato Parquet."""
    
    def __init__(
        self,
        cache_dir: Path,
        exports_dir: Path | None = None,
    ):
        self.cache_dir = cache_dir
        self.exports_dir = exports_dir or (cache_dir / "exports")
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        
        self.manifest_path = self.exports_dir / "manifest.json"
    
    def export_all(
        self,
        partition_by: str = "month",  # 'month', 'year', 'quarter'
    ) -> Dict[str, Any]:
        """
        Exporta todos os embeddings para Parquet.
        
        Args:
            partition_by: Estratégia de particionamento
        
        Returns:
            Relatório do export
        """
        # 1. Carregar dados do cache
        embeddings = self._load_embeddings()
        metadata = self._load_metadata()
        
        if embeddings is None or not metadata:
            return {
                "success": False,
                "error": "Cache vazio ou não encontrado"
            }
        
        # 2. Converter para DataFrame
        df = self._build_dataframe(embeddings, metadata)
        
        # 3. Particionar por período
        partitions = self._partition_dataframe(df, partition_by)
        
        # 4. Salvar cada partição
        exported_files = []
        for partition_key, partition_df in partitions.items():
            file_path = self._export_partition(partition_key, partition_df)
            exported_files.append({
                "file": file_path.name,
                "partition": partition_key,
                "rows": len(partition_df),
                "size_mb": file_path.stat().st_size / 1024 / 1024,
            })
        
        # 5. Atualizar manifest
        manifest = self._update_manifest(exported_files)
        
        return {
            "success": True,
            "files_exported": len(exported_files),
            "total_rows": len(df),
            "manifest": manifest,
        }
    
    def export_incremental(
        self,
        since_date: date | None = None,
    ) -> Dict[str, Any]:
        """
        Exporta apenas dados novos desde a última exportação.
        
        Args:
            since_date: Data mínima (None = usar último export)
        
        Returns:
            Relatório do export incremental
        """
        # 1. Determinar data de corte
        if since_date is None:
            manifest = self._load_manifest()
            since_date = manifest.get("last_export_date")
            
            if since_date:
                since_date = date.fromisoformat(since_date)
        
        if since_date is None:
            # Primeira vez - export completo
            return self.export_all()
        
        # 2. Carregar apenas chunks novos
        embeddings = self._load_embeddings()
        metadata = self._load_metadata()
        
        # Filtrar por data
        new_chunks = [
            chunk for chunk in metadata['chunks']
            if date.fromisoformat(chunk['newsletter_date']) > since_date
        ]
        
        if not new_chunks:
            return {
                "success": True,
                "files_exported": 0,
                "message": "Nenhum dado novo desde último export"
            }
        
        # 3. Extrair embeddings correspondentes
        new_indices = [chunk['chunk_id'] for chunk in new_chunks]
        new_embeddings = embeddings[new_indices]
        
        # 4. Converter e exportar
        df = self._build_dataframe(new_embeddings, {'chunks': new_chunks})
        partitions = self._partition_dataframe(df, "month")
        
        exported_files = []
        for partition_key, partition_df in partitions.items():
            # Append ou criar novo arquivo
            file_path = self.exports_dir / f"{partition_key}.parquet"
            
            if file_path.exists():
                # Append ao arquivo existente
                existing_df = pd.read_parquet(file_path)
                combined_df = pd.concat([existing_df, partition_df])
                # Remover duplicatas (caso existam)
                combined_df = combined_df.drop_duplicates(subset=['chunk_id'])
                partition_df = combined_df
            
            file_path = self._export_partition(partition_key, partition_df)
            exported_files.append({
                "file": file_path.name,
                "partition": partition_key,
                "rows": len(partition_df),
                "size_mb": file_path.stat().st_size / 1024 / 1024,
            })
        
        # 5. Atualizar manifest
        manifest = self._update_manifest(exported_files)
        
        return {
            "success": True,
            "files_exported": len(exported_files),
            "new_rows": len(df),
            "manifest": manifest,
        }
    
    def _load_embeddings(self) -> np.ndarray | None:
        """Carrega embeddings do cache."""
        import pickle
        
        embeddings_path = self.cache_dir / "embeddings.pkl"
        
        if not embeddings_path.exists():
            return None
        
        with open(embeddings_path, 'rb') as f:
            data = pickle.load(f)
            return data['embeddings']
    
    def _load_metadata(self) -> Dict | None:
        """Carrega metadata do cache."""
        metadata_path = self.cache_dir / "metadata.json"
        
        if not metadata_path.exists():
            return None
        
        with open(metadata_path, 'r') as f:
            return json.load(f)
    
    def _build_dataframe(
        self,
        embeddings: np.ndarray,
        metadata: Dict,
    ) -> pd.DataFrame:
        """Converte embeddings + metadata em DataFrame."""
        
        chunks = metadata['chunks']
        
        # Construir dados tabulares
        data = []
        for i, chunk in enumerate(chunks):
            data.append({
                'chunk_id': chunk['chunk_id'],
                'newsletter_date': chunk['newsletter_date'],
                'newsletter_path': chunk['newsletter_path'],
                'section_title': chunk.get('section_title'),
                'text': chunk['text'],
                'char_count': chunk.get('char_count', len(chunk['text'])),
                'chunk_index': chunk.get('chunk_index_in_newsletter', 0),
                'embedding': embeddings[i].tolist(),  # Array como lista
            })
        
        return pd.DataFrame(data)
    
    def _partition_dataframe(
        self,
        df: pd.DataFrame,
        partition_by: str,
    ) -> Dict[str, pd.DataFrame]:
        """Particiona DataFrame por período."""
        
        df['date'] = pd.to_datetime(df['newsletter_date'])
        
        partitions = {}
        
        if partition_by == 'month':
            df['partition'] = df['date'].dt.to_period('M').astype(str)
        elif partition_by == 'quarter':
            df['partition'] = df['date'].dt.to_period('Q').astype(str)
        elif partition_by == 'year':
            df['partition'] = df['date'].dt.year.astype(str)
        else:
            raise ValueError(f"partition_by inválido: {partition_by}")
        
        for partition_key, group in df.groupby('partition'):
            partitions[partition_key] = group.drop(columns=['partition', 'date'])
        
        return partitions
    
    def _export_partition(
        self,
        partition_key: str,
        df: pd.DataFrame,
    ) -> Path:
        """Exporta uma partição para Parquet."""
        
        file_path = self.exports_dir / f"{partition_key}.parquet"
        
        # Schema otimizado
        schema = pa.schema([
            ('chunk_id', pa.int64()),
            ('newsletter_date', pa.date32()),
            ('newsletter_path', pa.string()),
            ('section_title', pa.string()),
            ('text', pa.string()),
            ('char_count', pa.int32()),
            ('chunk_index', pa.int32()),
            ('embedding', pa.list_(pa.float32())),  # Array de floats
        ])
        
        # Converter DataFrame para Parquet
        table = pa.Table.from_pandas(df, schema=schema)
        
        pq.write_table(
            table,
            file_path,
            compression='zstd',  # Boa compressão
            compression_level=9,
        )
        
        return file_path
    
    def _load_manifest(self) -> Dict:
        """Carrega manifest existente."""
        if not self.manifest_path.exists():
            return {}
        
        with open(self.manifest_path, 'r') as f:
            return json.load(f)
    
    def _update_manifest(self, exported_files: List[Dict]) -> Dict:
        """Atualiza manifest com info dos exports."""
        
        manifest = self._load_manifest()
        
        # Atualizar metadata
        manifest['version'] = manifest.get('version', '1.0')
        manifest['last_export_date'] = date.today().isoformat()
        manifest['last_export_timestamp'] = datetime.now().isoformat()
        manifest['embedding_model'] = 'models/text-embedding-004'
        
        # Atualizar lista de arquivos
        files_dict = {f['file']: f for f in exported_files}
        
        if 'files' not in manifest:
            manifest['files'] = {}
        
        manifest['files'].update(files_dict)
        
        # Estatísticas
        manifest['total_files'] = len(manifest['files'])
        manifest['total_rows'] = sum(f['rows'] for f in manifest['files'].values())
        manifest['total_size_mb'] = sum(f['size_mb'] for f in manifest['files'].values())
        
        # Salvar
        with open(self.manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        return manifest
```

---

### Módulo 2: Sync com Internet Archive

#### Arquivo: `src/egregora/rag/archive_sync.py`

```python
"""
Sincronização com Internet Archive.

Upload/download de embeddings em formato Parquet
para backup durável e compartilhamento público.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    import internetarchive as ia
except ImportError:
    ia = None


class ArchiveSync:
    """Gerencia sync com Internet Archive."""
    
    # Identificador do item no Archive.org
    ARCHIVE_IDENTIFIER = "egregora-newsletters-embeddings"
    
    def __init__(
        self,
        exports_dir: Path,
        config_path: Path | None = None,
    ):
        if ia is None:
            raise RuntimeError(
                "Biblioteca 'internetarchive' não instalada. "
                "Instale com: pip install internetarchive"
            )
        
        self.exports_dir = exports_dir
        self.config_path = config_path or Path.home() / ".ia"
        
        # Verificar autenticação
        if not self.config_path.exists():
            raise RuntimeError(
                "Internet Archive não configurado. Execute: "
                "ia configure"
            )
    
    def upload_all(
        self,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Upload de todos os arquivos Parquet para o Archive.
        
        Args:
            metadata: Metadata adicional para o item
        
        Returns:
            Relatório do upload
        """
        # 1. Listar arquivos a fazer upload
        files_to_upload = list(self.exports_dir.glob("*.parquet"))
        files_to_upload.append(self.exports_dir / "manifest.json")
        
        if not files_to_upload:
            return {
                "success": False,
                "error": "Nenhum arquivo para upload"
            }
        
        # 2. Preparar metadata do item
        item_metadata = self._build_item_metadata(metadata)
        
        # 3. Criar README
        readme_path = self.exports_dir / "README.md"
        self._create_readme(readme_path)
        files_to_upload.append(readme_path)
        
        # 4. Upload
        item = ia.get_item(self.ARCHIVE_IDENTIFIER)
        
        uploaded_files = []
        failed_files = []
        
        for file_path in files_to_upload:
            try:
                print(f"[Archive] Uploading {file_path.name}...")
                
                result = item.upload_file(
                    file_path,
                    metadata=item_metadata if file_path == files_to_upload[0] else None,
                    queue_derive=False,  # Não processar automaticamente
                )
                
                uploaded_files.append({
                    "file": file_path.name,
                    "size_mb": file_path.stat().st_size / 1024 / 1024,
                    "status": "success"
                })
                
                print(f"[Archive] ✅ {file_path.name} uploaded")
            
            except Exception as e:
                failed_files.append({
                    "file": file_path.name,
                    "error": str(e)
                })
                print(f"[Archive] ❌ Erro ao fazer upload de {file_path.name}: {e}")
        
        # 5. Retornar relatório
        return {
            "success": len(failed_files) == 0,
            "uploaded": len(uploaded_files),
            "failed": len(failed_files),
            "files": uploaded_files,
            "errors": failed_files,
            "url": f"https://archive.org/details/{self.ARCHIVE_IDENTIFIER}",
        }
    
    def upload_incremental(self) -> Dict[str, Any]:
        """
        Upload apenas de arquivos novos ou modificados.
        
        Returns:
            Relatório do upload incremental
        """
        # 1. Obter lista de arquivos já no Archive
        item = ia.get_item(self.ARCHIVE_IDENTIFIER)
        
        if not item.exists:
            # Item não existe - fazer upload completo
            return self.upload_all()
        
        remote_files = {f['name']: f for f in item.files}
        
        # 2. Comparar com arquivos locais
        local_files = list(self.exports_dir.glob("*.parquet"))
        local_files.append(self.exports_dir / "manifest.json")
        
        files_to_upload = []
        
        for local_file in local_files:
            remote_file = remote_files.get(local_file.name)
            
            # Novo arquivo ou tamanho diferente
            if (remote_file is None or 
                int(remote_file['size']) != local_file.stat().st_size):
                files_to_upload.append(local_file)
        
        if not files_to_upload:
            return {
                "success": True,
                "uploaded": 0,
                "message": "Todos os arquivos já estão atualizados no Archive"
            }
        
        # 3. Upload apenas dos arquivos novos/modificados
        uploaded_files = []
        failed_files = []
        
        for file_path in files_to_upload:
            try:
                print(f"[Archive] Uploading {file_path.name}...")
                
                item.upload_file(file_path, queue_derive=False)
                
                uploaded_files.append(file_path.name)
                print(f"[Archive] ✅ {file_path.name} uploaded")
            
            except Exception as e:
                failed_files.append({
                    "file": file_path.name,
                    "error": str(e)
                })
                print(f"[Archive] ❌ Erro: {e}")
        
        return {
            "success": len(failed_files) == 0,
