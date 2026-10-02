from dataclasses import dataclass
from pathlib import Path
from bs4 import BeautifulSoup


@dataclass
class Page:
    path: Path
    root: Path
    html: str
    soup: BeautifulSoup

    @property
    def relative_path(self) -> str:
        return str(self.path.relative_to(self.root)).replace("\\", "/")


class BarklyCrawler:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir.resolve()

    def pages(self):
        for path in sorted(self.output_dir.rglob("*.html")):
            html = path.read_text(encoding="utf-8", errors="replace")
            yield Page(
                path=path,
                root=self.output_dir,
                html=html,
                soup=BeautifulSoup(html, "html.parser"),
            )

    def json_files(self):
        yield from sorted(self.output_dir.rglob("*.json"))
