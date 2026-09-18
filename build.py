#!/usr/bin/env python3
"""Static site generator for vitalityrize.me.

Stdlib only. Reads page fragments from src/pages/*.html, wraps them in
src/_base.html, and writes plain HTML to the repo root so GitHub Pages can
serve it with no build step. Run: python3 build.py

Ported from trysilex.com's generator. The differences that matter here:
  * multilingual — a fragment declares its own `lang` and a `cluster` id, and
    every page in a cluster gets a reciprocal hreflang set plus x-default;
  * MedicalWebPage schema on the evidence pages, since this is health content;
  * a standing medical-safety block instead of Silex's crisis helplines.
"""

from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "src"
PAGES = SRC / "pages"

# The one constant to change if the site ever moves to a brand-matching domain.
SITE = "https://www.vitalityrize.me"
BRAND = "VitalityRise"
BRAND_FULL = "VitalityRise — Men's Pelvic Floor Training"
APP_ID = "6754820098"
AUTHOR = "Kyrylo Lozovyi"
COMPANY = "VITALITY RISE LLC"
EMAIL = "support@vitalityrize.me"

# One Person node, referenced by @id from every page's author and the
# Organization's founder, so search engines see one entity rather than a name
# string repeated 40 times. trysilex.com carries the same @id for the same
# reason — it is the same person.
PERSON_ID = f"{SITE}/#kyrylo"
PERSON_SAME_AS = [
    "https://github.com/ppingui",
    "https://apps.apple.com/us/developer/vitality-rise-llc/id1850294300",
    "https://trysilex.com/about/",
]
SISTER_SITE = ("https://trysilex.com/", "Silex")

# Prices verified against App Store Connect on 2026-08-10 (US storefront) via
# `python3 scripts/asc.py subs` in the app repo. Re-verify before editing.
PRICE_WEEKLY = "4.99"
PRICE_MONTHLY = "9.99"
PRICE_YEARLY = "34.99"
PRICE_LIFETIME = "99.99"

# Apple provider token from App Store Connect (Analytics → Campaigns). Until it
# is filled in, links carry no campaign params rather than broken ones.
PROVIDER_TOKEN = ""

# Cloudflare Web Analytics beacon token (cookieless). Empty = no analytics.
ANALYTICS_TOKEN = ""

BUILD_DATE = "2026-08-10"

# The pre-rebuild flat URLs. GitHub Pages has no redirect mechanism, so these
# stay as canonical-tag stubs pointing at their replacements. `jpgconverter-
# privacy.html` and `style.css` predate this site and belong to another app —
# leave both alone.
REDIRECTS = {
    "privacy.html": "/privacy/",
    "terms.html": "/terms/",
}

# --- languages ----------------------------------------------------------------
# Only languages with real, human-quality pages belong here. A locale with thin
# machine copy costs more in duplicate-content risk than it earns in traffic.

LANGS = {
    "en": {"hreflang": "en", "name": "English"},
    "de": {"hreflang": "de", "name": "Deutsch"},
    "es": {"hreflang": "es-ES", "name": "Español"},
    "fr": {"hreflang": "fr", "name": "Français"},
    "pt": {"hreflang": "pt-BR", "name": "Português"},
    "ja": {"hreflang": "ja", "name": "日本語"},
}

NAV = {
    "en": [
        ("/kegel-exercises-for-men/", "Kegels for men"),
        ("/pelvic-floor-exercises-erectile-dysfunction/", "ED evidence"),
        ("/guides/", "All guides"),
        ("/pelvic-floor-self-check/", "Self-check"),
    ],
    "de": [
        ("/de/beckenbodentraining-maenner/", "Beckenboden"),
        ("/de/beckenbodentraining-erektionsstoerung/", "Erektion"),
    ],
    "es": [
        ("/es/ejercicios-kegel-hombres/", "Kegel"),
        ("/es/suelo-pelvico-disfuncion-erectil/", "Erección"),
        ("/es/ejercicios-eyaculacion-precoz/", "Eyaculación precoz"),
    ],
    "fr": [
        ("/fr/exercices-kegel-homme/", "Kegel"),
        ("/fr/perinee-dysfonction-erectile/", "Érection"),
    ],
    "pt": [
        ("/pt/exercicios-kegel-homens/", "Kegel"),
        ("/pt/assoalho-pelvico-disfuncao-eretil/", "Ereção"),
    ],
    "ja": [
        ("/ja/kegel-exercise-men/", "骨盤底筋"),
        ("/ja/kotsubanteikin-ed/", "ED"),
    ],
}

