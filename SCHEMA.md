# SAS Form Schema v1

One JSON file defines a form. It drives the fillable HTML **and** the PDF.
A new form = one file in `/forms/`. No HTML, no Python, no deploy.

## Top level

```json
{
  "title":     "Educational Waiver Request",
  "subtitle":  "British Army Officer Entry · Return to ...",
  "reference": "D-ARMY-864 (Revised 10 Sep 20)",
  "protect":   true,
  "filename":  "Educational_Waiver_Request.pdf",
  "sections":  [ ... ],
  "footer":    { "return_to": "...", "lines": ["...","..."] }
}
```

`protect` renders the PROTECT – PERSONAL DATA header band on every page.

## Components (`sections[]`)

### sec_bar — dark section header
```json
{"type":"sec_bar","text":"Candidate Particulars"}
```

### field_row — labelled fields, one line, widths auto-allocated
```json
{"type":"field_row","fields":[
  {"label":"Forenames","id":"forenames","default":"John","prefill":true},
  {"label":"Location","id":"s1l","default":"North Devon, UK"}
]}
```
- `prefill: true` → tinted, read-only. Fact, not input.
- `default` → pre-populated but editable.
- Widths are measured from label + value. No manual sizing.

### table — auto-sized columns, optional totals
```json
{"type":"table","id":"gcse",
 "headers":["Type","Subject","Date Awarded","Grade","ALIS Points"],
 "narrow":[0,2,3,4],
 "flex":1,
 "sum_col":4,
 "rows":[["GCSE","Mathematics","Summer 1994","A","7"]],
 "totals":[{"label":"Total ALIS Points:","of":["self"]}],
 "addable":true}
```
- `narrow` — columns that must never be widened to absorb slack.
- `flex` — column that absorbs slack. Omit and it is chosen by content volume.
- `sum_col` — index summed for totals.
- `of` — `["self"]`, or table ids e.g. `["al","mat"]` for a combined row.
- Totals arrive in `values` as `<table_id>__t<index>`.

### note — bordered explanatory block
```json
{"type":"note","text":"<b>Note:</b> ..."}
```

### textarea — large free-text, grows to fit
```json
{"type":"textarea","id":"justification","instruction":"State fully ...","default":"..."}
```

### signature / divider / page_break / text
```json
{"type":"signature"}
{"type":"divider"}
{"type":"page_break"}
{"type":"text","text":"ALIS Points: A*/9 = 8 · ..."}
```

## Column width rule (both renderers)

1. **min**   = widest single word (never break a word)
2. **natural** = widest whole string
3. **score**  = total ink volume in the column
4. flex column = explicit `flex`, else highest score, never one in `narrow`
5. all columns at natural; slack goes to flex; overflow compresses flex only,
   never below min.

## Values payload

```json
{"schema": {...}, "values": {
  "forenames": "John",
  "gcse": [["GCSE","Mathematics","Summer 1994","A","7"]],
  "gcse__t0": "69",
  "justification": "..."
}}
```
Scalars by field `id`. Tables by table `id`. Totals as `<id>__t<n>`.
