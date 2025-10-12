# Privacy & Security Enhancement

## Priority: High
## Effort: Medium
## Type: Security

## Problem Description

While Egregora has good baseline privacy features (deterministic anonymization), there are opportunities to enhance privacy and security:

1. **Limited Anonymization Levels**: Only one anonymization format option
2. **No Data Retention Policies**: No automatic cleanup of sensitive data
3. **Cache Security**: Enrichment cache may contain sensitive content
4. **No PII Detection**: Limited detection of personal information in content
5. **Audit Trail Missing**: No logging of privacy-sensitive operations

**Current privacy features:**
- ✅ Deterministic anonymization of phone numbers
- ✅ Consistent pseudonyms across processing runs
- ✅ No real names in output
- ❌ No configurable privacy levels
- ❌ No automatic PII detection/redaction
- ❌ No data retention management

## Current Behavior

### Basic Anonymization
```python
# Current anonymization (simplified)
def anonymize_author(self, author: str) -> str:
    if author.startswith('+'):
        # Phone number - always same format
        return f"Member-{self.generate_uuid(author)[:4]}"
    else:
        # Nickname - basic anonymization  
        return f"Member-{self.generate_uuid(author)[:4]}"
```

### Limited Privacy Controls
- Single anonymization format (`human`)
- No user control over privacy levels
- No detection of PII in message content
- Cache files may contain original URLs and content

## Proposed Solution

### 1. Configurable Privacy Levels

```python
from enum import Enum
from typing import List, Pattern
import re

class PrivacyLevel(Enum):
    """Privacy levels for different use cases."""
    MINIMAL = "minimal"      # Basic phone anonymization
    STANDARD = "standard"    # Phone + nickname anonymization  
    HIGH = "high"           # + PII detection and redaction
    MAXIMUM = "maximum"     # + content filtering and sanitization

class PrivacyConfig(BaseModel):
    """Configuration for privacy and anonymization."""
    
    level: PrivacyLevel = PrivacyLevel.STANDARD
    
    # Anonymization settings
    anonymize_phones: bool = True
    anonymize_nicknames: bool = True
    consistent_pseudonyms: bool = True
    
    # PII detection and redaction
    detect_pii: bool = True
    redact_emails: bool = True
    redact_addresses: bool = True
    redact_credit_cards: bool = True
    redact_urls: bool = False
    
    # Content filtering
    filter_sensitive_content: bool = False
    content_filters: List[str] = []
    
    # Data retention
    auto_cleanup_enabled: bool = True
    retention_days: int = 365
    cleanup_cache: bool = True
    cleanup_logs: bool = True

class EnhancedAnonymizer:
    """Enhanced anonymization with configurable privacy levels."""
    
    def __init__(self, config: PrivacyConfig):
        self.config = config
        self.pii_patterns = self.setup_pii_patterns()
        self.pseudonym_cache = {}
    
    def setup_pii_patterns(self) -> Dict[str, Pattern]:
        """Setup regex patterns for PII detection."""
        return {
            'email': re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
            'phone': re.compile(r'\+?[\d\s\-\(\)]{10,}'),
            'credit_card': re.compile(r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b'),
            'ssn': re.compile(r'\b\d{3}[\s\-]?\d{2}[\s\-]?\d{4}\b'),
            'url': re.compile(r'https?://[^\s]+'),
            'address': re.compile(r'\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr|Boulevard|Blvd)', re.IGNORECASE)
        }
    
    def anonymize_content(self, content: str, sender: str) -> str:
        """Anonymize content based on privacy level."""
        
        # Always anonymize sender
        anonymized_content = content
        
        if self.config.level in [PrivacyLevel.HIGH, PrivacyLevel.MAXIMUM]:
            anonymized_content = self.detect_and_redact_pii(anonymized_content)
        
        if self.config.level == PrivacyLevel.MAXIMUM:
            anonymized_content = self.apply_content_filters(anonymized_content)
        
        return anonymized_content
    
    def detect_and_redact_pii(self, content: str) -> str:
        """Detect and redact personally identifiable information."""
        redacted_content = content
        
        if self.config.redact_emails:
            redacted_content = self.pii_patterns['email'].sub('[EMAIL]', redacted_content)
        
        if self.config.redact_addresses:
            redacted_content = self.pii_patterns['address'].sub('[ADDRESS]', redacted_content)
        
        if self.config.redact_credit_cards:
            redacted_content = self.pii_patterns['credit_card'].sub('[CREDIT_CARD]', redacted_content)
        
        if self.config.redact_urls and self.config.level == PrivacyLevel.MAXIMUM:
            redacted_content = self.pii_patterns['url'].sub('[URL_REDACTED]', redacted_content)
        
        return redacted_content
    
    def apply_content_filters(self, content: str) -> str:
        """Apply custom content filters for maximum privacy."""
        filtered_content = content
        
        for filter_pattern in self.config.content_filters:
            filtered_content = re.sub(filter_pattern, '[FILTERED]', filtered_content, flags=re.IGNORECASE)
        
        return filtered_content
```