UI = {
    "en": {
        "skip": "Skip to content",
        "home": "Home",
        "about": "About",
        "method": "Methodology",
        "standards": "Editorial standards",
        "support": "Support",
        "privacy": "Privacy",
        "terms": "Terms",
        "cta_h": "Train the muscle. Privately.",
        "cta_p": "Guided pelvic floor sessions and a 30-day plan on your iPhone. "
                 "No account, and your answers and progress never leave the device.",
        "cta_btn": "Get VitalityRise on iPhone",
        "safety_h": "Before you start",
        "faq_h": "Common questions",
        "tldr": "Short answer:",
        "byline_by": "By",
        "byline_upd": "Updated",
        "langs": "Language",
        "disclaimer":
            "VitalityRise is a general wellness app. It is not medical care, and it "
            "does not diagnose, treat or cure any condition. Erectile difficulty that "
            "persists for more than a few months is worth a doctor's visit — it is "
            "sometimes the first sign of a cardiovascular or hormonal problem.",
    },
    "de": {
        "skip": "Zum Inhalt springen",
        "home": "Start", "about": "Über uns", "method": "Methodik", "standards": "Redaktionsgrundsätze",
        "support": "Hilfe", "privacy": "Datenschutz", "terms": "AGB",
        "cta_h": "Trainieren Sie den Muskel. Privat.",
        "cta_p": "Geführte Beckenbodeneinheiten und ein 30-Tage-Plan auf Ihrem iPhone. "
                 "Kein Konto, und Ihre Antworten und Fortschritte verlassen das Gerät nie.",
        "cta_btn": "VitalityRise fürs iPhone laden",
        "safety_h": "Bevor Sie beginnen",
        "faq_h": "Häufige Fragen",
        "tldr": "Kurze Antwort:",
        "byline_by": "Von", "byline_upd": "Aktualisiert", "langs": "Sprache",
        "disclaimer":
            "VitalityRise ist eine allgemeine Wellness-App. Sie ist keine medizinische "
            "Behandlung und stellt keine Diagnose. Erektionsprobleme, die länger als "
            "einige Monate anhalten, gehören ärztlich abgeklärt — sie sind manchmal das "
            "erste Anzeichen eines Herz-Kreislauf- oder Hormonproblems.",
    },
    "es": {
        "skip": "Ir al contenido",
        "home": "Inicio", "about": "Quiénes somos", "method": "Metodología", "standards": "Criterios editoriales",
        "support": "Ayuda", "privacy": "Privacidad", "terms": "Términos",
        "cta_h": "Entrena el músculo. En privado.",
        "cta_p": "Sesiones guiadas de suelo pélvico y un plan de 30 días en tu iPhone. "
                 "Sin cuenta: tus respuestas y tu progreso nunca salen del dispositivo.",
        "cta_btn": "Consigue VitalityRise para iPhone",
        "safety_h": "Antes de empezar",
        "faq_h": "Preguntas frecuentes",
        "tldr": "Respuesta corta:",
        "byline_by": "Por", "byline_upd": "Actualizado", "langs": "Idioma",
        "disclaimer":
            "VitalityRise es una app de bienestar general. No es atención médica y no "
            "diagnostica ni trata ninguna enfermedad. Una dificultad de erección que dura "
            "más de unos meses merece una consulta médica: a veces es el primer signo de "
            "un problema cardiovascular u hormonal.",
    },
    "fr": {
        "skip": "Aller au contenu",
        "home": "Accueil", "about": "À propos", "method": "Méthodologie", "standards": "Charte éditoriale",
        "support": "Aide", "privacy": "Confidentialité", "terms": "Conditions",
        "cta_h": "Entraînez le muscle. En privé.",
        "cta_p": "Des séances guidées du périnée et un plan de 30 jours sur votre iPhone. "
                 "Sans compte : vos réponses et votre progression ne quittent jamais l'appareil.",
        "cta_btn": "Obtenir VitalityRise sur iPhone",
        "safety_h": "Avant de commencer",
        "faq_h": "Questions fréquentes",
        "tldr": "Réponse courte :",
        "byline_by": "Par", "byline_upd": "Mis à jour", "langs": "Langue",
        "disclaimer":
            "VitalityRise est une application de bien-être général. Ce n'est pas un soin "
            "médical et elle ne diagnostique ni ne traite aucune pathologie. Des troubles "
            "de l'érection qui durent plus de quelques mois méritent une consultation : "
            "ils sont parfois le premier signe d'un problème cardiovasculaire ou hormonal.",
    },
    "pt": {
        "skip": "Ir para o conteúdo",
        "home": "Início", "about": "Sobre", "method": "Metodologia", "standards": "Padrões editoriais",
        "support": "Suporte", "privacy": "Privacidade", "terms": "Termos",
        "cta_h": "Treine o músculo. Com privacidade.",
        "cta_p": "Sessões guiadas de assoalho pélvico e um plano de 30 dias no seu iPhone. "
                 "Sem conta: suas respostas e seu progresso nunca saem do aparelho.",
        "cta_btn": "Baixar o VitalityRise para iPhone",
        "safety_h": "Antes de começar",
        "faq_h": "Perguntas frequentes",
        "tldr": "Resposta curta:",
        "byline_by": "Por", "byline_upd": "Atualizado", "langs": "Idioma",
        "disclaimer":
            "O VitalityRise é um app de bem-estar geral. Não é atendimento médico e não "
            "diagnostica nem trata nenhuma condição. Dificuldade de ereção que persiste "
            "por mais de alguns meses merece consulta médica — às vezes é o primeiro sinal "
            "de um problema cardiovascular ou hormonal.",
    },
    "ja": {
        "skip": "本文へスキップ",
        "home": "ホーム", "about": "運営者", "method": "根拠", "standards": "編集方針",
        "support": "サポート", "privacy": "プライバシー", "terms": "利用規約",
        "cta_h": "筋肉を鍛える。誰にも知られずに。",
        "cta_p": "ガイド付きの骨盤底筋セッションと30日プランを iPhone 上で。"
                 "アカウント不要で、回答と進捗が端末を出ることはありません。",
        "cta_btn": "iPhone で VitalityRise を入手",
        "safety_h": "はじめる前に",
        "faq_h": "よくある質問",
        "tldr": "結論:",
        "byline_by": "著者", "byline_upd": "更新", "langs": "言語",
        "disclaimer":
            "VitalityRise は一般的なウェルネスアプリです。医療行為ではなく、いかなる疾患の診断・"
            "治療も行いません。数か月以上続く勃起の問題は受診を検討してください。心血管や"
            "ホルモンの問題の最初のサインであることがあります。",
    },
}


