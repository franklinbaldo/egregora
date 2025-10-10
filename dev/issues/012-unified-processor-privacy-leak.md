# Issue #012: Critical Privacy Leak in UnifiedProcessor

## Priority: Critical
## Effort: Medium
## Type: Security Bug

## Problem Description

**CRITICAL PRIVACY VULNERABILITY**: The UnifiedProcessor completely bypasses the anonymization system, sending raw phone numbers directly to the LLM. This violates the privacy-by-design architecture and exposes user phone numbers.

**Impact**: Last 4 digits of real phone numbers are included in generated newsletters, creating privacy risk.

## Current Behavior

### Broken Flow (UnifiedProcessor)
1. ❌ Raw transcript extracted with phone numbers: `+55 11 94529-4774`
2. ❌ No anonymization applied before LLM
3. ❌ LLM receives: `10:30 - +55 11 94529-4774: message`
4. ❌ System prompt instructs extraction of last 4 digits: `(4774)`
5. ❌ Newsletter contains partial phone numbers

### Expected Flow (Privacy-Safe)
1. ✅ Extract transcript
2. ✅ Apply anonymization: `+55 11 94529-4774` → `Member-A1B2`
3. ✅ Send to LLM: `10:30 - Member-A1B2: message`
4. ✅ Newsletter references: `(Member-A1B2)`

## Root Cause

The UnifiedProcessor was implemented without integrating the existing anonymization step:

```python
# src/egregora/processor.py:174-197 (BROKEN)
for target_date in target_dates:
    transcript = extract_transcript(source, target_date)  # Raw transcript
    newsletter = self._generate_newsletter(source, transcript, target_date)  # No anonymization!
```

## Solution

### 1. Integrate Anonymization in UnifiedProcessor

```python
def _generate_newsletter(self, source, transcript, target_date):
    from .pipeline import _prepare_transcripts
    
    # 1. Apply anonymization BEFORE sending to LLM
    transcripts = [(target_date, transcript)]
    anonymized_transcripts = _prepare_transcripts(transcripts, self.config)
    
    # 2. Build LLM input with anonymized data
    llm_input = build_llm_input(
        group_name=source.name,
        timezone=self.config.timezone,
        transcripts=anonymized_transcripts,  # Use anonymized!
        previous_newsletter=None,
        enrichment_section=None,
        rag_context=None,
    )
    
    # Rest of generation...
```

### 2. Update System Prompt

Remove phone number extraction instruction and ensure consistent anonymization:

```markdown
# Before (DANGEROUS)
Se NÃO houver nick, extrair os quatro dígitos finais do número: 
ex.: +55 11 94529-4774 → (4774)

# After (SAFE)
- Em CADA FRASE, colocar o identificador anônimo entre parênteses: (Member-ABCD)
- Se o remetente tiver nick reconhecível, pode usar: (Nick)
```

### 3. Privacy Validation

Add checks to ensure no phone numbers leak:

```python
def validate_newsletter_privacy(newsletter_text: str) -> bool:
    """Ensure newsletter doesn't contain phone number patterns."""
    
    # Check for phone number patterns
    phone_patterns = [
        r'\+\d{2}\s?\d{2}\s?\d{4,5}-?\d{4}',  # +55 11 94529-4774
        r'\(\d{4}\)',  # (4774) - last 4 digits
        r'\d{4,5}-?\d{4}',  # 94529-4774
    ]
    
    for pattern in phone_patterns:
        if re.search(pattern, newsletter_text):
            raise PrivacyViolationError(f"Phone pattern detected: {pattern}")
    
    return True
```

## Expected Benefits

1. **Privacy Protection**: No phone numbers leak to LLM or newsletters
2. **Compliance**: Maintains privacy-by-design architecture
3. **User Trust**: Ensures anonymization works as documented
4. **Security**: Prevents identification of participants

## Acceptance Criteria

- [ ] UnifiedProcessor applies anonymization before LLM calls
- [ ] No raw phone numbers sent to LLM
- [ ] Newsletter contains `Member-XXXX` references, not phone digits
- [ ] Privacy validation catches any leaks
- [ ] Tests verify anonymization works end-to-end
- [ ] System prompt updated to remove phone extraction instructions

## Files to Modify

- `src/egregora/processor.py` - Add anonymization step
- `src/egregora/prompts/system_instruction_base.md` - Update instructions
- `tests/test_unified_processor_anonymization.py` - Verify privacy protection

## Related Issues

- #046: UnifiedProcessor missing enrichment integration
- #009: Privacy & Security Enhancement