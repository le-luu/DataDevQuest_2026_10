import os
from fastmcp import FastMCP
from fastmcp.utilities.types import Image
from DDQ_2026_10_Intermediate import (
    get_token, list_workbook_views, parse_workbooks_response, get_view_image,
    add_svg_accessibility, build_accessibility_test_pages, PAT_NAME, PAT_SECRET, SERVER_ADDRESS, SITE_ID, IMG_DIR
)

mcp = FastMCP("Tableau View Tools")


# The image tools only read/write files inside the img folder, so the AI can't be
# pointed at other files on this computer.
def _img_path(path_or_name: str, extension: str) -> str:
    name = os.path.basename(path_or_name)
    if not name.lower().endswith(f".{extension}"):
        name = os.path.splitext(name)[0] + f".{extension}"
    path = os.path.join(IMG_DIR, name)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"{name} is not in {IMG_DIR}. Export the view first with export_view_image.")
    return path

@mcp.tool
def list_workbooks() -> list[dict]:
    """
    List all workbooks (with their views) from Tableau Server/ Cloud with metadata API via TSC
    """
    response = list_workbook_views(PAT_NAME, PAT_SECRET, SERVER_ADDRESS, SITE_ID)
    workbooks = parse_workbooks_response(response)
    return workbooks

@mcp.tool
def list_views(workbook_name: str) -> list[dict]:
    """
    List views from a specific workbook
    """
    response = list_workbook_views(PAT_NAME, PAT_SECRET, SERVER_ADDRESS, SITE_ID, workbook_name)
    workbooks = parse_workbooks_response(response)
    if workbooks:
        return workbooks[0]['views']
    else:
        return []

@mcp.tool
def export_view_image(view_luid: str, file_name: str, filters: dict[str, str] | None = None,
                      viz_width: int = 1200, viz_height: int = 900) -> list[str]:
    """
    Export a view as PNG and SVG with the REST API.
    Optional filters map a field name to a value, e.g. {"Region": "West"}.
    Filter values are appended to file_name automatically ("Superstore_Product" -> "Superstore_Product_West"),
    so pass the base name without the filter value.
    """
    token, site_luid = get_token(PAT_NAME, PAT_SECRET, SERVER_ADDRESS, SITE_ID)
    return get_view_image(SERVER_ADDRESS, site_luid, view_luid, token, file_name, IMG_DIR, filters,
                          viz_width, viz_height)

@mcp.tool
def list_exported_images() -> list[str]:
    """
    List the PNG and SVG files already exported to the img folder.
    """
    return sorted(f for f in os.listdir(IMG_DIR) if f.lower().endswith((".png", ".svg")))

@mcp.tool
def view_png(png_file: str) -> Image:
    """
    Return an exported PNG so you can look at it, e.g. to write alt text and a summary.
    png_file is a file name or path from export_view_image / list_exported_images.
    """
    return Image(path=_img_path(png_file, "png"))

@mcp.tool
def add_svg_accessibility_text(svg_file: str, alt: str, summary: str, lang: str = "en") -> dict:
    """
    Write alt text and a summary into an exported SVG so screen readers can read it.
    Puts alt in <title id="alt">, summary in <desc id="summary">, and adds role="img",
    aria-labelledby="alt summary" and lang to the <svg> tag. Edits only those parts with code;
    the drawing is left unchanged. Running it again replaces the previous text.
    alt must be 150 characters or fewer. svg_file is a file name or path in the img folder.
    """
    return add_svg_accessibility(_img_path(svg_file, "svg"), alt, summary, lang)

@mcp.tool
def build_screen_reader_test_page(open_browser: bool = True) -> str:
    """
    Build HTML pages for testing the accessible SVGs with a screen reader, one page per SVG
    that has alt text, plus an index page. Each page shows the chart as an inline SVG.
    Opens the index in the browser by default. Returns the index.html path.
    """
    return build_accessibility_test_pages(open_browser=open_browser)


if __name__ == "__main__":
    mcp.run(transport="stdio")