def app_store_url(campaign: str) -> str:
    """App Store link, with campaign attribution when the provider token is set."""
    base = f"https://apps.apple.com/app/id{APP_ID}"
    if PROVIDER_TOKEN:
        return f"{base}?pt={PROVIDER_TOKEN}&ct={campaign}&mt=8"
    return f"{base}?mt=8"


# --- standing safety block ----------------------------------------------------
# Health content carries an obligation the gambling site discharged with helpline
# numbers. Here it is the referral advice: erectile difficulty is frequently a
# vascular symptom before it is anything else, and the site says so on every page.

SEE_A_DOCTOR = {
    "en": [
        "Erectile difficulty that has lasted more than three months, or that came on "
        "suddenly",
        "Chest pain, breathlessness or leg pain on exertion — ED shares its plumbing "
        "with the heart, and often shows up first",
        "Pain during erection, a curve that is new or worsening, or any pain in the "
        "pelvis or perineum",
        "A pelvic floor that will not relax, or urinary symptoms — these need a pelvic "
        "health physiotherapist, and strengthening alone can make them worse",
        "Low mood, low libido or fatigue that arrived together — worth a hormone and "
        "mental-health check",
    ],
    "de": [
        "Erektionsprobleme, die länger als drei Monate bestehen oder plötzlich auftraten",
        "Brustschmerz, Atemnot oder Beinschmerz bei Belastung — Erektionsstörungen teilen "
        "sich die Gefäße mit dem Herzen und zeigen sich oft zuerst",
        "Schmerzen bei der Erektion, eine neue oder zunehmende Krümmung, Schmerzen im "
        "Becken oder Damm",
        "Ein Beckenboden, der nicht loslässt, oder Blasenbeschwerden — dafür braucht es "
        "Beckenboden-Physiotherapie; reines Kräftigen kann es verschlimmern",
        "Niedergeschlagenheit, wenig Lust oder Erschöpfung gleichzeitig — Hormon- und "
        "psychische Abklärung sinnvoll",
    ],
    "es": [
        "Dificultad de erección de más de tres meses, o de aparición repentina",
        "Dolor torácico, falta de aire o dolor en las piernas al esforzarte: la disfunción "
        "eréctil comparte circulación con el corazón y suele aparecer antes",
        "Dolor durante la erección, una curvatura nueva o que empeora, o dolor pélvico o "
        "perineal",
        "Un suelo pélvico que no se relaja, o síntomas urinarios: eso requiere "
        "fisioterapia de suelo pélvico, y fortalecer solo puede empeorarlo",
        "Ánimo bajo, poco deseo o fatiga que aparecieron juntos: conviene revisar hormonas "
        "y salud mental",
    ],
    "fr": [
        "Des troubles de l'érection depuis plus de trois mois, ou apparus brutalement",
        "Douleur thoracique, essoufflement ou douleur aux jambes à l'effort — la dysfonction "
        "érectile partage sa circulation avec le cœur et se manifeste souvent en premier",
        "Douleur pendant l'érection, une courbure nouvelle ou qui s'aggrave, ou une douleur "
        "du bassin ou du périnée",
        "Un périnée qui ne se relâche pas, ou des symptômes urinaires — cela relève d'un "
        "kinésithérapeute périnéal ; le seul renforcement peut aggraver les choses",
        "Moral bas, libido basse ou fatigue apparus ensemble — un bilan hormonal et "
        "psychique est justifié",
    ],
    "pt": [
        "Dificuldade de ereção há mais de três meses, ou que começou de repente",
        "Dor no peito, falta de ar ou dor nas pernas ao esforço — a disfunção erétil "
        "compartilha a circulação com o coração e costuma aparecer antes",
        "Dor durante a ereção, uma curvatura nova ou que piora, ou dor na pelve ou no períneo",
        "Um assoalho pélvico que não relaxa, ou sintomas urinários — isso pede fisioterapia "
        "pélvica; só fortalecer pode piorar",
        "Humor baixo, libido baixa ou cansaço que surgiram juntos — vale checar hormônios e "
        "saúde mental",
    ],
    "ja": [
        "3か月以上続く、または突然始まった勃起の問題",
        "運動時の胸痛・息切れ・脚の痛み — ED は心臓と血管を共有しており、先に現れることが多い",
        "勃起時の痛み、新たに生じた・悪化する湾曲、骨盤や会陰部の痛み",
        "緩まない骨盤底、または排尿の症状 — 骨盤底理学療法が必要で、締める練習だけでは悪化しうる",
        "気分の落ち込み・性欲低下・倦怠感が同時に出た場合 — ホルモンとメンタルの評価を",
    ],
}


