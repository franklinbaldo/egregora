# 🚀 Egregora API Testing Plan

## Overview
Comprehensive testing strategy for egregora with real Gemini API access, focusing on post quality and system reliability.

## 🔑 Prerequisites
- `GEMINI_API_KEY` or `GOOGLE_API_KEY` environment variable set
- Test WhatsApp exports available in `data/whatsapp_zips/`
- Quality control framework in place

## 📋 Test Sequence

### Phase 1: Basic API Connectivity (5 minutes)
```bash
# Test 1: Single day, minimal processing
uv run egregora data/whatsapp_zips/real-whatsapp-export.zip \
  --from-date 2025-10-03 --to-date 2025-10-03 \
  --disable-enrichment --config egregora.toml

# Expected: Single post generated without enrichment
# Validates: safety_settings fix, basic LLM connectivity
```

### Phase 2: Safety Settings Validation (10 minutes)
```bash
# Test 2: Verify fix for UnboundLocalError
uv run egregora data/whatsapp_zips/real-whatsapp-export.zip \
  --from-date 2025-10-03 --to-date 2025-10-03 \
  --config egregora.toml

# Expected: Post generated with enrichment enabled
# Validates: safety_settings fix, enrichment pipeline
```

### Phase 3: Quality Control Analysis (15 minutes)
```bash
# Test 3: Generate post and analyze quality
uv run egregora data/whatsapp_zips/real-whatsapp-export.zip \
  --from-date 2025-10-03 --to-date 2025-10-03 \
  --config egregora.toml

# Then analyze generated post
POST_FILE=$(find data/*/posts/daily/ -name "2025-10-03.md" | head -1)
uv run python scripts/quality_control.py "$POST_FILE"

# Expected: Quality score ≥70/100, no privacy violations
```

### Phase 4: Date Range Functionality (20 minutes)
```bash
# Test 4: Multi-day processing
uv run egregora data/whatsapp_zips/real-whatsapp-export.zip \
  --from-date 2025-10-01 --to-date 2025-10-03 \
  --config egregora.toml

# Expected: 3 posts generated, proper date handling
# Validates: Date range feature, bulk processing
```

### Phase 5: Multi-File Processing (25 minutes)
```bash
# Test 5: Multiple ZIP files
uv run egregora data/whatsapp_zips/real-whatsapp-export.zip \
  data/whatsapp_zips/second-export.zip \
  --days 2 --config egregora.toml

# Expected: Auto-merged processing, combined date range
# Validates: Multi-file handling, auto-merge logic
```

### Phase 6: Error Handling & Edge Cases (30 minutes)
```bash
# Test 6: Large date range (should warn about quota)
uv run egregora data/whatsapp_zips/real-whatsapp-export.zip \
  --from-date 2025-03-01 --to-date 2025-10-03 \
  --dry-run --config egregora.toml

# Test 7: API rate limiting behavior
uv run egregora data/whatsapp_zips/real-whatsapp-export.zip \
  --days 5 --config egregora.toml
# Expected: Proper rate limiting, graceful handling
```

### Phase 7: Content Type Validation (35 minutes)
```bash
# Test 8: Analyze different content patterns
for post in data/*/posts/daily/*.md; do
  echo "=== $post ==="
  uv run python scripts/quality_control.py "$post"
  echo ""
done

# Expected: Quality analysis for all generated posts
# Validates: Various conversation patterns, link handling
```

## 🎯 Success Criteria

### ✅ **Must Pass**
- [ ] **API Connectivity**: No authentication errors
- [ ] **Safety Settings**: No UnboundLocalError 
- [ ] **Privacy Protection**: All posts pass privacy scan
- [ ] **YAML Generation**: Valid front matter in all posts
- [ ] **Date Accuracy**: Correct date in filename and content

### ✅ **Should Pass** 
- [ ] **Quality Score**: Average ≥75/100 across all posts
- [ ] **Attribution**: ≥90% sentence attribution coverage
- [ ] **Voice Consistency**: 1st person plural throughout
- [ ] **Link Preservation**: All URLs at correct positions
- [ ] **Fio Structure**: 4-10 fios per post

### ⚠️ **Monitor**
- [ ] **API Usage**: Quota consumption vs estimates
- [ ] **Rate Limiting**: Proper delays between calls
- [ ] **Error Recovery**: Graceful handling of failures
- [ ] **Performance**: Processing time per post

## 🔍 Quality Checkpoints

### After Each Test Phase
1. **Check Generated Files**:
   ```bash
   ls -la data/*/posts/daily/
   ```

2. **Run Quality Control**:
   ```bash
   find data/*/posts/daily/ -name "*.md" -exec \
     uv run python scripts/quality_control.py {} \;
   ```

3. **Privacy Validation**:
   ```bash
   grep -r "+55\|(\d\{4\})" data/*/posts/daily/ || echo "No privacy issues"
   ```

4. **Content Review** (sample random post):
   ```bash
   POST=$(find data/*/posts/daily/ -name "*.md" | shuf | head -1)
   echo "=== Sample Post: $POST ==="
   head -20 "$POST"
   ```

## 📊 Expected Quality Metrics

### **High-Quality Post Example**
- **Structure**: 6-8 fios with clear titles
- **Attribution**: Every sentence ends with (Member-XXXX)
- **Voice**: Consistent "nós" throughout
- **Context**: Explicit explanations of implicit tensions
- **Links**: All URLs preserved at mention points
- **Privacy**: No phone numbers or real names

### **Sample Quality Analysis Output**
```
🔍 QUALITY CONTROL REPORT
Post: 2025-10-03-rationality-club-latam.md
Status: PRODUCTION READY
Overall Score: 87/100

DETAILED SCORES:
✅ Privacy: PASS
📊 Structure: 23/25
📝 Content: 21/25  
🔧 Technical: 22/25

⚠️ WARNINGS:
  • Attribution coverage: 93%

✅ RECOMMENDATION: Ready for production
```

## 🚨 Failure Scenarios & Recovery

### **Privacy Violation**
```bash
# If privacy scan fails:
# 1. Stop processing immediately
# 2. Review generated content manually
# 3. Check anonymization logic
# 4. Update privacy patterns if needed
```

### **Poor Quality Score**
```bash
# If quality < 70/100:
# 1. Analyze specific failure points
# 2. Check prompt engineering
# 3. Review input data quality
# 4. Consider model parameter tuning
```

### **API Quota Exceeded**
```bash
# If quota limits hit:
# 1. Check rate limiting implementation
# 2. Reduce batch sizes
# 3. Implement better scheduling
# 4. Monitor usage patterns
```

## 🔧 Debugging Tools

### **Log Analysis**
```bash
# Enable verbose logging
export EGREGORA_LOG_LEVEL=DEBUG
uv run egregora [args] 2>&1 | tee test_run.log
```

### **Manual Content Review**
```bash
# Quick content spot-check
grep -n "Member-" data/*/posts/daily/*.md | head -10
grep -n "https://" data/*/posts/daily/*.md | head -5
grep -n "## Fio" data/*/posts/daily/*.md | wc -l
```

### **API Usage Tracking**
```bash
# Monitor API call patterns
tail -f test_run.log | grep -i "api\|quota\|rate"
```

## 🎯 Next Steps After Testing

### **If All Tests Pass**
1. Document successful configuration
2. Create production deployment guide
3. Set up monitoring and alerting
4. Plan scaled processing workflows

### **If Issues Found**
1. Delegate complex fixes to Jules
2. Create specific issue reports
3. Update quality thresholds
4. Improve error handling

This comprehensive testing plan ensures egregora's API functionality works correctly while maintaining high content quality and privacy protection.