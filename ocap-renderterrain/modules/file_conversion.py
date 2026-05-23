import os
import subprocess
import sys

from prettytable import PrettyTable

import xml.etree.ElementTree as ET


def _env_float(name, default):
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return float(default)


TOWN_NAME_FONT_SIZE = _env_float("OCAP_RENDER_TOWN_NAME_FONT_SIZE", "24")
TOWN_NAME_COLLISION_PADDING = _env_float(
    "OCAP_RENDER_TOWN_NAME_COLLISION_PADDING", "8"
)
TOWN_NAME_OVERLAP_FONT_SIZE = _env_float("OCAP_RENDER_TOWN_NAME_OVERLAP_FONT_SIZE", "14")
TOWN_NAME_POI_WORDS = {
    "airfield",
    "base",
    "camp",
    "checkpoint",
    "depot",
    "factory",
    "farm",
    "field",
    "garage",
    "market",
    "mine",
    "oil",
    "outpost",
    "station",
}


def run_command(command):
    """Run a shell command and fail loudly with the command that failed."""
    print(f"Running: {command}", flush=True)
    subprocess.run(command, shell=True, check=True)


def get_svg_items(root, category_id, item_type):
    """Get SVG items of a specific type from a specific category"""
    for category in root.findall("./{http://www.w3.org/2000/svg}g"):
        if category.get("id") == category_id:
            return category.findall("./{http://www.w3.org/2000/svg}" + item_type)
    return []


def _svg_float(value, default=0.0):
    try:
        return float(str(value).replace("px", ""))
    except (TypeError, ValueError):
        return default


def _text_value(text_el):
    return "".join(text_el.itertext()).strip()


def _town_name_priority(label):
    words = [word for word in label.lower().replace("-", " ").split() if word]
    poi_penalty = sum(1 for word in words if word in TOWN_NAME_POI_WORDS)
    return (
        -poi_penalty,
        -max(0, len(words) - 1),
        -len(label),
        label.lower(),
    )


def _text_bbox(text_el, label, font_size, padding):
    x = _svg_float(text_el.get("x"))
    y = _svg_float(text_el.get("y"))
    width = max(font_size * 3, len(label) * font_size * 0.58)
    height = font_size * 1.2
    return (
        x - width / 2 - padding,
        y - height - padding,
        x + width / 2 + padding,
        y + height * 0.25 + padding,
    )


def _boxes_overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def scale_overlapping_town_names(town_names_text, font_size, overlap_font_size):
    labels = []
    for text in town_names_text:
        label = _text_value(text)
        if label == "":
            continue
        labels.append(
            {
                "element": text,
                "label": label,
                "priority": _town_name_priority(label),
                "bbox": _text_bbox(
                    text, label, font_size, TOWN_NAME_COLLISION_PADDING
                ),
            }
        )

    kept = []
    scaled = []
    for item in sorted(labels, key=lambda value: value["priority"], reverse=True):
        if any(_boxes_overlap(item["bbox"], existing["bbox"]) for existing in kept):
            item["element"].set("font-size", f"{overlap_font_size:g}px")
            scaled.append(item)
        else:
            item["element"].set("font-size", f"{font_size:g}px")
            kept.append(item)

    if scaled:
        print(
            "Reduced font size for",
            len(scaled),
            "overlapping town/location labels",
            flush=True,
        )