def safety_block(lang: str) -> str:
    rows = "\n".join(f"      <li>{item}</li>" for item in SEE_A_DOCTOR[lang])
    return (
        '  <aside class="safety" aria-label="' + html.escape(UI[lang]["safety_h"]) + '">\n'
        f'    <h2>{UI[lang]["safety_h"]}</h2>\n'
        f'    <p>{UI[lang]["disclaimer"]}</p>\n'
        f"    <ul>\n{rows}\n    </ul>\n"
        "  </aside>"
    )


CTA_NOTE = {
    "en": f"iPhone · iOS 17+ · ${PRICE_YEARLY}/year with a 3-day free trial",
    "de": f"iPhone · iOS 17+ · {PRICE_YEARLY} $/Jahr mit 3 Tagen gratis",
    "es": f"iPhone · iOS 17+ · {PRICE_YEARLY} $/año con 3 días gratis",
    "fr": f"iPhone · iOS 17+ · {PRICE_YEARLY} $/an avec 3 jours offerts",
    "pt": f"iPhone · iOS 17+ · US$ {PRICE_YEARLY}/ano com 3 dias grátis",
    "ja": f"iPhone · iOS 17+ · 年額 ${PRICE_YEARLY}・3日間無料",
}


def cta_block(campaign: str, lang: str) -> str:
    u = UI[lang]
    return (
        f'  <section class="cta">\n    <h2>{u["cta_h"]}</h2>\n'
        f'    <p>{u["cta_p"]}</p>\n'
        f'    <p><a class="btn" href="{app_store_url(campaign)}">{u["cta_btn"]}</a></p>\n'
        f'    <p class="cta-note">{CTA_NOTE[lang]}</p>\n  </section>'
    )


