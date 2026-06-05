---
name: django-meta-tags
description: Use this skill when implementing reusable SEO meta tags in Django templates, including title, meta description, canonical URL, Open Graph, Twitter cards, robots meta, and page-specific SEO blocks.
---

# Django Meta Tags Skill

## Objective

Create a reusable SEO metadata system for Django templates.

## Requirements

Implement a clean template structure using:

- `{% block title %}`
- `{% block meta_description %}`
- canonical URL block
- Open Graph tags
- Twitter card tags
- robots meta tag
- fallback values from settings or context processors

## Inspect

Check:

- `base.html`
- page templates
- views that pass context
- models that contain title, slug, description, image, updated_at
- URL naming and `get_absolute_url()`

## Recommended implementation

Prefer:

- Global SEO defaults in settings
- Page-specific context from views
- Model methods for SEO fields when appropriate
- Template blocks for overrides
- Absolute canonical URLs in production

## Output

Return:

1. Improved `base.html` head section
2. Example view context
3. Example model SEO methods
4. Template usage examples
5. Validation checklist

## Rules

- Every public page must have a unique title.
- Every important page should have a unique meta description.
- Canonical should point to the final production URL.
- Do not add keyword meta tags.
- Do not create duplicate Open Graph data.