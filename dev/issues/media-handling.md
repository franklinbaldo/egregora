# Media Handling Enhancement

## Priority: Medium
## Effort: Medium
## Type: Enhancement

## Problem Description

Current media handling is basic and could be significantly improved for better user experience and efficiency:

1. **Basic Extraction**: Media files extracted but no optimization
2. **No Validation**: No security scanning or file type validation
3. **Storage Inefficiency**: No compression or thumbnail generation
4. **Limited Formats**: May not handle all WhatsApp media types well
5. **No Organization**: Media files stored with UUID names, hard to browse

**Current media handling:**
- Extracts media to `data/<group>/media/` with UUID filenames
- No thumbnails or previews
- No optimization for web display
- No security validation

## Current Behavior

### Media Extraction
```python
# Current implementation (simplified)
def extract_media(zip_file, media_dir):
    for file in zip_file.namelist():
        if is_media_file(file):
            # Extract with UUID name
            uuid_name = generate_uuid(file)
            zip_file.extract(file, media_dir / uuid_name)
```

### Output Structure
```
data/rationality-club-latam/media/
├── a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg  # Hard to identify
├── b2c3d4e5-f6g7-8901-bcde-f23456789012.pdf  # No preview
└── c3d4e5f6-g7h8-9012-cdef-345678901234.mp4  # Large file
```

## Proposed Solution

### 1. Enhanced Media Processing Pipeline

```python
from PIL import Image
import ffmpeg
from pathlib import Path
import magic
import hashlib

class MediaProcessor:
    """Advanced media processing with optimization and security."""
    
    def __init__(self, config: MediaConfig):
        self.config = config
        self.supported_types = {
            'image': ['.jpg', '.jpeg', '.png', '.gif', '.webp'],
            'video': ['.mp4', '.avi', '.mov', '.mkv'],
            'audio': ['.mp3', '.ogg', '.m4a', '.wav'],
            'document': ['.pdf', '.doc', '.docx', '.txt']
        }
    
    def process_media_file(self, source_path: Path, media_dir: Path) -> MediaFile:
        """Process a media file with validation, optimization, and metadata."""
        
        # Security validation
        if not self.validate_file_security(source_path):
            raise SecurityError(f"File failed security validation: {source_path}")
        
        # Detect file type
        file_type = self.detect_file_type(source_path)
        
        # Generate organized path
        organized_path = self.generate_organized_path(source_path, media_dir, file_type)
        
        # Process based on type
        if file_type == 'image':
            return self.process_image(source_path, organized_path)
        elif file_type == 'video':
            return self.process_video(source_path, organized_path)
        elif file_type == 'audio':
            return self.process_audio(source_path, organized_path)
        else:
            return self.process_document(source_path, organized_path)
    
    def validate_file_security(self, file_path: Path) -> bool:
        """Validate file for security threats."""
        # Check file size
        if file_path.stat().st_size > self.config.max_file_size:
            return False
        
        # Check MIME type
        mime_type = magic.from_file(str(file_path), mime=True)
        if mime_type not in self.config.allowed_mime_types:
            return False
        
        # Basic malware scanning (could integrate with external service)
        return self.scan_for_malware(file_path)
    
    def process_image(self, source: Path, dest: Path) -> MediaFile:
        """Process image with optimization and thumbnail generation."""
        with Image.open(source) as img:
            # Get metadata
            metadata = {
                'width': img.width,
                'height': img.height,
                'format': img.format,
                'mode': img.mode
            }
            
            # Optimize image
            if self.config.optimize_images:
                img = self.optimize_image(img)
            
            # Save optimized version
            img.save(dest, optimize=True, quality=self.config.image_quality)
            
            # Generate thumbnail
            thumbnail_path = self.generate_thumbnail(img, dest)
            
            return MediaFile(
                original_path=source,
                processed_path=dest,
                thumbnail_path=thumbnail_path,
                file_type='image',
                metadata=metadata,
                file_size=dest.stat().st_size
            )
    
    def generate_thumbnail(self, image: Image, original_path: Path) -> Path:
        """Generate thumbnail for image."""
        thumbnail_dir = original_path.parent / 'thumbnails'
        thumbnail_dir.mkdir(exist_ok=True)
        
        thumbnail_path = thumbnail_dir / f"{original_path.stem}_thumb{original_path.suffix}"
        
        # Create thumbnail
        thumbnail = image.copy()
        thumbnail.thumbnail(self.config.thumbnail_size, Image.Resampling.LANCZOS)
        thumbnail.save(thumbnail_path, optimize=True, quality=85)
        
        return thumbnail_path
```