def preprocess_svg(in_file, out_file):
    """Preprocess SVG file"""

    """
    Some issues face us with the default SVG exports from Arma 3:
      1. There is no "fill=none" attribute on the
        <g id="countLines">
          <polyline>...</polyline>
        </g>
        element, so the lines are filled with black.
      2. The <ellipse> elements representing trees have no on-element fill or stroke attributes, so they're translated to black opaque circles. We also want to shrink the trees by 50% (to 6px radius) and add a stroke to them.
      3. There is no "fill=none" attribute on the
        <g id="roads">
          <polyline>...</polyline>
        </g>
        element, so the lines are filled with black.
      4. We want the text for mountains and location names to be 12px Arial.
      5. We want to set "fill=none" on airport polylines
    """

    # read in_file
    # with open(in_file, "r", encoding="utf-8") as f:
    #     svg = f.read()
    #     f.close()

    # read SVG as XML for parsing
    print("Reading SVG...")
    svg = ET.parse(in_file)
    svg_root = svg.getroot()
    if svg_root is None:
        print(f"Failed to parse SVG file ({in_file}), exiting...")
        sys.exit(1)

    # get counts of each g category and print as a table
    type_counts = PrettyTable()
    type_counts.field_names = [
        "Category",
        "polyline",
        "polygon",
        "ellipse",
        "line",
        "text",
    ]
    for category in svg_root.findall("./{http://www.w3.org/2000/svg}g"):
        category_id = category.get("id")
        type_counts.add_row(
            [
                category_id,
                len(get_svg_items(svg_root, category_id, "polyline")),
                len(get_svg_items(svg_root, category_id, "polygon")),
                len(get_svg_items(svg_root, category_id, "ellipse")),
                len(get_svg_items(svg_root, category_id, "line")),
                len(get_svg_items(svg_root, category_id, "text")),
            ]
        )

    # get forestBorders under forests
    forests_root = svg_root.find("./{http://www.w3.org/2000/svg}g[@id='forests']")
    forest_border_els = get_svg_items(forests_root, "forestBorder", "line")
    type_counts.add_row(["forestBorders", 0, 0, 0, len(forest_border_els), 0])

    print(type_counts)

    # forests_polygons = get_svg_items(svg_root, "forests", "polygon")
    # # if count of forest polygons is > 50000, compress the SVG
    # print("Forest count:", len(forests_polygons))
    # if len(forests_polygons) > 50000:
    #     print("Warning: Forests count is > 50000, removing forests from SVG")
    #     # get forests root
    #     forests = svg_root.find("./{http://www.w3.org/2000/svg}g[@id='forests']")
    #     # remove forests from svg
    #     for forest in forests:
    #         forests.remove(forest)

    tree_ellipses = get_svg_items(svg_root, "objects", "ellipse")
    # if count of tree ellipses is > 30000, compress the SVG
    print("Tree count:", len(tree_ellipses))
    if len(tree_ellipses) > 30000:
        print("Warning: Tree count is > 30000, removing trees + forestborders from SVG")
        # get objects root
        objects = svg_root.find("./{http://www.w3.org/2000/svg}g[@id='objects']")
        # remove objects from svg
        print("Removing", len(tree_ellipses), "trees")
        for tree in tree_ellipses:
            objects.remove(tree)

    # get forest root
    forests_root = svg_root.find("./{http://www.w3.org/2000/svg}g[@id='forests']")
    # get forestborders
    forest_polygon_els = get_svg_items(svg_root, "forests", "polygon")
    forest_border_els = get_svg_items(forests_root, "forestBorder", "line")
    print("Forest count:", len(forest_polygon_els))
    print("Forest border count:", len(forest_border_els))

    # pick the one that's greater
    to_cull = (
        ["forests", forest_polygon_els]
        if len(forest_polygon_els) > len(forest_border_els)
        else ["borders", forest_border_els]
    )

    if len(to_cull[1]) > 250000:
        print(
            "Warning: Forest or forest border count is > 250000. Keeping the one with fewest features."
        )

        if to_cull[0] == "forests":
            # remove forests
            for forest in to_cull[1]:
                forests_root.remove(forest)
        else:
            forest_borders_root = forests_root.find(
                "./{http://www.w3.org/2000/svg}g[@id='forestBorders']"
            )
            # remove forestborder
            for forestborder in to_cull[1]:
                forest_borders_root.remove(forestborder)
        print("Removed", len(to_cull[1]), to_cull[0])

    # breakpoint()

    print("Processing countLines...")
    # get all polylines under <g id="countLines">
    count_lines = get_svg_items(svg_root, "countLines", "polyline")

    # add fill=none to all polylines under <g id="countLines">
    for polyline in count_lines:
        polyline.set("fill", "none")

    print("Processing trees...")
    # get all ellipses under <g id="objects">
    objects_ellipses = get_svg_items(svg_root, "objects", "ellipse")

    # for all ellipses under <g id="objects">:
    # add fill=none
    # add stroke="url(#colorForestBorder)"
    for ellipse in objects_ellipses:
        ellipse.set("fill", "none")
        ellipse.set("stroke", "url(#colorForestBorder)")
        ellipse.set("rx", "6.00")
        ellipse.set("ry", "6.00")

    print("Processing forests...")
    forests_polygons = get_svg_items(svg_root, "forests", "polygon")
    # for all polygons under <g id="forests">, add fill-opacity=0.5
    for polygon in forests_polygons:
        polygon.set("fill-opacity", "0.2")
        polygon.set("fill", "#3e6e30")

    print("Processing roads...")
    # get all polylines under <g id="roads">
    roads_polylines = get_svg_items(svg_root, "roads", "polyline")

    # add fill=none to all polylines under <g id="roads">
    for polyline in roads_polylines:
        polyline.set("fill", "none")

    print("Processing mountains...")
    # get all text under <g id="mountains">
    mountains_text = get_svg_items(svg_root, "mountains", "text")

    # for all text under <g id="mountains">, set font-size to 10px and font-family to Arial
    if mountains_text is not None:
        for text in mountains_text:
            text.set("font-size", "10px")
            text.set("font-family", "Arial")

    print("Processing townNames...")
    town_names_root = svg_root.find("./{http://www.w3.org/2000/svg}g[@id='townNames']")
    town_names_text = get_svg_items(svg_root, "townNames", "text")

    # Keep every label. Reduce lower-priority overlapping labels instead of removing them.
    if town_names_root is not None:
        scale_overlapping_town_names(
            town_names_text, TOWN_NAME_FONT_SIZE, TOWN_NAME_OVERLAP_FONT_SIZE
        )
        for text in get_svg_items(svg_root, "townNames", "text"):
            text.set("font-family", "Arial")

    print("Processing airports...")
    # get all polylines under <g id="airports">
    airports_polylines = get_svg_items(svg_root, "airports", "polyline")

    # add fill=none to all polylines under <g id="airports">
    for polyline in airports_polylines:
        polyline.set("fill", "none")

    # write xml back to svg
    svg.write(out_file)

    # if file size still > 90MB, remove minor countlines
    if os.path.getsize(out_file) > 90000000:
        print("File size still > 90MB, removing minor countlines")
        # get countlines root
        countlines_root = svg_root.find(
            "./{http://www.w3.org/2000/svg}g[@id='countLines']"
        )
        # remove minor countlines (where stroke is url(#colorCountlines))
        for polyline in count_lines:
            if polyline.get("stroke") == "url(#colorCountlines)":
                countlines_root.remove(polyline)
        # write xml back to svg
        svg.write(out_file)


