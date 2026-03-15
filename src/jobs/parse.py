"""Reusable HTML parsing helpers for BLS Occupational Outlook Handbook pages."""

import re

from bs4 import BeautifulSoup


def clean(text: str) -> str:
    """Normalise whitespace in extracted text."""
    return re.sub(r"\s+", " ", text).strip()


def parse_ooh_page(html_path: str) -> str:
    """Parse a BLS OOH detail page into a clean Markdown document.

    Args:
        html_path: Path to the raw HTML file.

    Returns:
        A Markdown string representing the occupation page.
    """
    with open(html_path, "r") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    md: list[str] = []

    # --- Title ---
    h1 = soup.find("h1")
    title = clean(h1.get_text()) if h1 else "Unknown Occupation"
    md.append(f"# {title}")
    md.append("")

    # --- Source URL ---
    canonical = soup.find("link", rel="canonical")
    if canonical:
        md.append(f"**Source:** {canonical['href']}")
        md.append("")

    # --- Quick Facts ---
    qf_table = soup.find("table", id="quickfacts")
    if qf_table:
        md.append("## Quick Facts")
        md.append("")
        md.append("| Field | Value |")
        md.append("|-------|-------|")
        for row in qf_table.find("tbody").find_all("tr"):
            th = row.find("th")
            td = row.find("td")
            if th and td:
                field = clean(th.get_text())
                value = clean(td.get_text())
                md.append(f"| {field} | {value} |")
        md.append("")

    # --- Tab sections ---
    panes = soup.find("div", id="panes")
    if not panes:
        return "\n".join(md)

    tab_ids = [
        "tab-1",
        "tab-2",
        "tab-3",
        "tab-4",
        "tab-5",
        "tab-6",
        "tab-7",
        "tab-8",
        "tab-9",
    ]
    # Skip tab-1 (Summary, covered by quick facts), tab-7 (State & Area Data),
    # tab-8 (Similar Occupations), tab-9 (Contacts)
    _SKIP_TABS = {"tab-1", "tab-7", "tab-8", "tab-9"}

    for tab_id in tab_ids:
        tab_div = panes.find("div", id=tab_id)
        if not tab_div:
            continue

        article = tab_div.find("article")
        if not article:
            article = tab_div

        h2 = article.find("h2")
        if not h2:
            continue
        section_title = (
            clean(h2.find("span").get_text()) if h2.find("span") else clean(h2.get_text())
        )

        if tab_id in _SKIP_TABS:
            continue

        md.append(f"## {section_title}")
        md.append("")

        # Pay chart
        chart_div = article.find("div", class_="ooh-chart")
        if chart_div:
            chart_subtitle = chart_div.find("p")
            dts = chart_div.find("dl")
            if dts:
                items: list[tuple[str, str]] = []
                dt_list = dts.find_all("dt")
                dd_list = dts.find_all("dd")
                for dt, dd in zip(dt_list, dd_list):
                    label = clean(dt.get_text())
                    for s in dd.find_all("span"):
                        val_text = clean(s.get_text())
                        if val_text and (val_text.startswith("$") or val_text.endswith("%")):
                            items.append((label, val_text))
                            break
                if items:
                    subtitle = clean(chart_subtitle.get_text()) if chart_subtitle else ""
                    if subtitle:
                        md.append(f"*{subtitle}*")
                        md.append("")
                    for label, val in items:
                        md.append(f"- **{label}**: {val}")
                    md.append("")

        # Remaining content
        for elem in article.children:
            if not hasattr(elem, "name"):
                continue
            if elem.name == "h2":
                continue
            if elem.name == "div" and "ooh-chart" in elem.get("class", []):
                continue
            if elem.name == "div" and "ooh_right_img" in elem.get("class", []):
                continue
            if elem.name == "h3":
                md.append(f"### {clean(elem.get_text())}")
                md.append("")
            elif elem.name == "p":
                text = clean(elem.get_text())
                if text:
                    md.append(text)
                    md.append("")
            elif elem.name == "ul":
                for li in elem.find_all("li"):
                    md.append(f"- {clean(li.get_text())}")
                md.append("")
            elif elem.name == "table":
                if elem.get("id") == "outlook-table":
                    continue
                rows = elem.find_all("tr")
                if rows:
                    table_data = []
                    for row in rows:
                        cells = row.find_all(["td", "th"])
                        row_data = [clean(c.get_text()) for c in cells]
                        if row_data and any(row_data):
                            table_data.append(row_data)
                    if table_data:
                        max_cols = max(len(r) for r in table_data)
                        for r in table_data:
                            while len(r) < max_cols:
                                r.append("")
                        md.append("| " + " | ".join(["---"] * max_cols) + " |")
                        for row_data in table_data:
                            md.append("| " + " | ".join(row_data) + " |")
                        md.append("")

        # Employment projections table (Job Outlook tab)
        if tab_id == "tab-6":
            outlook_table = article.find("table", id="outlook-table")
            if outlook_table:
                md.append("### Employment Projections")
                md.append("")
                tbody = outlook_table.find("tbody")
                if tbody:
                    for row in tbody.find_all("tr"):
                        cells = row.find_all(["td", "th"])
                        values = [clean(c.get_text()) for c in cells]
                        if values:
                            labels = [
                                "Occupational Title",
                                "SOC Code",
                                "Employment 2024",
                                "Projected Employment 2034",
                                "Change % 2024-34",
                                "Change Numeric 2024-34",
                            ]
                            for label, val in zip(labels, values):
                                if val and val != "Get data":
                                    md.append(f"- **{label}:** {val}")
                            md.append("")

    # --- Last Modified ---
    update_p = soup.find("p", class_="update")
    if update_p:
        md.append("---")
        md.append(f"*{clean(update_p.get_text())}*")
        md.append("")

    return "\n".join(md)