### 2. Data Retention Management

```python
from datetime import datetime, timedelta
import shutil

class DataRetentionManager:
    """Manage data retention and cleanup policies."""
    
    def __init__(self, config: PrivacyConfig):
        self.config = config
        self.retention_period = timedelta(days=config.retention_days)
    
    def cleanup_expired_data(self, base_dir: Path) -> CleanupReport:
        """Clean up data older than retention period."""
        
        report = CleanupReport()
        cutoff_date = datetime.now() - self.retention_period
        
        if self.config.cleanup_cache:
            cache_cleaned = self.cleanup_cache_directory(base_dir / "cache", cutoff_date)
            report.cache_files_deleted = cache_cleaned
        
        if self.config.cleanup_logs:
            logs_cleaned = self.cleanup_log_files(base_dir / "logs", cutoff_date)
            report.log_files_deleted = logs_cleaned
        
        # Clean up old posts if configured
        if self.config.auto_cleanup_enabled:
            posts_cleaned = self.cleanup_old_posts(base_dir / "data", cutoff_date)
            report.posts_deleted = posts_cleaned
        
        return report
    
    def cleanup_cache_directory(self, cache_dir: Path, cutoff_date: datetime) -> int:
        """Clean up cache files older than cutoff date."""
        deleted_count = 0
        
        if not cache_dir.exists():
            return deleted_count
        
        for cache_file in cache_dir.rglob("*"):
            if cache_file.is_file():
                file_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
                if file_time < cutoff_date:
                    try:
                        cache_file.unlink()
                        deleted_count += 1
                        logger.info(f"Deleted expired cache file: {cache_file}")
                    except Exception as e:
                        logger.warning(f"Failed to delete cache file {cache_file}: {e}")
        
        return deleted_count
    
    def secure_delete_file(self, file_path: Path) -> bool:
        """Securely delete file by overwriting before removal."""
        try:
            if file_path.exists() and file_path.is_file():
                # Overwrite with random data
                file_size = file_path.stat().st_size
                with open(file_path, 'wb') as f:
                    f.write(os.urandom(file_size))
                
                # Remove file
                file_path.unlink()
                return True
        except Exception as e:
            logger.error(f"Failed to securely delete {file_path}: {e}")
        
        return False

@dataclass
class CleanupReport:
    """Report of data cleanup operations."""
    cache_files_deleted: int = 0
    log_files_deleted: int = 0
    posts_deleted: int = 0
    errors: List[str] = field(default_factory=list)
    
    @property
    def total_files_deleted(self) -> int:
        return self.cache_files_deleted + self.log_files_deleted + self.posts_deleted
```

### 3. Privacy Audit Logging