# --- template plumbing --------------------------------------------------------

META_RE = re.compile(r"^<!--meta\s*(\{.*?\})\s*-->\s*", re.DOTALL)
SHORTCODE_RE = re.compile(r"\{\{cta:([a-z0-9_]+)\}\}")


def parse_fragment(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8")
    m = META_RE.match(raw)
    if not m:
        raise SystemExit(f"{path.name}: missing leading <!--meta {{...}} --> block")
    meta = json.loads(m.group(1))
    for key in ("slug", "title", "description", "h1"):
        if key not in meta:
            raise SystemExit(f"{path.name}: meta is missing '{key}'")
    meta.setdefault("lang", "en")
    if meta["lang"] not in LANGS:
        raise SystemExit(f"{path.name}: unknown lang {meta['lang']!r}")
    # Google truncates around these lengths. CJK renders roughly twice as wide
    # per character, so the budget there is halved.
    wide = meta["lang"] in ("ja",)
    t_max, d_max = (30, 80) if wide else (62, 160)
    if len(meta["title"]) > t_max:
        print(f"  ! {path.name}: title is {len(meta['title'])} chars (max {t_max})")
    if len(meta["description"]) > d_max:
        print(f"  ! {path.name}: description is {len(meta['description'])} "
              f"chars (max {d_max})")
    return meta, raw[m.end():]


def canonical_for(slug: str) -> str:
    return f"{SITE}/" if slug == "" else f"{SITE}/{slug}/"


def nav_html(meta: dict) -> str:
    items = []
    for href, label in NAV[meta["lang"]]:
        cur = ' aria-current="page"' if href.strip("/") == meta["slug"] else ""
        items.append(f'<a href="{href}"{cur}>{label}</a>')
    return "".join(items)


def alternates_html(meta: dict, clusters: dict) -> str:
    """Reciprocal hreflang for every page in this translation cluster."""
    cluster = meta.get("cluster")
    if not cluster or len(clusters.get(cluster, [])) < 2:
        return ""
    out = []
    for peer in sorted(clusters[cluster], key=lambda m: m["lang"]):
        tag = LANGS[peer["lang"]]["hreflang"]
        out.append(f'<link rel="alternate" hreflang="{tag}" '
                   f'href="{canonical_for(peer["slug"])}">')
        if peer["lang"] == "en":
            out.append('<link rel="alternate" hreflang="x-default" '
                       f'href="{canonical_for(peer["slug"])}">')
    return "\n".join(out) + "\n"


def langswitch_html(meta: dict, clusters: dict) -> str:
    cluster = meta.get("cluster")
    peers = clusters.get(cluster, [])
    if len(peers) < 2:
        return ""
    links = []
    for peer in sorted(peers, key=lambda m: m["lang"] != "en"):
        name = LANGS[peer["lang"]]["name"]
        if peer["slug"] == meta["slug"]:
            links.append(f'<span aria-current="true">{name}</span>')
        else:
            links.append(f'<a lang="{LANGS[peer["lang"]]["hreflang"]}" '
                         f'hreflang="{LANGS[peer["lang"]]["hreflang"]}" '
                         f'href="{canonical_for(peer["slug"])}">{name}</a>')
    return (f'<nav class="langs" aria-label="{html.escape(UI[meta["lang"]]["langs"])}">'
            + "".join(links) + "</nav>")


def faq_html(meta: dict) -> str:
    faq = meta.get("faq") or []
    if not faq:
        return ""
    rows = "\n".join(
        f"    <h3>{html.escape(q)}</h3>\n    <p>{a}</p>" for q, a in faq
    )
    return ('  <section class="faq" id="faq">\n'
            f'    <h2>{UI[meta["lang"]]["faq_h"]}</h2>\n{rows}\n  </section>')


def byline_html(meta: dict) -> str:
    if meta.get("type") != "article":
        return ""
    u = UI[meta["lang"]]
    about = "/about/"  # one About page, English, shared by every locale
    pub, upd = meta["published"], meta.get("updated", meta["published"])
    updated = "" if pub == upd else \
        f' · {u["byline_upd"]} <time datetime="{upd}">{pretty(upd, meta["lang"])}</time>'
    return (f'  <p class="byline">{u["byline_by"]} <a rel="author" href="{about}">'
            f'{AUTHOR}</a> · <time datetime="{pub}">{pretty(pub, meta["lang"])}</time>'
            f"{updated}</p>")


MONTHS = {
    "en": ("January", "February", "March", "April", "May", "June", "July",
           "August", "September", "October", "November", "December"),
    "de": ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
           "August", "September", "Oktober", "November", "Dezember"),
    "es": ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
           "agosto", "septiembre", "octubre", "noviembre", "diciembre"),
    "fr": ("janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"),
    "pt": ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
           "agosto", "setembro", "outubro", "novembro", "dezembro"),
}