### 2. Organized File Structure

```python
def generate_organized_path(self, source_path: Path, media_dir: Path, file_type: str) -> Path:
    """Generate organized path based on file type and date."""
    
    # Extract date from filename or use current date
    date_str = self.extract_date_from_filename(source_path) or datetime.now().strftime('%Y-%m')
    
    # Create organized directory structure
    type_dir = media_dir / file_type / date_str
    type_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate readable filename
    original_name = source_path.stem
    extension = source_path.suffix
    
    # Create hash for uniqueness while keeping readable name
    content_hash = self.generate_content_hash(source_path)[:8]
    new_name = f"{original_name}_{content_hash}{extension}"
    
    return type_dir / new_name

# Result structure:
# data/group/media/
# ├── image/
# │   ├── 2024-03/
# │   │   ├── sunset_photo_a1b2c3d4.jpg
# │   │   ├── thumbnails/
# │   │   │   └── sunset_photo_a1b2c3d4_thumb.jpg
# │   └── 2024-04/
# ├── video/
# │   └── 2024-03/
# │       ├── birthday_party_e5f6g7h8.mp4
# │       └── previews/
# │           └── birthday_party_e5f6g7h8_preview.jpg
# └── document/
#     └── 2024-03/
#         └── meeting_notes_i9j0k1l2.pdf
```

### 3. Video Processing

```python
def process_video(self, source: Path, dest: Path) -> MediaFile:
    """Process video with compression and preview generation."""
    
    # Get video metadata
    probe = ffmpeg.probe(str(source))
    video_info = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    
    metadata = {
        'width': video_info['width'],
        'height': video_info['height'],
        'duration': float(video_info['duration']),
        'codec': video_info['codec_name'],
        'bitrate': video_info.get('bit_rate')
    }
    
    # Compress video if too large
    if source.stat().st_size > self.config.video_compression_threshold:
        self.compress_video(source, dest)
    else:
        shutil.copy2(source, dest)
    
    # Generate preview frame
    preview_path = self.generate_video_preview(dest)
    
    return MediaFile(
        original_path=source,
        processed_path=dest,
        thumbnail_path=preview_path,
        file_type='video',
        metadata=metadata,
        file_size=dest.stat().st_size
    )

def compress_video(self, source: Path, dest: Path):
    """Compress video for web optimization."""
    (
        ffmpeg
        .input(str(source))
        .video('libx264', crf=23)  # Good quality/size balance
        .audio('aac', audio_bitrate='128k')
        .output(str(dest))
        .overwrite_output()
        .run(quiet=True)
    )

def generate_video_preview(self, video_path: Path) -> Path:
    """Generate preview image from video."""
    preview_dir = video_path.parent / 'previews'
    preview_dir.mkdir(exist_ok=True)
    
    preview_path = preview_dir / f"{video_path.stem}_preview.jpg"
    
    # Extract frame at 25% of video duration
    (
        ffmpeg
        .input(str(video_path), ss='25%')
        .output(str(preview_path), vframes=1, format='image2')
        .overwrite_output()
        .run(quiet=True)
    )
    
    return preview_path
```

### 4. Media Index and Metadata