```python
from enum import Enum
import logging

class PrivacyEvent(Enum):
    """Types of privacy-related events to log."""
    ANONYMIZATION = "anonymization"
    PII_DETECTION = "pii_detection"
    DATA_REDACTION = "data_redaction"
    CACHE_ACCESS = "cache_access"
    DATA_EXPORT = "data_export"
    DATA_CLEANUP = "data_cleanup"

class PrivacyAuditor:
    """Audit privacy-related operations."""
    
    def __init__(self, audit_file: Path):
        self.audit_file = audit_file
        self.logger = self.setup_audit_logger()
    
    def setup_audit_logger(self) -> logging.Logger:
        """Setup dedicated logger for privacy audit."""
        logger = logging.getLogger('egregora.privacy_audit')
        logger.setLevel(logging.INFO)
        
        # Audit log handler
        handler = logging.FileHandler(self.audit_file)
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S UTC'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger
    
    def log_event(self, event: PrivacyEvent, details: Dict[str, Any]):
        """Log privacy-related event."""
        
        log_entry = {
            'event': event.value,
            'timestamp': datetime.utcnow().isoformat(),
            'details': details
        }
        
        self.logger.info(json.dumps(log_entry))
    
    def log_anonymization(self, original_author: str, anonymized_author: str, group: str):
        """Log anonymization operation."""
        self.log_event(PrivacyEvent.ANONYMIZATION, {
            'group': group,
            'original_hash': hashlib.sha256(original_author.encode()).hexdigest()[:8],
            'anonymized_id': anonymized_author,
            'method': 'deterministic_uuid'
        })
    
    def log_pii_detection(self, content_hash: str, pii_types: List[str], redacted_count: int):
        """Log PII detection and redaction."""
        self.log_event(PrivacyEvent.PII_DETECTION, {
            'content_hash': content_hash,
            'pii_types_found': pii_types,
            'items_redacted': redacted_count
        })
    
    def generate_privacy_report(self, days: int = 30) -> PrivacyReport:
        """Generate privacy audit report."""
        
        # Read audit log for specified period
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        events = self.read_audit_events_since(cutoff_date)
        
        report = PrivacyReport()
        
        for event in events:
            event_type = event['event']
            
            if event_type == PrivacyEvent.ANONYMIZATION.value:
                report.anonymizations_performed += 1
            elif event_type == PrivacyEvent.PII_DETECTION.value:
                report.pii_detections += 1
                report.items_redacted += event['details'].get('items_redacted', 0)
            elif event_type == PrivacyEvent.DATA_CLEANUP.value:
                report.cleanup_operations += 1
        
        return report

@dataclass
class PrivacyReport:
    """Privacy operations report."""
    anonymizations_performed: int = 0
    pii_detections: int = 0
    items_redacted: int = 0
    cleanup_operations: int = 0
    compliance_score: float = 0.0
    
    def calculate_compliance_score(self) -> float:
        """Calculate privacy compliance score."""
        # Simple scoring based on privacy operations
        score = 100.0
        
        # Deduct points for detected but not redacted PII
        if self.pii_detections > self.items_redacted:
            score -= (self.pii_detections - self.items_redacted) * 5
        
        return max(0.0, min(100.0, score))
```

### 4. Secure Cache Management

```python
class SecureCache:
    """Cache with encryption and expiration for sensitive data."""
    
    def __init__(self, cache_dir: Path, encryption_key: bytes):
        self.cache_dir = cache_dir
        self.cipher = Fernet(encryption_key)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def store_encrypted(self, key: str, data: Dict, ttl_hours: int = 24):
        """Store data encrypted in cache."""
        
        cache_entry = {
            'data': data,
            'expires_at': (datetime.utcnow() + timedelta(hours=ttl_hours)).isoformat(),
            'created_at': datetime.utcnow().isoformat()
        }
        
        # Encrypt data
        encrypted_data = self.cipher.encrypt(json.dumps(cache_entry).encode())
        
        # Store to file
        cache_file = self.cache_dir / f"{hashlib.sha256(key.encode()).hexdigest()}.cache"
        cache_file.write_bytes(encrypted_data)
    
    def retrieve_decrypted(self, key: str) -> Optional[Dict]:
        """Retrieve and decrypt data from cache."""
        
        cache_file = self.cache_dir / f"{hashlib.sha256(key.encode()).hexdigest()}.cache"
        
        if not cache_file.exists():
            return None
        
        try:
            # Decrypt data
            encrypted_data = cache_file.read_bytes()
            decrypted_data = self.cipher.decrypt(encrypted_data)
            cache_entry = json.loads(decrypted_data.decode())
            
            # Check expiration
            expires_at = datetime.fromisoformat(cache_entry['expires_at'])
            if datetime.utcnow() > expires_at:
                cache_file.unlink()  # Remove expired cache
                return None
            
            return cache_entry['data']
            
        except Exception as e:
            logger.warning(f"Failed to decrypt cache entry: {e}")
            cache_file.unlink()  # Remove corrupted cache
            return None
```

