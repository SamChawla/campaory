# Mockups

The approved design was built as a Design canvas on claude.ai. The six boards are in `source/`:

| Board | File | Size | What it shows |
|---|---|---|---|
| 01 Start | `Main.dc.html` | 1280 x 2040 | Landing and start form, floating pill nav, hero with platform circles |
| 02 Confirm facts | `Facts.dc.html` | 1280 x 1300 | Fact table, status chips, source snippets |
| 03 Plan | `Plan.dc.html` | 1280 x 1200 | Campaign calendar by stage |
| 04 Posts | `Posts.dc.html` | 1280 x 1400 | Four platform cards per item, counters, actions |
| 05 A fact changed | `Change.dc.html` | 1280 x 1400 | Affected posts, diff, accept or keep |
| 06 Phone | `Mobile.dc.html` | 390 x 844 | Review a post on a phone |

Live canvas (private to your claude.ai account): https://claude.ai/artifact/LMB2Zk8whVAb1w7xHs813s

## Read this before relying on the files

- The `.dc.html` files load `./support.js`, the Design canvas runtime. That file is not in this repo and cannot be opened by double-clicking. They are reference sources: read the inline styles for exact colours, spacing and copy, or open the live canvas.
- Use `tokens.css` (this folder) for the extracted design tokens. Copy it to `frontend/src/styles/tokens.css`.
- Not mocked: sign-in sheet, save banner, saved campaigns list, rate-limit message, empty states, error states. They are specified in [UI_SPEC](../UI_SPEC.md) section 7. Build them from the spec using the same tokens.
- The mockups use sample copy and sample data; do not ship that copy as facts.

## Suggested use in VS Code

1. Open the live canvas in a browser beside the editor, or screenshot each board into `docs/mockups/png/` for offline reference.
2. Build components from UI_SPEC, then compare against the canvas at 1280 px and 360 px.