```python
@dataclass
class MediaFile:
    """Metadata for processed media file."""
    original_path: Path
    processed_path: Path
    thumbnail_path: Optional[Path]
    file_type: str
    metadata: Dict[str, Any]
    file_size: int
    content_hash: str
    processed_at: datetime
    
    def to_dict(self) -> Dict:
        """Serialize for JSON storage."""
        return {
            'original_name': self.original_path.name,
            'processed_path': str(self.processed_path),
            'thumbnail_path': str(self.thumbnail_path) if self.thumbnail_path else None,
            'file_type': self.file_type,
            'metadata': self.metadata,
            'file_size': self.file_size,
            'content_hash': self.content_hash,
            'processed_at': self.processed_at.isoformat()
        }

class MediaIndex:
    """Index of all processed media files."""
    
    def __init__(self, media_dir: Path):
        self.media_dir = media_dir
        self.index_file = media_dir / 'media_index.json'
        self.index = self.load_index()
    
    def add_media(self, media_file: MediaFile):
        """Add media file to index."""
        self.index[media_file.content_hash] = media_file.to_dict()
        self.save_index()
    
    def find_by_hash(self, content_hash: str) -> Optional[MediaFile]:
        """Find media file by content hash."""
        if content_hash in self.index:
            return MediaFile.from_dict(self.index[content_hash])
        return None
    
    def find_duplicates(self) -> List[Tuple[str, List[str]]]:
        """Find duplicate files by content hash."""
        duplicates = []
        hash_to_files = {}
        
        for hash_key, media_data in self.index.items():
            path = media_data['processed_path']
            if hash_key not in hash_to_files:
                hash_to_files[hash_key] = []
            hash_to_files[hash_key].append(path)
        
        return [(h, files) for h, files in hash_to_files.items() if len(files) > 1]
```

### 5. Configuration and CLI Integration

```toml
# Configuration
[media]
enabled = true
optimize_images = true
image_quality = 85
thumbnail_size = [300, 300]
video_compression_threshold = "50MB"
max_file_size = "100MB"
allowed_mime_types = [
    "image/jpeg", "image/png", "image/gif",
    "video/mp4", "video/quicktime",
    "audio/mpeg", "audio/ogg",
    "application/pdf"
]

# Storage organization
organize_by_date = true
preserve_original_names = true
generate_thumbnails = true
compress_videos = true
```

```bash
# CLI commands for media management
egregora media optimize    # Re-process all media with current settings
egregora media index       # Rebuild media index
egregora media duplicates  # Find and manage duplicate files  
egregora media stats       # Show media storage statistics
```

## Expected Benefits

1. **Better User Experience**: Thumbnails and previews for easy browsing
2. **Storage Efficiency**: Compression reduces storage costs
3. **Security**: File validation prevents malware
4. **Organization**: Structured storage makes media manageable
5. **Performance**: Optimized files load faster in generated posts

## Acceptance Criteria

- [ ] Automatic thumbnail generation for images
- [ ] Video compression and preview frames
- [ ] Organized directory structure by type and date
- [ ] Security validation for all uploaded files
- [ ] Media index with search capabilities
- [ ] Duplicate detection and management
- [ ] CLI commands for media management
- [ ] Configuration options for optimization settings

## Implementation Phases

### Phase 1: Basic Enhancements
- Thumbnail generation
- Basic optimization
- Organized file structure

### Phase 2: Advanced Processing
- Video compression and previews
- Security validation
- Media indexing

### Phase 3: Management Features
- Duplicate detection
- CLI management commands
- Analytics and reporting

## Files to Modify

- `src/egregora/media_processor.py` - New enhanced processor
- `src/egregora/config.py` - Media configuration
- `src/egregora/__main__.py` - Media CLI commands
- `src/egregora/models.py` - MediaFile model
- `requirements.txt` - Add PIL, ffmpeg-python, python-magic
- `docs/media-handling.md` - Media documentation

## Related Issues

- #005: Performance & Scalability (optimize media processing)
- #008: Output Formats (media in different output formats)
- #009: Privacy & Security (media security validation)