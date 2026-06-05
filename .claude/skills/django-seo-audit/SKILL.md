---
name: django-seo-audit
description: Use this skill when reviewing a Django project for technical SEO issues, including templates, URLs, meta tags, canonical URLs, sitemap.xml, robots.txt, Open Graph, structured data, image alt text, performance, and indexability problems.
---

# Django SEO Audit Skill

You are auditing a Django project for technical SEO.

## Goals

Review the project and produce a practical SEO improvement plan focused on:

1. Page titles and meta descriptions
2. Canonical URLs
3. URL structure
4. Sitemap implementation
5. robots.txt
6. Open Graph and Twitter cards
7. Structured data with JSON-LD
8. Image alt attributes
9. Internal linking
10. Page speed and static/media handling
11. Mobile-first issues
12. Duplicate or thin pages
13. Indexability problems

## Django-specific files to inspect

Prioritize:

- `settings.py`
- `urls.py`
- app-level `urls.py`
- templates, especially `base.html`
- models with public pages
- views that render public pages
- static and media configuration
- sitemap-related files
- robots-related files

## Output format

Return:

1. Critical issues
2. Quick wins
3. Recommended code changes
4. Files to modify
5. Exact implementation steps
6. Testing checklist

## Rules

- Do not make changes without explaining them first.
- Prefer native Django features where possible.
- Avoid adding unnecessary dependencies.
- If a package is suggested, explain why it is worth adding.
- Assume the project is production-oriented.