def generate_svg_dark(in_file, out_file):
    """Change some of the default colors to make a 'dark' version of the SVG"""
    # read SVG as XML for parsing
    print("Reading SVG...")
    svg = ET.parse(in_file)
    svg_root = svg.getroot()
    if svg_root is None:
        print(f"Failed to parse SVG file ({in_file}), exiting...")
        sys.exit(1)

    print("Processing countLines")
    count_lines = get_svg_items(svg_root, "countLines", "polyline")
    if count_lines is not None:
        # reduce opacity of countLines
        for polyline in count_lines:
            polyline.set("opacity", "0.5")

    print("Processing land...")
    land = get_svg_items(svg_root, "terrain", "polygon")
    if land is not None:
        # darken land
        for land_el in land:
            land_el.set("fill", "#1d2b20")

    print("Processing sea...")
    sea = get_svg_items(svg_root, "terrain", "rect")
    if sea is not None:
        # darken sea
        for sea_el in sea:
            sea_el.set("fill", "#303d6e")

    print("Brightening text...")
    town_names = get_svg_items(svg_root, "townNames", "text")
    if town_names is not None:
        # brighten location names
        for text in town_names:
            text.set("fill", "#EEEEEE")
            text.set("stroke", "#0f0f0f")
            text.set("stroke-width", "1px")
            text.set("font-weight", "bold")
    mountains = get_svg_items(svg_root, "mountains", "text")
    if mountains is not None:
        # brighten mountain height markers
        for text in mountains:
            text.set("fill", "#EEEEEE")
            # text.set("stroke", "#0f0f0f")
            # text.set("stroke-width", "1px")
            # text.set("font-weight", "bold")

    # write xml back to svg
    svg.write(out_file)


def generate_svg_landonly(in_file, out_file):
    """Create an SVG that only has land and sea layers for us to overlay analysis layers."""
    # read SVG as XML for parsing
    print("Reading SVG...")
    svg = ET.parse(in_file)
    svg_root = svg.getroot()
    if svg_root is None:
        print(f"Failed to parse SVG file ({in_file}), exiting...")
        sys.exit(1)

    # get all <g> elements
    gs = svg_root.findall("./{http://www.w3.org/2000/svg}g")
    # remove all <g> elements except for terrain
    for g in gs:
        if g.get("id") != "terrain":
            svg_root.remove(g)

    # write xml back to svg
    svg.write(out_file)