def pretty(iso: str, lang: str = "en") -> str:
    y, m, d = iso.split("-")
    if lang == "ja":
        return f"{y}年{int(m)}月{int(d)}日"
    month = MONTHS[lang][int(m) - 1]
    if lang == "en":
        return f"{month} {int(d)}, {y}"
    if lang in ("es", "pt"):
        return f"{int(d)} de {month} de {y}"
    if lang == "fr":
        return f"{int(d)} {month} {y}"
    return f"{int(d)}. {month} {y}"


def jsonld_for(meta: dict) -> str:
    person = {
        "@type": "Person",
        "@id": PERSON_ID,
        "name": AUTHOR,
        "url": f"{SITE}/about/",
        "jobTitle": "Independent iOS developer",
        "worksFor": {"@id": f"{SITE}/#org"},
        "sameAs": PERSON_SAME_AS,
    }
    org = {
        "@type": "Organization",
        "@id": f"{SITE}/#org",
        "name": COMPANY,
        "alternateName": BRAND,
        "url": SITE,
        "founder": {"@id": PERSON_ID},
        "email": EMAIL,
    }
    graph: list[dict] = [person, org]

    # Every locale homepage describes the same site and the same app, so they
    # share the @id nodes rather than each minting its own entity.
    if meta["slug"] == "" or meta["slug"] == meta["lang"]:
        graph += [
            {
                "@type": "WebSite",
                "@id": f"{SITE}/#website",
                "url": SITE,
                "name": BRAND_FULL,
                "publisher": {"@id": f"{SITE}/#org"},
            },
            {
                "@type": "SoftwareApplication",
                "@id": f"{SITE}/#app",
                "name": "Vitality Rise: Men's Health",
                "alternateName": BRAND,
                "operatingSystem": "iOS 17.0 or later",
                "applicationCategory": "HealthApplication",
                "url": app_store_url("schema"),
                "author": {"@id": f"{SITE}/#org"},
                # No aggregateRating: the app has too few App Store ratings to
                # state one honestly, and inventing one is a manual-action risk.
                "offers": [
                    {"@type": "Offer", "price": PRICE_WEEKLY, "priceCurrency": "USD",
                     "name": "Weekly"},
                    {"@type": "Offer", "price": PRICE_MONTHLY, "priceCurrency": "USD",
                     "name": "Monthly, 3-day free trial"},
                    {"@type": "Offer", "price": PRICE_YEARLY, "priceCurrency": "USD",
                     "name": "Yearly, 3-day free trial"},
                    {"@type": "Offer", "price": PRICE_LIFETIME, "priceCurrency": "USD",
                     "name": "Lifetime"},
                ],
            },
        ]

    if meta.get("type") == "article":
        page_type = "MedicalWebPage" if meta.get("medical") else "Article"
        node = {
            "@type": page_type,
            "@id": canonical_for(meta["slug"]) + "#article",
            "name" if meta.get("medical") else "headline": meta["h1"],
            "description": meta["description"],
            "inLanguage": LANGS[meta["lang"]]["hreflang"],
            "datePublished": meta["published"],
            "dateModified": meta.get("updated", meta["published"]),
            "author": {"@id": PERSON_ID},
            "publisher": {"@id": f"{SITE}/#org"},
            "mainEntityOfPage": canonical_for(meta["slug"]),
        }
        if meta.get("medical"):
            node["lastReviewed"] = meta.get("updated", meta["published"])
            node["audience"] = {"@type": "MedicalAudience",
                                "audienceType": "Patient"}
        graph.append(node)
        graph.append({
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": UI[meta["lang"]]["home"],
                 "item": SITE},
                {"@type": "ListItem", "position": 2, "name": meta["h1"],
                 "item": canonical_for(meta["slug"])},
            ],
        })

    if meta.get("faq"):
        graph.append({
            "@type": "FAQPage",
            "inLanguage": LANGS[meta["lang"]]["hreflang"],
            "mainEntity": [
                {"@type": "Question", "name": q,
                 "acceptedAnswer": {"@type": "Answer",
                                    "text": re.sub("<[^>]+>", "", a)}}
                for q, a in meta["faq"]
            ],
        })

    payload = {"@context": "https://schema.org", "@graph": graph}
    return ('<script type="application/ld+json">'
            + json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
            + "</script>")


