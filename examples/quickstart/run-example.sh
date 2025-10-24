#!/bin/bash
# Egregora Quickstart Example
# This script demonstrates the complete workflow

set -e  # Exit on error

echo "🧠 Egregora Quickstart Example"
echo "=============================="
echo ""

# Check API key
if [ -z "$GOOGLE_API_KEY" ]; then
    echo "❌ Error: GOOGLE_API_KEY not set"
    echo "Run: export GOOGLE_API_KEY='your-api-key-here'"
    exit 1
fi

# Check if WhatsApp export provided
EXPORT_ZIP="${1:-}"
if [ -z "$EXPORT_ZIP" ]; then
    echo "❌ Error: No WhatsApp export provided"
    echo "Usage: ./run-example.sh /path/to/whatsapp-export.zip"
    exit 1
fi

if [ ! -f "$EXPORT_ZIP" ]; then
    echo "❌ Error: Export file not found: $EXPORT_ZIP"
    exit 1
fi

echo "✅ API key configured"
echo "✅ Export file found: $EXPORT_ZIP"
echo ""

# Step 1: Initialize site
echo "📁 Step 1: Initialize site"
egregora init example-blog
cd example-blog

# Step 2: Install MkDocs
echo "📦 Step 2: Install MkDocs Material"
pip install -q 'mkdocs-material[imaging]'

# Step 3: Process export
echo "⚙️  Step 3: Process WhatsApp export"
egregora process \
  "$EXPORT_ZIP" \
  --output=. \
  --timezone='America/Sao_Paulo' \
  --from-date=2025-01-01 \
  --to-date=2025-01-31 \
  --enable-enrichment

# Step 4: Show results
echo ""
echo "✅ Processing complete!"
echo ""
echo "📊 Results:"
echo "----------"
echo "Posts generated: $(find posts -name "*.md" 2>/dev/null | wc -l)"
echo "Profiles created: $(find profiles -name "*.md" 2>/dev/null | wc -l)"
echo ""

# Step 5: Serve site
echo "🌐 Step 5: Starting preview server"
echo ""
echo "Open http://localhost:8000 in your browser"
echo "Press Ctrl+C to stop the server"
echo ""

mkdocs serve
