"""Build the customer-facing download with only print and viewing files."""
from pathlib import Path
import zipfile

LICENSE = """PRINT PLAY MAGIC — PERSONAL USE LICENSE

This license applies to the printable model and preview images in this download.
The purchaser may print, cut, fold, assemble, and display this model for personal,
non-commercial use. The files may be used to make personal copies for the purchaser
and their household.

Do not resell, redistribute, publish, or share the digital files, or use them to
produce items for sale. Copyright in the template and artwork remains with Print
Play Magic. This license does not transfer ownership of the digital files.

For questions about other uses, contact the template publisher before use.
"""


def create_download_archive(output: Path) -> None:
    output=Path(output)
    pdfs=sorted(output.glob('printable_*.pdf'))
    # One print-ready PDF only; colored and coloring variants remain separate
    # downloads in the project view, while this bundle uses the color PDF.
    pdf=next((p for p in pdfs if not p.stem.endswith('_coloring')),None)
    previews=[output/name for name in ('model_3d_preview.png','printable_preview.png')]
    with zipfile.ZipFile(output/'project.zip','w',zipfile.ZIP_DEFLATED) as archive:
        if pdf and pdf.is_file():archive.write(pdf,pdf.name)
        for image in previews:
            if image.is_file():archive.write(image,image.name)
        archive.writestr('LICENSE.txt',LICENSE)