def footer_nav(lang: str) -> str:
    u = UI[lang]
    home = "/" if lang == "en" else f"/{lang}/"
    return "".join(
        f'<a href="{href}">{label}</a>'
        for href, label in (
            (home, u["home"]),
            ("/about/", u["about"]),
            ("/methodology/", u["method"]),
            ("/editorial-standards/", u["standards"]),
            ("/support/", u["support"]),
            ("/privacy/", u["privacy"]),
            ("/terms/", u["terms"]),
        )
    )


def render(meta: dict, body: str, template: str, clusters: dict) -> str:
    lang = meta["lang"]
    body = SHORTCODE_RE.sub(lambda m: cta_block(m.group(1), lang), body)
    tldr = meta.get("tldr")
    tldr_html = (f'  <div class="tldr"><p><strong>{UI[lang]["tldr"]}</strong> '
                 f"{tldr}</p></div>\n" if tldr else "")
    analytics = (
        f'<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
        f'data-cf-beacon=\'{{"token": "{ANALYTICS_TOKEN}"}}\'></script>'
        if ANALYTICS_TOKEN else ""
    )
    noindex = bool(meta.get("noindex"))
    head_extra = '<meta name="robots" content="noindex">\n' if noindex else ""
    head_extra += alternates_html(meta, clusters)

    out = template
    subs = {
        "lang": LANGS[lang]["hreflang"],
        "title": html.escape(meta["title"]),
        "description": html.escape(meta["description"]),
        # A noindex page has no canonical URL of its own — point at the root.
        "canonical": SITE + "/" if noindex else canonical_for(meta["slug"]),
        "head_extra": head_extra,
        "og_image": f"{SITE}/assets/og.png",
        "og_locale": LANGS[lang]["hreflang"].replace("-", "_"),
        "home": "/" if lang == "en" else f"/{lang}/",
        "skip": html.escape(UI[lang]["skip"]),
        "nav": nav_html(meta),
        "langswitch": langswitch_html(meta, clusters),
        "h1": meta["h1"],
        "byline": byline_html(meta),
        "tldr": tldr_html,
        "body": body.strip(),
        "faq": faq_html(meta),
        "safety": safety_block(lang),
        "jsonld": jsonld_for(meta),
        "analytics": analytics,
        "app_id": APP_ID,
        "year": "2026",
        "brand": BRAND,
        "email": EMAIL,
        "footer_nav": footer_nav(lang),
        "disclaimer": UI[lang]["disclaimer"],
        "main_class": "article" if meta.get("type") == "article" else "page",
    }
    for key, value in subs.items():
        out = out.replace("{{" + key + "}}", value)
    leftover = re.findall(r"\{\{[a-z_]+\}\}", out)
    if leftover:
        raise SystemExit(f"{meta['slug'] or 'index'}: unresolved {set(leftover)}")
    return out


