# Egrégora Documentation Design Review

This review captures the current state of the documentation site and highlights opportunities to improve clarity, visual hierarchy, and contributor workflows. The goal is to make the multi-language experience intuitive for newcomers while keeping maintenance overhead low for the core team.

## Current Strengths

- **Content depth** – The developer notes offer candid rationales, implementation details, and migration plans that are valuable for onboarding engineers.
- **Report automation** – Daily, weekly, and monthly newsletters are generated from the WhatsApp pipeline, ensuring stakeholders receive timely updates without manual work.
- **Privacy narrative** – End-user explanations around anonymisation and consent provide a trustworthy baseline for community members.

## Pain Points

- **Navigation density** – Mixed technical and operational topics create long menus that make it hard to find audience-specific information.
- **Language mismatch** – Portuguese and English documents coexist without structure, confusing search, SEO, and cross-linking.
- **Report discoverability** – Generated newsletters live deep in the tree and lack entry pages that explain their context or current availability.

## Recommendations

### 1. Segment by Audience
- Split the menu into **User Guide** and **Developer Guide**, keeping homepages for each with curated highlights.
- Promote quick links for the most accessed tasks (e.g., anonymisation steps, export naming) at the top of each section.

### 2. Polish Report Landing Pages
- Add short blurbs describing what each report frequency represents and who should read it.
- Display the latest issue directly on the landing page, with a fallback message when no reports exist.

### 3. Expand Localisation Workflow
- Adopt a shared glossary to keep technical terms consistent across languages.
- Track translation status per file to make it easy for contributors to identify missing pages.

### 4. Visual Enhancements
- Use hero blocks or callouts on the home page to summarise the project mission.
- Introduce timeline or card layouts for release notes and reports once data volume increases.

### 5. Contributor Experience
- Document the build process, preview commands, and translation guidelines in a dedicated contributor page.
- Encourage small, frequent documentation pull requests to keep both languages in sync.

## Next Steps

1. Gather feedback from the community on which sections are most valuable.
2. Prioritise translation of user-facing guides before developer deep-dives.
3. Iterate on the navigation and theming once report automation is stable across languages.

These improvements will help Egrégora scale from a single-language knowledge base into a multilingual hub that serves organisers, analysts, and developers alike.
