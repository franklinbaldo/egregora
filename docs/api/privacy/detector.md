# Privacy - PII Detector

Detect personally identifiable information (PII) in content.

> Privacy scope: egregora now enforces privacy exclusively by masking or redacting sensitive
> information **before** text is sent to the LLM. Downstream components such as the annotation
> store no longer attempt to detect or block PII at persistence time; use the detector during
> input processing when masking is required.

::: egregora.privacy.detector
    options:
      show_source: true
      show_root_heading: true
      members_order: source
      show_if_no_docstring: false