def generate_svg_noland(in_file, out_file):
    """Create an SVG that has everything above the terrain layers, to render over analysis layers (except forests which need opacity)."""
    # read SVG as XML for parsing
    print("Reading SVG...")
    svg = ET.parse(in_file)
    svg_root = svg.getroot()
    if svg_root is None:
        print(f"Failed to parse SVG file ({in_file}), exiting...")
        sys.exit(1)

    # get all <g> elements where id=terrain
    gs = svg_root.findall("./{http://www.w3.org/2000/svg}g")
    # remove all <g> elements except for terrain
    for g in gs:
        if g.get("id") == "terrain":
            svg_root.remove(g)

    # write xml back to svg
    svg.write(out_file)


# def generate_svg_forestonly(in_file, out_file):
#     """Create an SVG that has everything above the terrain layers, to render over analysis layers."""
#     # read SVG as XML for parsing
#     print("Reading SVG...")
#     svg = ET.parse(in_file)
#     svg_root = svg.getroot()
#     if svg_root is None:
#         print(f"Failed to parse SVG file ({in_file}), exiting...")
#         sys.exit(1)

#     # get all <g> elements where id=terrain
#     gs = svg_root.findall("./{http://www.w3.org/2000/svg}g")
#     # remove all <g> elements except for terrain
#     for g in gs:
#       if g.get("id") != "forests":
#         svg_root.remove(g)

#     # write xml back to svg
#     svg.write(out_file)


def convert_svg_to_png(in_file, out_file, export_size):
    """Convert SVG to PNG using Inkscape"""
    # convert svg file to png
    print("Converting SVG to PNG...")

    temp_file = out_file.replace(".png", "_temp.png")
    run_command(
        f"inkscape -o {out_file} --export-height={export_size} --export-width={export_size} {in_file}",
    )
    print("Converted SVG to PNG")


def convert_png_to_24bit(in_file, out_file):
    """Convert PNG to 24-bit"""
    print("Converting PNG to 24-bit...")

    run_command(
        f"magick {in_file} -alpha off {out_file}",
    )
    print("Converted PNG to 24-bit, saved as", out_file)


def resize_raster(in_file, out_file, export_size):
    """Resize a raster with GDAL instead of ImageMagick for large DEM-derived images."""
    temp_file = out_file.replace(".png", "_resized.png")
    run_command(
        f"gdal_translate -of PNG -outsize {export_size} {export_size} -r bilinear {in_file} {temp_file}",
    )
    os.replace(temp_file, out_file)


def generate_heightmap(in_file, out_file, export_size):
    """Convert DEM (XYZ or ASC) to GeoTIFF"""

    run_command(
        f"gdaldem hillshade -alg Horn -alt 45 -multidirectional -of PNG {in_file} {out_file}",
    )
    resize_raster(out_file, out_file, export_size)


def generate_colorrelief(in_file, out_file, export_size):
    """Convert DEM (XYZ or ASC) to GeoTIFF"""

    # see here for other color relief options
    # http://soliton.vm.bytemark.co.uk/pub/cpt-city/index.html
    run_command(
        f"gdaldem color-relief -of PNG {in_file} ./modules/nzblue.cpt {out_file}",
    )
    resize_raster(out_file, out_file, export_size)


def set_half_opacity(in_file, out_file):
    """Set image to half opacity"""
    run_command(
        f"magick -limit area 0 {in_file} -alpha set -channel a -evaluate set 50% {out_file}",
    )


def composite_images(in_file, overlay_file, out_file):
    """Composite two PNGs"""
    # overlay filter
    run_command(
        f"magick {in_file} {overlay_file} -composite {out_file}",
    )


def overlay_images(in_file, overlay_file, out_file):
    """Overlay two PNGs"""
    # overlay filter
    run_command(
        f"magick {in_file} {overlay_file} -compose overlay -composite {out_file}",
    )


def multiply_images(in_file, overlay_file, out_file):
    """Multiply two PNGs"""
    # multiply filter
    run_command(
        f"magick -limit area 2GP {in_file} {overlay_file} -compose multiply -composite {out_file}",
    )
