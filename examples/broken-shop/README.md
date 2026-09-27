# broken-shop (intentionally broken example system)

A deliberately messed-up e-commerce system, used to develop and prove the ragghost surgeon against
real defects. Point the surgeon at a COPY of this and it should fix what is fixable, surface what
needs a human, and ship a working store.

## Planted defects
| id | file | class | surgeon should |
|----|------|-------|---------------|
| D1 | data/products.json | trailing-comma JSON | FIX |
| D2 | data/config.json | missing store_name | FIX (from scope) |
| D3 | data/settings.json | empty/invalid JSON | FIX |
| D4 | src/build_store.py | import typo (templating->template) | FIX |
| D5 | src/legacy_paypal_ipn.py | unwired/orphan | SURFACE (never auto-delete) |
| D6 | src/discount_broken.py | syntax error | SURFACE (no safe auto-fix) |

Plus a rule that helps (rules/quality.md, KEPT) and one that conflicts with the store goal
(rules/legacy-scope.md, FLAGGED for the owner, never deleted).
