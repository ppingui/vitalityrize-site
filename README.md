# vitalityrize.me

The marketing and content site for **VitalityRise** (App Store: *Vitality Rise: Men's
Health*, id `6754820098`). Static HTML, served by GitHub Pages from `main` at the repo
root. Pushing to `main` deploys; there is no CI step.

## How it works

`build.py` is a stdlib-only generator. It reads page fragments from `src/pages/`, wraps
each in `src/_base.html`, and writes plain HTML to the repo root.

```bash
python3 build.py                    # regenerate every page + sitemap/robots/llms.txt
python3 -m http.server 8099         # then open http://localhost:8099
```

**Never edit the generated files at the repo root** — `index.html`, `about/index.html`
and friends are all overwritten on the next build. Edit the fragment in `src/pages/`.

### Writing a page

Every fragment opens with a JSON front-matter block:

```html
<!--meta
{
  "slug": "kegel-exercises-for-men",
  "lang": "en",
  "cluster": "kegels",
  "type": "article",
  "medical": true,
  "published": "2026-08-10",
  "updated": "2026-08-10",
  "title": "…",           // ≤62 chars (≤30 for ja) — build warns if over
  "description": "…",     // ≤160 chars (≤80 for ja)
  "h1": "…",
  "tldr": "…",            // renders as the "Short answer:" block
  "faq": [["Q", "A"], …]  // renders the FAQ section and FAQPage schema
}
-->
```

- `slug` is the full path. English pages sit at the root; localized ones carry their
  locale prefix, e.g. `"de/beckenbodentraining-maenner"`.
- `cluster` links translations of the same page. Every page in a cluster gets a
  reciprocal `hreflang` set plus `x-default` pointing at the English one, in both the
  `<head>` and `sitemap.xml`. A cluster without an English member is a build error.
- `type: "article"` adds a byline and `BreadcrumbList`; `medical: true` upgrades the
  schema to `MedicalWebPage` with `lastReviewed`.
- `{{cta:some_campaign}}` anywhere in the body expands to the App Store CTA block, in
  the page's language.

### Constants worth knowing

At the top of `build.py`:

- `SITE` — the only thing to change if the site ever moves to a brand-matching domain.
  Everything else (canonicals, hreflang, sitemap, `llms.txt`, `CNAME`) follows.
- `PRICE_*` — verified against App Store Connect on 2026-08-10 via
  `python3 scripts/asc.py subs` in the app repo. Re-verify before changing.
- `PROVIDER_TOKEN` — Apple campaign attribution token (App Store Connect → Analytics →
  Campaigns). Empty means App Store links carry no campaign params rather than broken
  ones.
- `ANALYTICS_TOKEN` — Cloudflare Web Analytics (cookieless). Empty means no analytics
  script at all.

## Assets

`make_assets.py` regenerates the favicon, apple-touch-icon, OG image and app screenshots
from the app repo next door (`../VitalityRise`). It needs Pillow; nothing else here does.

```bash
python3 make_assets.py
```

## After deploying

```bash
python3 submit_indexnow.py
```

Pings IndexNow so Bing — and therefore ChatGPT's retrieval — picks up changes without
waiting for a crawl. Run it *after* the push has gone live, since IndexNow fetches the
URLs. Google has no equivalent; submit `sitemap.xml` in Search Console instead.

## Editorial rules

This is health content about a sensitive subject, and the site's whole position is that
it is the honest one in a field that mostly isn't.

1. **Every clinical figure gets a named, linked source.** No "studies show".
2. **No treatment or cure claims**, in any language. The app is a general wellness app.
3. **Verify citations before publishing.** Author lists and DOIs get checked against
   Crossref or PubMed, not recalled from memory.
4. **The comparison page discloses that we make one of the apps**, and every competitor
   price is read from that app's own App Store listing on the day of publishing.
5. **No `aggregateRating` in schema** until the app has real ratings to report.
6. State the failure numbers. The 24.5% who didn't improve belong on the page next to
   the 40% who did.

## Files that predate this site

`jpgconverter-privacy.html` and `style.css` belong to a different app and are not part of
the build. Leave them alone. `privacy.html` and `terms.html` are generated redirect stubs
pointing at `/privacy/` and `/terms/`.
