---
name: django-structured-data
description: Use this skill when adding or auditing JSON-LD structured data in a Django project, including Organization, LocalBusiness, WebSite, BreadcrumbList, Article, FAQPage, Product, Service, Event, and medical or professional service schemas where appropriate.
---

# Django Structured Data Skill

## Objective

Add valid JSON-LD structured data to Django templates.

## Tasks

1. Identify the type of website and page.
2. Choose the correct schema type.
3. Add JSON-LD safely in the template.
4. Avoid fake or unsupported schema.
5. Match structured data to visible page content.
6. Add breadcrumbs when useful.
7. Add Organization or LocalBusiness globally where appropriate.
8. Add FAQPage only when FAQs are visible on the page.
9. Add Article only for real article/blog content.
10. Add Service schema for service pages when appropriate.

## Output

Return:

- Recommended schema types
- JSON-LD template snippet
- Context variables required
- View/model changes required
- Validation checklist

## Rules

- Do not invent reviews, ratings, prices, locations, or medical claims.
- Structured data must match the visible content.
- Prefer JSON-LD.
- Keep schema maintainable with template includes.