def main() -> None:
    template = (SRC / "_base.html").read_text(encoding="utf-8")

    parsed = []
    for path in sorted(PAGES.rglob("*.html")):
        parsed.append((path, *parse_fragment(path)))

    seen: dict[str, Path] = {}
    for path, meta, _ in parsed:
        if meta["slug"] in seen:
            raise SystemExit(f"duplicate slug {meta['slug']!r}: "
                             f"{seen[meta['slug']].name} and {path.name}")
        seen[meta["slug"]] = path

    clusters: dict[str, list[dict]] = {}
    for _, meta, _ in parsed:
        if meta.get("cluster"):
            clusters.setdefault(meta["cluster"], []).append(meta)
    for name, members in clusters.items():
        langs = [m["lang"] for m in members]
        if len(langs) != len(set(langs)):
            raise SystemExit(f"cluster {name!r} has two pages in the same language")
        if "en" not in langs:
            raise SystemExit(f"cluster {name!r} has no English page for x-default")

    pages = []
    for path, meta, body in parsed:
        out_path = ROOT / "index.html" if meta["slug"] == "" \
            else ROOT / meta["slug"] / "index.html"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(render(meta, body, template, clusters), encoding="utf-8")
        pages.append(meta)
        print(f"  {str(path.relative_to(PAGES)):46} -> {out_path.relative_to(ROOT)}")

    # 404 (GitHub Pages serves /404.html for unknown paths)
    if any(m["slug"] == "404" for m in pages):
        shutil.copyfile(ROOT / "404" / "index.html", ROOT / "404.html")
        shutil.rmtree(ROOT / "404")
        print("  404/index.html                                 -> 404.html")

    indexable = [m for m in pages if m["slug"] != "404" and not m.get("noindex")]

    urls = []
    for meta in sorted(indexable, key=lambda m: m["slug"]):
        lastmod = meta.get("updated", meta.get("published", BUILD_DATE))
        prio = "1.0" if meta["slug"] == "" else "0.8"
        alts = ""
        for peer in sorted(clusters.get(meta.get("cluster") or "", []),
                           key=lambda m: m["lang"]):
            tag = LANGS[peer["lang"]]["hreflang"]
            alts += (f'\n    <xhtml:link rel="alternate" hreflang="{tag}" '
                     f'href="{canonical_for(peer["slug"])}"/>')
            if peer["lang"] == "en":
                alts += ('\n    <xhtml:link rel="alternate" hreflang="x-default" '
                         f'href="{canonical_for(peer["slug"])}"/>')
        urls.append(
            f"  <url>\n    <loc>{canonical_for(meta['slug'])}</loc>"
            f"\n    <lastmod>{lastmod}</lastmod>"
            f"\n    <priority>{prio}</priority>{alts}\n  </url>"
        )
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        + "\n".join(urls)
        + "\n</urlset>\n",
        encoding="utf-8",
    )

    (ROOT / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\n"
        f"Sitemap: {SITE}/sitemap.xml\n",
        encoding="utf-8",
    )

    (ROOT / "CNAME").write_text(SITE.split("//")[1] + "\n", encoding="utf-8")

    # GitHub Pages cannot issue a 301, so the old flat URLs get a canonical tag
    # (which is what search engines act on) plus a meta refresh for humans.
    for old, new in REDIRECTS.items():
        (ROOT / old).write_text(
            '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            f'<link rel="canonical" href="{SITE}{new}">\n'
            '<meta name="robots" content="noindex,follow">\n'
            f'<meta http-equiv="refresh" content="0; url={new}">\n'
            f"<title>Moved to {new}</title>\n</head>\n<body>\n"
            f'<p>This page has moved to <a href="{new}">{SITE}{new}</a>.</p>\n'
            "</body>\n</html>\n",
            encoding="utf-8",
        )
        print(f"  redirect  {old:38} -> {new}")

    # Plain-text site summary for answer engines that fetch it.
    lines = [
        f"# {BRAND_FULL}",
        "",
        "VitalityRise (App Store name: Vitality Rise: Men's Health) is an iPhone app "
        "for men's pelvic floor training. It runs guided contract-and-relax sessions, "
        "pelvic mobility and breathing work, a 30-day plan, and progress scoring. "
        "Everything a user enters stays on the device: no account, no cloud sync, no "
        f"ads. Built by {AUTHOR} ({COMPANY}). US pricing: ${PRICE_WEEKLY}/week, "
        f"${PRICE_MONTHLY}/month or ${PRICE_YEARLY}/year (both with a 3-day free "
        f"trial), or ${PRICE_LIFETIME} once. iOS 17 or later.",
        "",
        "It is a general wellness app, not medical care, and does not diagnose or "
        "treat erectile dysfunction or any other condition.",
        "",
        "## Pages",
        "",
    ]
    for meta in sorted(indexable, key=lambda m: (m["lang"] != "en", m["slug"])):
        lines.append(f"- [{meta['h1']}]({canonical_for(meta['slug'])}): "
                     f"{meta['description']}")
    (ROOT / "llms.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\n{len(urls)} indexable pages across "
          f"{len({m['lang'] for m in pages})} languages.")
    print("sitemap.xml + robots.txt + llms.txt + CNAME written.")


if __name__ == "__main__":
    main()
