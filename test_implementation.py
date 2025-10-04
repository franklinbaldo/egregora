#!/usr/bin/env python3
"""Quick test script to verify the new auto-discovery and virtual groups implementation."""

import sys
from pathlib import Path
from datetime import date

# Add src to path for imports
sys.path.insert(0, 'src')

def test_group_discovery():
    """Test group discovery from test ZIP file."""
    print("🔍 Testing group discovery...")
    
    from egregora.group_discovery import discover_groups
    
    test_zips_dir = Path("tests/data")
    groups = discover_groups(test_zips_dir)
    
    print(f"Found {len(groups)} groups:")
    for slug, exports in groups.items():
        print(f"  • {exports[0].group_name} ({slug}): {len(exports)} exports")
        for export in exports:
            print(f"    - {export.export_date}: {export.chat_file}")
    
    return groups

def test_parser():
    """Test parsing a WhatsApp export."""
    print("\n📊 Testing parser...")
    
    from egregora.group_discovery import discover_groups
    from egregora.parser import parse_export
    
    test_zips_dir = Path("tests/data")
    groups = discover_groups(test_zips_dir)
    
    if not groups:
        print("❌ No groups found for testing")
        return None
    
    # Get first export
    first_group = list(groups.values())[0]
    first_export = first_group[0]
    
    df = parse_export(first_export)
    print(f"Parsed {len(df)} messages:")
    print(f"  Columns: {list(df.columns)}")
    if not df.empty:
        print(f"  Sample message: {df.iloc[0]['author']}: {df.iloc[0]['message']}")
        print(f"  Date range: {df['date'].min()} to {df['date'].max()}")
    
    return df

def test_virtual_groups():
    """Test virtual group creation."""
    print("\n🔀 Testing virtual groups...")
    
    from egregora.group_discovery import discover_groups
    from egregora.models import MergeConfig
    from egregora.merger import create_virtual_groups
    
    test_zips_dir = Path("tests/data")
    real_groups = discover_groups(test_zips_dir)
    
    if not real_groups:
        print("❌ No real groups found for testing")
        return None
    
    # Create a test merge config
    first_slug = list(real_groups.keys())[0]
    merge_configs = {
        "test-virtual": MergeConfig(
            name="Test Virtual Group",
            source_groups=[first_slug],
            tag_style="emoji",
            group_emojis={first_slug: "🧪"}
        )
    }
    
    virtual_groups = create_virtual_groups(real_groups, merge_configs)
    print(f"Created {len(virtual_groups)} virtual groups:")
    for slug, source in virtual_groups.items():
        print(f"  • {source.name} ({slug})")
        print(f"    Merges: {source.merge_config.source_groups}")
        print(f"    Is virtual: {source.is_virtual}")
    
    return virtual_groups

def test_transcript():
    """Test transcript extraction."""
    print("\n📝 Testing transcript extraction...")
    
    from egregora.group_discovery import discover_groups
    from egregora.models import GroupSource
    from egregora.transcript import extract_transcript, get_available_dates
    
    test_zips_dir = Path("tests/data")
    groups = discover_groups(test_zips_dir)
    
    if not groups:
        print("❌ No groups found for testing")
        return None
    
    # Create GroupSource from first group
    first_slug, first_exports = next(iter(groups.items()))
    source = GroupSource(
        slug=first_slug,
        name=first_exports[0].group_name,
        exports=first_exports,
        is_virtual=False
    )
    
    # Get available dates
    dates = get_available_dates(source)
    print(f"Available dates: {dates}")
    
    if dates:
        # Extract transcript for first available date
        first_date = dates[0]
        transcript = extract_transcript(source, first_date)
        print(f"Transcript for {first_date} ({len(transcript.split())} words):")
        print(transcript[:200] + "..." if len(transcript) > 200 else transcript)
    
    return transcript if dates else None

def main():
    """Run all tests."""
    print("🚀 Testing Auto-discovery and Virtual Groups Implementation\n")
    
    try:
        groups = test_group_discovery()
        df = test_parser()
        virtual_groups = test_virtual_groups()
        transcript = test_transcript()
        
        print("\n✅ All tests completed successfully!")
        
        if groups:
            print(f"   - Discovered {len(groups)} groups")
        if df is not None:
            print(f"   - Parsed {len(df)} messages")
        if virtual_groups:
            print(f"   - Created {len(virtual_groups)} virtual groups")
        if transcript:
            print(f"   - Generated transcript ({len(transcript)} chars)")
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure polars is installed: pip install polars")
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()