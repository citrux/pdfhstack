"""
Module for merging pages of pdf documents horizontally, a-la numpy.hstack

You can use this script directly, but install pypdf first
"""

import argparse
import sys
from io import BytesIO
from pathlib import Path
from typing import IO

try:
    from pypdf import PageObject, PaperSize, PdfReader, PdfWriter, Transformation
    from pypdf.papersizes import Dimensions
except ImportError:
    if __name__ == "__main__":
        print("pdfhstack requires pypdf to work. Install it first")
        sys.exit(1)
    else:
        raise

MM = 72 / 25.4  # pt per mm


def hstack(files: list[str | IO | Path], papersize: Dimensions = PaperSize.A4, padding: float = 5) -> BytesIO:
    """Make all work. Takes all pages from files and merge them. Returns BytesIO object with resulting pdf file

    The result is a single *portrait* sheet of ``papersize`` with the pages laid out side by side
    along its long edge, i.e. the strip is rotated 90 degrees inside the content stream.
    The page deliberately carries no ``/Rotate`` entry: CUPS (pdftopdf + gstoraster) applies
    ``/Rotate`` and hands the driver a landscape raster, which host-based HP LaserJets (hpcups)
    cannot print - they emit a portrait A4 page header and abort after a few centimetres.
    A raster in the sheet's native portrait orientation prints everywhere.
    """
    pages = []
    for pdf in files:
        for page in PdfReader(pdf).pages:
            # bake the source page's own /Rotate into its content, so that it is merged as displayed
            page.transfer_rotation_to_content()
            pages.append(page)

    width = sum(page.cropbox.width for page in pages)  # strip width: pages side by side
    height = max(page.cropbox.height for page in pages)  # strip height: the tallest page

    padding = padding * MM
    out = PageObject.create_blank_page(width=papersize.width, height=papersize.height)
    # the strip runs along the long (vertical) edge of the sheet
    scale = min((out.mediabox.height - 2 * padding) / width, (out.mediabox.width - 2 * padding) / height)

    # Each page is scaled and rotated 90 degrees counter-clockwise: (x, y) -> (-y, x).
    # The matrix is written out explicitly instead of Transformation().rotate(90) to avoid
    # cos(90deg) = 6e-17 leaking into the content stream as a 25-digit number.
    # Strip's top edge ends up at the left margin, pages follow each other from bottom to top,
    # so the sheet reads correctly after turning it 90 degrees clockwise.
    current_y = out.mediabox.bottom + padding
    for page in pages:
        box = page.cropbox
        top_x = out.mediabox.left + padding + box.height * scale  # top-align pages in the strip
        matrix = (0, scale, -scale, 0, top_x + box.bottom * scale, current_y - box.left * scale)
        out.merge_transformed_page(page, Transformation(matrix))
        current_y += box.width * scale

    writer = PdfWriter()
    writer.add_page(out)

    output = BytesIO()
    writer.write(output)
    return output


def main():
    """Literally main"""
    parser = argparse.ArgumentParser(prog="pdfhstack", description="Merge pages of pdf documents horizontally")
    parser.add_argument("files", nargs="+", type=Path, help="files to merge")
    parser.add_argument(
        "-o",
        "--output",
        required=False,
        default="out.pdf",
        type=Path,
        help="output file",
    )
    parser.add_argument("-p", "--padding", type=float, default=5, help="margin in mm (default: 5)")
    args = parser.parse_args()

    args.output.write_bytes(hstack(args.files, padding=args.padding).getbuffer())


if __name__ == "__main__":
    main()
