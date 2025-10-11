# 🔍 Egregora Quality Control Framework

## Overview
Comprehensive testing and validation framework for egregora post generation quality.

## 🎯 Quality Metrics

### 1. **Structural Compliance**
- [ ] **YAML Front Matter**: Valid Material for MkDocs format
  - Title format: `📩 {GROUP_NAME} — Diário de {DATE}`
  - Date in YYYY-MM-DD format
  - Language set to `pt-BR`
  - Authors contains `egregora`
  - Categories include `daily` and group slug
  - Summary in 1st person plural, ≤160 chars
- [ ] **Fio Structure**: 4-10 fios with descriptive titles
  - Format: `## Fio X — {contextual title}`
  - Each fio begins with 1-2 context sentences
  - Clear separation criteria (theme/time/participants/tone)

### 2. **Content Quality**
- [ ] **Voice Consistency**: 1st person plural ("nós") throughout
- [ ] **Attribution**: Every substantive sentence ends with (Nick) or (Member-XXXX)
- [ ] **Link Preservation**: All URLs appear at exact mention points
- [ ] **Contextualization**: Implicit meanings made explicit
- [ ] **Narrative Flow**: Group as collective mind, not external analysis

### 3. **Privacy & Security**
- [ ] **Anonymous IDs**: Only use provided Member-XXXX identifiers
- [ ] **Phone Number Detection**: No phone patterns in output
- [ ] **Name Sanitization**: No real names from message content
- [ ] **Email Protection**: No email addresses exposed

### 4. **Technical Accuracy**
- [ ] **Date Consistency**: Post date matches target date
- [ ] **Group Name**: Correct group identification
- [ ] **Media Handling**: Proper handling of `<Mídia oculta>` markers
- [ ] **Link Completeness**: Full URLs preserved, not shortened

## 🧪 Test Scenarios

### Scenario A: Basic Discussion
**Input**: Simple group conversation with 3-4 participants
**Expected**: 4-6 fios, clear attribution, natural flow

### Scenario B: Link-Heavy Content  
**Input**: Messages with multiple URLs and references
**Expected**: All links at exact mention points, proper context

### Scenario C: Media-Rich Content
**Input**: Messages with images, videos, documents
**Expected**: Explicit media mentions with attribution

### Scenario D: Long Complex Discussion
**Input**: Multi-hour conversation with topic shifts
**Expected**: 8-10 fios, clear transitions, tension resolution

### Scenario E: Conflict/Disagreement
**Input**: Messages with opposing viewpoints
**Expected**: Explicit tensions, multiple perspectives, resolution status

## 🔧 Automated Validation

### Privacy Checks
```python
# Test phone number detection
assert_no_match(r"\+\d{2}\s?\d{2}\s?\d{4,5}-?\d{4}", post_content)
assert_no_match(r"\b\d{4,5}-?\d{4}\b", post_content)
assert_no_match(r"\(\d{4}\)", post_content)
```

### Structure Validation
```python
# YAML front matter validation
assert post.startswith("---\n")
assert "title:" in yaml_section
assert "date:" in yaml_section
assert "lang: pt-BR" in yaml_section

# Fio structure validation
fio_count = len(re.findall(r"^## Fio \d+", post, re.MULTILINE))
assert 4 <= fio_count <= 10
```

### Attribution Validation
```python
# Every substantive sentence should end with attribution
sentences = extract_substantive_sentences(post)
for sentence in sentences:
    assert re.search(r"\([^)]+\)$", sentence.strip())
```

## 📊 Quality Scoring

### Content Quality Score (0-100)
- **Structure (25 points)**: YAML + Fio organization
- **Voice (25 points)**: Consistent 1st person plural
- **Attribution (25 points)**: Complete author tracking  
- **Context (25 points)**: Explicit subtext and tensions

### Privacy Score (Pass/Fail)
- **Phone Detection**: No phone patterns
- **Name Sanitization**: No real names
- **Anonymous IDs**: Only approved identifiers

### Technical Score (0-100)
- **Link Preservation (30 points)**: All URLs intact
- **Date Accuracy (20 points)**: Correct temporal reference
- **Media Handling (25 points)**: Proper media markers
- **Format Compliance (25 points)**: Valid Markdown + YAML

## 🎯 Quality Thresholds

### Production Ready
- Content Quality: ≥85/100
- Privacy Score: Pass (100%)
- Technical Score: ≥90/100

### Needs Review
- Content Quality: 70-84/100
- Privacy Score: Pass required
- Technical Score: 75-89/100

### Requires Revision
- Content Quality: <70/100
- Privacy Score: Fail
- Technical Score: <75/100

## 🔄 Testing Workflow

1. **Generate Post**: Run egregora with test data
2. **Structural Analysis**: Validate YAML and Fio structure
3. **Content Analysis**: Check voice, attribution, context
4. **Privacy Scan**: Run all privacy validation patterns
5. **Technical Validation**: Verify links, dates, media handling
6. **Quality Score**: Calculate composite score
7. **Human Review**: Final quality assessment for edge cases

## 🚨 Red Flags

### Immediate Rejection Criteria
- Privacy violation detected
- Missing YAML front matter
- No attribution in substantive content
- Links moved from original context
- External analysis voice instead of collective narrative

### Review Required
- Unusual fio count (<4 or >10)
- Low context explanation
- Excessive informal language
- Missing media handling
- Incomplete tension resolution

## 📝 Sample Quality Report

```
Post: 2025-10-03-rationality-club-latam.md
Generated: 2025-10-03 15:30:00

✅ PRIVACY SCAN: PASSED
✅ YAML STRUCTURE: VALID
✅ FIO COUNT: 6 (optimal range)
⚠️  ATTRIBUTION: 92% coverage (3 sentences missing)
✅ LINK PRESERVATION: 100% (8/8 links intact)
⚠️  CONTEXT LEVEL: Medium (some implicit tensions)

OVERALL SCORE: 87/100 (Production Ready)
RECOMMENDATION: Minor attribution cleanup needed
```

This framework provides comprehensive quality control for egregora's AI-generated content while ensuring privacy protection and technical accuracy.