---
name: django-sitemap-robots
description: Use this skill when adding, fixing, or auditing sitemap.xml and robots.txt in a Django project, especially for SEO indexability, crawl control, public pages, and production deployment.
---

# Django Sitemap and Robots Skill

## Objective

Implement or improve sitemap.xml and robots.txt for a Django project.

## Tasks

1. Check if `django.contrib.sitemaps` is installed.
2. Check if `django.contrib.sites` is needed.
3. Identify public models and public static pages.
4. Create sitemap classes for each public content type.
5. Add sitemap routes to the main `urls.py`.
6. Add a robots.txt route or static file.
7. Include the sitemap URL in robots.txt.
8. Exclude admin, dashboard, auth, internal, private, and webhook URLs.
9. Avoid blocking pages that should be indexed.
10. Add `noindex` where needed instead of relying only on robots.txt.

## Expected output

Provide:

- Code for `sitemaps.py`
- Code for `urls.py`
- Recommended `robots.txt`
- List of URLs included in sitemap
- List of URLs excluded from crawling/indexing
- Production testing checklist

## Django preference

Prefer native Django sitemap framework unless the project clearly needs another package.

## Testing checklist

- `/sitemap.xml` returns XML.
- `/robots.txt` returns plain text.
- Public pages appear in sitemap.
- Private/admin/dashboard pages do not appear in sitemap.
- robots.txt includes Sitemap line.
- No development domain appears in production sitemap.