### 5. CLI Privacy Commands

```bash
# Privacy management commands
egregora privacy audit                 # Generate privacy audit report
egregora privacy cleanup               # Run data retention cleanup
egregora privacy test-anonymization    # Test anonymization on sample data
egregora privacy export-report         # Export privacy compliance report
egregora privacy configure-level HIGH  # Set privacy level
```

```python
# CLI implementation
@click.group()
def privacy():
    """Privacy and security management commands."""
    pass

@privacy.command()
@click.option('--days', default=30, help='Report period in days')
def audit(days: int):
    """Generate privacy audit report."""
    
    auditor = PrivacyAuditor(Path("logs/privacy_audit.log"))
    report = auditor.generate_privacy_report(days)
    
    console.print(Panel.fit(
        f"Privacy Audit Report (Last {days} days)\n\n"
        f"Anonymizations: {report.anonymizations_performed}\n"
        f"PII Detections: {report.pii_detections}\n"
        f"Items Redacted: {report.items_redacted}\n"
        f"Cleanup Operations: {report.cleanup_operations}\n"
        f"Compliance Score: {report.compliance_score:.1f}/100",
        title="🔒 Privacy Audit"
    ))

@privacy.command()
@click.option('--dry-run', is_flag=True, help='Show what would be cleaned up')
def cleanup(dry_run: bool):
    """Run data retention cleanup."""
    
    config = PipelineConfig.load()
    retention_manager = DataRetentionManager(config.privacy)
    
    if dry_run:
        # Show what would be cleaned up
        console.print("🧹 Dry run - files that would be deleted:")
        # Implementation for dry run
    else:
        report = retention_manager.cleanup_expired_data(Path("."))
        console.print(f"✅ Cleaned up {report.total_files_deleted} files")
```

## Expected Benefits

1. **Enhanced Privacy**: Configurable privacy levels for different needs
2. **Compliance**: Audit trails and reports for privacy compliance
3. **Data Protection**: Automatic cleanup and secure deletion
4. **PII Protection**: Automatic detection and redaction of sensitive information
5. **User Control**: Granular privacy settings and transparency

## Acceptance Criteria

- [ ] Multiple privacy levels (minimal, standard, high, maximum)
- [ ] Automatic PII detection and redaction
- [ ] Data retention policies with automatic cleanup
- [ ] Privacy audit logging and reporting
- [ ] Encrypted cache for sensitive data
- [ ] CLI commands for privacy management
- [ ] Privacy configuration validation
- [ ] Secure file deletion for cleanup operations

## Configuration Example

```toml
[privacy]
level = "high"
anonymize_phones = true
anonymize_nicknames = true

# PII detection
detect_pii = true
redact_emails = true
redact_addresses = true
redact_credit_cards = true

# Data retention
auto_cleanup_enabled = true
retention_days = 365
cleanup_cache = true

# Audit logging
audit_enabled = true
audit_file = "logs/privacy_audit.log"

# Custom filters for maximum privacy
content_filters = [
    "\\b\\d{4}\\s*\\d{4}\\s*\\d{4}\\s*\\d{4}\\b",  # Credit cards
    "\\b[A-Z]{2}\\d{8}\\b"  # Government IDs
]
```

## Files to Modify

- `src/egregora/privacy/` - New privacy module
- `src/egregora/anonymizer.py` - Enhanced anonymization
- `src/egregora/config.py` - Privacy configuration
- `src/egregora/__main__.py` - Privacy CLI commands
- `src/egregora/cache/` - Secure cache implementation
- `docs/privacy.md` - Privacy documentation
- `docs/compliance.md` - Compliance guide

## Related Issues

- #002: Configuration UX (privacy level configuration)
- #007: Media Handling (media file security)
- #010: Backup & Recovery (secure backup procedures)
- #012: Monitoring & Analytics (privacy metrics)