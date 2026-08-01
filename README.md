# PDF Form Service — READ THIS FIRST

**If you are an AI being asked to add or change a form: read this file and
`SCHEMA.md` before writing a single line. Do not redesign this system.**

## The rule

> A new form is **one JSON file** in `forms/`.
> No new HTML. No new Python. No deploy.

If you find yourself writing a renderer, a per-form HTML page, or a new PDF
library, you have taken a wrong turn. Stop and re-read this.

## How it fits together

```
sas.vc/forms/<slug>.json     the form — the only file a new form needs
sas.vc/form.html             runtime: builds the fillable page from the schema
        │  POST {schema, values, filename}
        ▼
Railway /generate-schema-pdf → schema_renderer.py → application/pdf
```

Open a form at `sas.vc/form.html?f=<slug>`.

`forms/waiver.json` is the **golden reference**. Copy its shape. It exercises
every component: prefilled fields, three tables, cross-table totals, a note
box, a page break, a grow-to-fit textarea, and a signature block.

## Approaches already tried and rejected

Do not revisit these. Each cost hours.

| Approach | Why it failed |
|---|---|
| jsPDF + autoTable in the browser | autoTable applies **body** column widths to **footer** rows, so total labels wrap catastrophically. Unfixable without abandoning `foot:`. |
| Browser print-to-PDF (`window.print()`) | White borders, truncated text boxes, no control over pagination. |
| One hand-written HTML file per form | Every new form became a day of layout tinkering. This is the problem the schema exists to solve. |
| Hardcoded per-form Python (`pdf_builder.py`) | Deleted. Duplicated the renderer per form. |

## Layout rules that took a day to settle — do not "simplify" them

**Column widths** (`_column_widths`, mirrored in `form.html`):

1. `min` = widest single **word** — the floor. Words never break.
2. `natural` = widest whole string.
3. `score` = total text volume in the column.
4. If everything fits: hand slack to `flex`, else share it by `score + natural`.
5. If it does not fit: start every column at `min`, hand out the remainder in
   proportion to `score`, capping at `natural`, redistributing what spills.

This is what stops one long single string (a Grade cell) starving a column
carrying far more total text (a Subject cell). A naive "widest string wins"
allocator produces an 11-line Subject column beside a half-empty Grade column.

`narrow` means **"never chosen as the flex column"**. It does *not* mean
"never compressed". Reading it the other way starves the flex column.

**Totals**: the label cell spans every column *except the last*, so the figure
lands flush beneath the figures above it. Do not put the label in a fixed
percentage — it will drift as columns resize.

## Regression check

Run after **any** change to `schema_renderer.py`:

```bash
python3 test_render.py
```

It renders `forms/waiver.json` and asserts the invariants that were broken
repeatedly during the original build. If it fails, you have regressed
something that was expensive to get right.

## Deploy

- **Railway** — push this directory. `Procfile` and `railway.json` are set up.
- **sas.vc** — `form.html` into `public_html/`, schemas into `public_html/forms/`.
- Set `SERVER` at the top of `form.html` to the Railway URL.
