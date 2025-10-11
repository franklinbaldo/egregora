#!/usr/bin/env python3
"""Quality control validation for egregora-generated posts."""

import re
import yaml
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import argparse


@dataclass
class QualityResult:
    """Quality assessment result for a post."""
    privacy_score: bool
    structure_score: int
    content_score: int
    technical_score: int
    issues: List[str]
    warnings: List[str]
    
    @property
    def overall_score(self) -> int:
        """Calculate weighted overall score."""
        if not self.privacy_score:
            return 0  # Privacy failure = immediate rejection
        return int((self.structure_score + self.content_score + self.technical_score) / 3)
    
    @property
    def status(self) -> str:
        """Determine post status based on scores."""
        if not self.privacy_score:
            return "REJECTED - Privacy Violation"
        elif self.overall_score >= 85:
            return "PRODUCTION READY"
        elif self.overall_score >= 70:
            return "NEEDS REVIEW"
        else:
            return "REQUIRES REVISION"


class PostQualityValidator:
    """Comprehensive quality validator for egregora posts."""
    
    # Privacy patterns (from egregora/privacy.py)
    PHONE_PATTERNS = [
        (r"\+\d{2}\s?\d{2}\s?\d{4,5}-?\d{4}", "international phone number"),
        (r"\b\d{4,5}-?\d{4}\b", "local phone number"),
        (r"\(\d{4}\)", "last four digits in parentheses"),
    ]
    
    def __init__(self):
        self.issues = []
        self.warnings = []
    
    def validate_post(self, post_path: Path) -> QualityResult:
        """Validate a single post file."""
        self.issues = []
        self.warnings = []
        
        content = post_path.read_text(encoding='utf-8')
        
        # Split YAML front matter and content
        yaml_section, post_content = self._extract_yaml_and_content(content)
        
        privacy_score = self._validate_privacy(content)
        structure_score = self._validate_structure(yaml_section, post_content)
        content_score = self._validate_content_quality(post_content)
        technical_score = self._validate_technical_aspects(yaml_section, post_content)
        
        return QualityResult(
            privacy_score=privacy_score,
            structure_score=structure_score,
            content_score=content_score,
            technical_score=technical_score,
            issues=self.issues.copy(),
            warnings=self.warnings.copy()
        )
    
    def _extract_yaml_and_content(self, content: str) -> Tuple[Optional[Dict], str]:
        """Extract and parse YAML front matter."""
        if not content.startswith('---\n'):
            self.issues.append("Missing YAML front matter")
            return None, content
        
        try:
            # Find end of YAML section
            yaml_end = content.find('\n---\n', 4)
            if yaml_end == -1:
                self.issues.append("Invalid YAML front matter format")
                return None, content
            
            yaml_text = content[4:yaml_end]
            yaml_data = yaml.safe_load(yaml_text)
            post_content = content[yaml_end + 5:]
            
            return yaml_data, post_content
            
        except yaml.YAMLError as e:
            self.issues.append(f"Invalid YAML syntax: {e}")
            return None, content
    
    def _validate_privacy(self, content: str) -> bool:
        """Validate privacy compliance."""
        for pattern, description in self.PHONE_PATTERNS:
            if re.search(pattern, content):
                self.issues.append(f"Privacy violation: {description} detected")
                return False
        return True
    
    def _validate_structure(self, yaml_data: Optional[Dict], content: str) -> int:
        """Validate YAML and fio structure (25 points max)."""
        score = 0
        
        # YAML validation (15 points)
        if yaml_data:
            # Title format (3 points)
            title = yaml_data.get('title', '')
            if re.match(r'📩 .+ — Diário de \d{4}-\d{2}-\d{2}', title):
                score += 3
            else:
                self.issues.append("Invalid title format")
            
            # Required fields (3 points each)
            required_fields = [
                ('date', r'\d{4}-\d{2}-\d{2}'),
                ('lang', 'pt-BR'),
                ('authors', lambda x: 'egregora' in x if isinstance(x, list) else False)
            ]
            
            for field, validator in required_fields:
                if field in yaml_data:
                    value = yaml_data[field]
                    if callable(validator):
                        if validator(value):
                            score += 3
                        else:
                            self.issues.append(f"Invalid {field} value")
                    elif isinstance(validator, str):
                        if value == validator:
                            score += 3
                        else:
                            self.issues.append(f"Invalid {field}: expected {validator}")
                    elif re.match(validator, str(value)):
                        score += 3
                    else:
                        self.issues.append(f"Invalid {field} format")
                else:
                    self.issues.append(f"Missing required field: {field}")
            
            # Categories validation (3 points)
            categories = yaml_data.get('categories', [])
            if 'daily' in categories and len(categories) >= 2:
                score += 3
            else:
                self.issues.append("Missing required categories")
        
        # Fio structure validation (10 points)
        fio_matches = re.findall(r'^## Fio \d+', content, re.MULTILINE)
        fio_count = len(fio_matches)
        
        if 4 <= fio_count <= 10:
            score += 10
        elif 3 <= fio_count <= 12:
            score += 7
            self.warnings.append(f"Unusual fio count: {fio_count} (optimal: 4-10)")
        else:
            score += 3
            self.issues.append(f"Poor fio count: {fio_count} (expected: 4-10)")
        
        return min(score, 25)
    
    def _validate_content_quality(self, content: str) -> int:
        """Validate content quality (25 points max)."""
        score = 0
        
        # Voice consistency - 1st person plural (8 points)
        plural_indicators = len(re.findall(r'\bnós\b|\bnosso\b|\bnossa\b|\bconosco\b', content, re.IGNORECASE))
        singular_indicators = len(re.findall(r'\beu\b|\bmeu\b|\bminha\b|\bcomigo\b', content, re.IGNORECASE))
        
        if plural_indicators > singular_indicators * 3:
            score += 8
        elif plural_indicators > singular_indicators:
            score += 5
            self.warnings.append("Mixed voice usage detected")
        else:
            score += 2
            self.issues.append("Inconsistent voice - not consistently 1st person plural")
        
        # Attribution checking (10 points)
        # Look for substantive sentences (not titles, not short phrases)
        sentences = re.findall(r'[^.!?]*[.!?]', content)
        substantive_sentences = [s for s in sentences if len(s.strip()) > 20 and not s.strip().startswith('#')]
        
        attributed_count = 0
        for sentence in substantive_sentences:
            if re.search(r'\([^)]+\)$', sentence.strip()):
                attributed_count += 1
        
        if substantive_sentences:
            attribution_rate = attributed_count / len(substantive_sentences)
            if attribution_rate >= 0.95:
                score += 10
            elif attribution_rate >= 0.85:
                score += 8
                self.warnings.append(f"Attribution coverage: {attribution_rate:.1%}")
            elif attribution_rate >= 0.70:
                score += 5
                self.issues.append(f"Low attribution coverage: {attribution_rate:.1%}")
            else:
                score += 2
                self.issues.append(f"Poor attribution coverage: {attribution_rate:.1%}")
        
        # Context and explanation quality (7 points)
        context_indicators = len(re.findall(r'\bporque\b|\bquando\b|\bcomo\b|\bentão\b|\bassim\b|\bpois\b', content, re.IGNORECASE))
        content_length = len(content.split())
        
        if content_length > 0:
            context_density = context_indicators / content_length
            if context_density >= 0.02:
                score += 7
            elif context_density >= 0.015:
                score += 5
                self.warnings.append("Medium context density")
            else:
                score += 3
                self.issues.append("Low context/explanation density")
        
        return min(score, 25)
    
    def _validate_technical_aspects(self, yaml_data: Optional[Dict], content: str) -> int:
        """Validate technical aspects (25 points max)."""
        score = 0
        
        # Link preservation (10 points)
        urls = re.findall(r'https?://[^\s]+', content)
        if urls:
            # Check if links appear to be in context (not grouped at end)
            content_lines = content.split('\n')
            link_distribution = []
            for i, line in enumerate(content_lines):
                if 'http' in line:
                    link_distribution.append(i / len(content_lines))
            
            if len(link_distribution) > 1:
                # Good distribution across content
                score += 10
            elif link_distribution and link_distribution[0] < 0.8:
                # At least not all at the end
                score += 7
                self.warnings.append("Links might be grouped together")
            else:
                score += 4
                self.issues.append("Links appear to be moved from original context")
        else:
            score += 10  # No links to validate
        
        # Date consistency (5 points)
        if yaml_data and 'date' in yaml_data:
            yaml_date = yaml_data['date']
            title = yaml_data.get('title', '')
            if str(yaml_date) in title:
                score += 5
            else:
                self.issues.append("Date inconsistency between YAML and title")
        
        # Media handling (5 points)
        media_mentions = re.findall(r'<Mídia oculta>|mídia sem descrição', content, re.IGNORECASE)
        if content.count('mídia') > 0:
            if any('enviamos mídia' in content.lower() for _ in media_mentions):
                score += 5
            else:
                score += 3
                self.warnings.append("Media mentions might need better handling")
        else:
            score += 5  # No media to validate
        
        # Markdown format compliance (5 points)
        if content.count('#') >= 4:  # Has headers
            score += 5
        else:
            score += 2
            self.issues.append("Insufficient header structure")
        
        return min(score, 25)
    
    def generate_report(self, result: QualityResult, post_name: str) -> str:
        """Generate a human-readable quality report."""
        report = f"""
🔍 QUALITY CONTROL REPORT
Post: {post_name}
Status: {result.status}
Overall Score: {result.overall_score}/100

DETAILED SCORES:
{'✅' if result.privacy_score else '❌'} Privacy: {'PASS' if result.privacy_score else 'FAIL'}
📊 Structure: {result.structure_score}/25
📝 Content: {result.content_score}/25  
🔧 Technical: {result.technical_score}/25

"""
        if result.issues:
            report += "❌ ISSUES:\n"
            for issue in result.issues:
                report += f"  • {issue}\n"
            report += "\n"
        
        if result.warnings:
            report += "⚠️ WARNINGS:\n"
            for warning in result.warnings:
                report += f"  • {warning}\n"
            report += "\n"
        
        if result.overall_score >= 85:
            report += "✅ RECOMMENDATION: Ready for production\n"
        elif result.overall_score >= 70:
            report += "🔄 RECOMMENDATION: Needs minor review\n"
        else:
            report += "🔧 RECOMMENDATION: Requires revision\n"
        
        return report


def main():
    """CLI interface for post quality validation."""
    parser = argparse.ArgumentParser(description="Validate egregora post quality")
    parser.add_argument("post_path", type=Path, help="Path to post file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    if not args.post_path.exists():
        print(f"Error: File not found: {args.post_path}")
        return 1
    
    validator = PostQualityValidator()
    result = validator.validate_post(args.post_path)
    
    print(validator.generate_report(result, args.post_path.name))
    
    # Exit code based on quality
    if not result.privacy_score:
        return 2  # Privacy violation
    elif result.overall_score < 70:
        return 1  # Needs major revision
    else:
        return 0  # Acceptable quality


if __name__ == "__main__":
    exit(main())