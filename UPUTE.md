# MARRUBI automatski cjenik (NN 101/2026)

Isti princip kao mylapiel.com: stranica /pages/cjenik na Shopifyju s gumbom na poddomenu
cjenik.<domena>, gdje GitHub svako jutro sam generira CSV + XML i drži arhivu 30+ dana.
Besplatno, bez Shopify aplikacije i bez API ključa (koristi javni /products.json).

## 1. Popuni podatke (5 min)
- `config.json`: shop_url, custom_domain, naziv firme, OIB, adresa sjedišta, opcije dostave su već upisane (services), promijeni ih samo ako promijeniš dostavu u Shopifyju.
- Barkod: MARRUBI nema barkodove, stupac barkod u cjeniku ostaje prazan (zakon ga traži samo kada je primjenjivo).
- `proizvodi_dodatno.csv`: po jedan red za svaki SKU iz Shopifyja: neto količina + jedinica
  (npr. `0,03;l` za 30 ml, onda se cijena po litri računa sama), sidrena cijena i datum.
  - Kozmetika: ako ste već isticali sidrenu cijenu po staroj odluci (NN 75/25), ostaje cijena od **02.05.2025**.
  - Inače: cijena na dan **10.09.2026**.
  - SKU koji fali u ovoj tablici dobije trenutnu cijenu kao sidrenu + upozorenje u logu. Provjeri log nakon prvog runa.
- Provjeri da svaka varijanta u Shopifyju ima SKU (inače se koristi ID varijante).

## 2. GitHub (10 min)
1. Novi repo (može private uz plaćeni plan; na free planu Pages traži public repo, što je ok jer je cjenik ionako javan).
2. Uploadaj sve datoteke iz ovog paketa, uključujući `.github/workflows/cjenik.yml`.
3. Settings → Pages → Source: *Deploy from a branch* → `main` / `/docs`.
4. Actions → "Dnevni cjenik" → **Run workflow** (prvi ručni run).
5. Settings → Pages → Custom domain: `cjenik.<domena>` → Enforce HTTPS.

## 3. DNS
Kod registrara domene dodaj CNAME zapis: `cjenik` → `<github-username>.github.io`

## 4. Shopify
1. Online Store → Pages → Add page, naslov **Cjenik**. U editoru klikni `<>` (Show HTML) i zalijepi
   `shopify-stranica-cjenik.html` (zamijeni ZAMIJENI dijelove).
2. Online Store → Navigation → footer izbornik "Korisničke informacije" → Add menu item → Cjenik → /pages/cjenik.

## Kako radi
- Svaki dan u 05:15 (ljeti) / 04:15 (zimi) GitHub pokrene skriptu, povuče sve objavljene proizvode,
  zapiše `webshop_<adresa>_P-01_<redni broj>_<datum>_<vrijeme>.csv/.xml`, osvježi index i obriše datoteke starije od 35 dana.
- Stalni linkovi za scrapere: `/cjenik.csv` i `/cjenik.xml`.
- Akcija se prepoznaje automatski: ako varijanta ima "Compare at price" veći od cijene → DA / Akcija.
- GitHub cron zna kasniti 10-30 min, zato je postavljen daleko prije roka od 8:00.
- Ako promijeniš cijenu tijekom dana i želiš odmah novi cjenik: Actions → Run workflow.
- GitHub gasi zakazane workflowe u repoima bez aktivnosti 60 dana; ovdje se svaki dan radi commit pa to ne bi trebalo biti problem.
