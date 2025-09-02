import re
from typing import Dict, Generator, Tuple, Union, Optional, Any

import bs4

from ..scraper import Scraper
from ..teletext import Teletext, TeletextPage
from ..teletext.unico import G1_TO_UNICODE_MAPPING


class SWR_RP(Scraper):

    NAME = "swr_rp"
    STREAM = "rp"

    PAGE_CATEGORIES = {
        100: "index",
    }

    _RE_PAGE_LINK = re.compile(r".*page=(\d\d\d).*")
    _RE_SUB_PAGE_LINK = re.compile(r".*sub=(\d+).*")

    def iter_pages(self) -> Generator[Tuple[int, int, bs4.BeautifulSoup], None, None]:
        page_index = 100
        sub_page_index = 1
        while page_index < 900:
            url = f"https://wraps.swr.de/videotext/?page={page_index}&sub={sub_page_index}&stream={self.STREAM}"
            soup = self.get_soup(url)

            yield page_index, sub_page_index, soup

            ttx_info = {
                pre["id"]: pre.text
                for pre in soup.find("div", {"id": "ttxEnv"}).find_all("pre")
            }
            cur_page = int(ttx_info["ttxPageNum"])
            cur_sub_page = int(ttx_info["ttxSubpageNum"])
            num_sub_pages = int(ttx_info["ttxNumSubpages"])
            next_page = int(ttx_info["ttxNextPageNum"])

            if cur_page != page_index:
                raise AssertionError(f"Expected {page_index}, got {cur_page}")
            if cur_sub_page != sub_page_index:
                raise AssertionError(f"Expected {sub_page_index}, got {cur_sub_page}")

            if sub_page_index < num_sub_pages:
                sub_page_index += 1

            else:
                if next_page < page_index:
                    break
                page_index = next_page
                sub_page_index = 1


    def compare_pages(self, old: TeletextPage, new: TeletextPage) -> bool:
        if len(old.lines) != len(new.lines):
            return False
        if len(old.lines) < 1:
            return False
        # compare pages without the first line which includes the current date and time
        return old.lines[1:] == new.lines[1:]

    def to_teletext(self, content: bs4.BeautifulSoup) -> TeletextPage:
        tt = TeletextPage()

        container = content.find("div", {"id": "ttxPage"})
        for row in container.find_all("pre", {"class": "ttxRow"}):

            tt.new_line()
            self._recursive_row_children(row, tt)

        return tt

    def _recursive_row_children(self, row: bs4.Tag, tt: TeletextPage):
        COLORS = "brgylmcw"
        bg_color = "b"
        fg_color = "w"
        cur_link = None
        cur_special_char = None
        for i, elem in enumerate(row.recursiveChildGenerator()):
            if isinstance(elem, bs4.Tag):
                if elem.name == "a":
                    match = self._RE_PAGE_LINK.match(elem.attrs["href"])
                    if match:
                        match2 = self._RE_SUB_PAGE_LINK.match(elem.attrs["href"])
                        cur_link = int(match.groups()[0])
                        if match2:
                            cur_link = (cur_link, int(match2.groups()[0]))
                elif elem.name == "span":
                    klasses = elem.attrs.get("class")
                    for klass in klasses:
                        if klass.startswith("bg"):
                            bg_color = COLORS[int(klass[2:])]
                        elif klass.startswith("fg"):
                            fg_color = COLORS[int(klass[2:])]
                        elif klass.startswith("g1s") or klass.startswith("g1c"):
                            cur_special_char = chr(G1_TO_UNICODE_MAPPING[int(klass[4:], 16)])
                            if klass.startswith("g1c"):
                                fg_color = COLORS[int(klass[3:4])]

            elif isinstance(elem, bs4.NavigableString):
                tt.add_block(TeletextPage.Block(
                    cur_special_char or elem.text, color=fg_color,bg_color=bg_color,
                    link=cur_link,
                ))
                cur_link = None
                cur_special_char = None

    @classmethod
    def legacy_bytes_to_content(cls, content: bytes) -> Any:
        return cls.to_soup(content.decode("utf-8"))


class SWR_BW(SWR_RP):
    NAME = "swr_bw"
    STREAM = "bw"
