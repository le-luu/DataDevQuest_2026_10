---
name: tableau-accessible-svg
description: Makes exported Tableau view images accessible by describing the PNG with AI (alt text under 150 characters plus a three-sentence summary, returned as JSON), checking the numbers, and writing the text into the matching SVG's title and desc tags with role="img", aria-labelledby and lang. Use this whenever a Tableau view has been exported (or the user asks to export one) to PNG/SVG with the Tableau View Tools MCP server (export_view_image), including exports filtered by Region or any other field, and whenever the user mentions alt text, screen readers, accessibility, describing a dashboard image, or "shipping" an accessible SVG, even if they don't name this skill.
---

# Accessible Tableau SVGs

After a Tableau view is exported as PNG + SVG, turn the SVG into one a screen reader can read aloud:

1. **Describe**: look at the PNG and draft alt text and a summary as JSON.
2. **Check**: verify every number in the draft against the image.
3. **Ship**: write the text into the SVG with the `add_svg_accessibility_text` tool.

The AI drafts the words and code makes the edit. Tableau SVGs are 1 MB or more, and rewriting one by hand (or by having the model output it) can change or cut parts of the drawing. `add_svg_accessibility_text` touches only the `<svg>` tag and its `<title>`/`<desc>`, so never try to edit the SVG text yourself.

## Tools (Tableau View Tools MCP server)

| Tool | Use |
|---|---|
| `export_view_image(view_luid, file_name, filters?)` | Exports `<file_name>[_<filter value>].png` and `.svg`. Returns both paths. |
| `list_exported_images()` | Lists the files in the img folder, for when the user refers to an earlier export. |
| `view_png(png_file)` | Shows you the PNG. You need to actually see it before describing it. |
| `add_svg_accessibility_text(svg_file, alt, summary, lang="en")` | Writes the text into the SVG. Re-running it replaces the old text. |
| `build_screen_reader_test_page(open_browser=True)` | Builds one HTML test page per accessible SVG, plus an index page, and opens the index. |

If the view hasn't been exported yet, export it first (use `list_views` to find the view's `luid`). If these tools aren't available, tell the user that the Tableau View Tools MCP server needs to be connected in Claude Desktop. Don't fall back to editing SVG text in chat.

## Step 1: Describe

Call `view_png` on the PNG and study it: the title, the chart types, the axes, the legend, the filter state (for example "Region: West" in a filter card), and the actual values.

Draft:
- **alt**: 150 characters or fewer. Say what the view is and what it shows, not every number. A screen reader reads this first, so lead with the view's name and type.
- **summary**: exactly three sentences. (1) What the view shows and its scope (time range, categories, filter). (2) The main pattern or trend. (3) The most notable specific: a peak, an outlier or a comparison, with a real number from the image.

Present the draft to the user as JSON:

```json
{"alt": "...", "summary": "..."}
```

Example, for the Product view filtered to the West region:

```json
{
  "alt": "Product Drilldown, West region: monthly sales heatmap by category for 2022-2025, with product sales and profit by customer segment.",
  "summary": "This dashboard shows monthly sales from 2022 to 2025 for Furniture, Office Supplies and Technology in the West region. Sales peak in the last four months of each year and are lowest in January and February. The highest month shown is Technology in March 2025 at $X."
}
```

(`$X` stands for a value you read from the image. Never write a number you didn't see.)

## Step 2: Check the numbers

Models misread small heatmap labels, so treat your draft as unverified. Go back to the PNG and, for every number, date, category or claim of "highest" or "lowest" in the draft:
- find it in the image and confirm it matches exactly (digits, year, month and category);
- for "highest" or "lowest" claims, scan the whole row, column or grid, not just the cells you noticed first;
- if you can't read a value with confidence, drop it or describe the pattern without the number. A vague but true summary is better than a precise wrong one.

If cells show `#####` or are cut off, the export was too small to show the numbers. Re-export with a larger `viz_width`/`viz_height` (for example 1600 x 1200) before describing it.

## Step 3: Ship

Call `add_svg_accessibility_text` with the SVG from the same export as the PNG you described, plus your checked `alt` and `summary`. Set `lang` to the language you wrote in. If the tool rejects the alt text as too long, shorten it and call it again.

## Filtered exports (one SVG per Region, etc.)

Each filtered export is its own image with its own numbers, so run Describe → Check → Ship separately for every file. Don't reuse one region's text for another, or the alt text will read out the wrong numbers.

- Pair files by name: `Superstore_Product_West.png` goes with `Superstore_Product_West.svg`. The filter value is the suffix after the base name.
- Name the filter value in both the alt text and the summary ("West region"), so a listener knows which version they're hearing.
- When the user asks for "each region" without listing them, use the values they gave, or ask. For Superstore the regions are Central, East, South and West.
- For an unfiltered export, say "all regions" if the filter card shows "All".

## Report back

The AI drafts; a person checks. After shipping, give the user a short report for each file:
- the SVG file name;
- the final JSON (`alt` and `summary`);
- the specific figures you cited, so they can quickly check them against the dashboard;
- anything you weren't sure about or left out because you couldn't read it clearly.

Offer to change the wording. If they ask for changes, call `add_svg_accessibility_text` again with the new text; it replaces the old text.

## Screen reader test page

After shipping (or whenever the user wants to hear the result), call `build_screen_reader_test_page` once, after all files in the batch are done. It rebuilds the pages for every accessible SVG, so it picks up re-worded text too. Each page shows the chart as an inline SVG (the SVG code is inside the page), so the screen reader reads the title (alt text) and then the description (summary).

If the user embeds a chart on their own page with `<img src="chart.svg">` instead, browsers ignore the title inside the file, so remind them to copy the alt text into the tag's `alt="..."`.

Tell the user where the index is, and suggest testing with Narrator (Ctrl+Win+Enter) or NVDA. The pages also have a hidden "Expected text" section they can open afterwards to compare.
