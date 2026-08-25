from pathlib import Path
from bs4 import BeautifulSoup
from bs4.element import Tag, NavigableString
from app.models.html_node import HTMLNode


class HTMLParser:
    def __init__(self):
        self.position = 0
        self.heading_stack = []

    def parse(self, html_file):
        self.position = 0
        self.heading_stack = []

        html_file = Path(html_file)
        document_name = html_file.stem

        with html_file.open(
            "r",
            encoding="utf-8",
        ) as file:
            html = file.read()

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        root = HTMLNode(
            document_name=document_name,
            tag="document",
            position=self._next_position(),
        )

        container = soup.body if soup.body else soup

        for element in container.children:
            if isinstance(
                element,
                NavigableString,
            ):
                continue

            if not isinstance(element, Tag):
                continue

            if self._is_heading(element):
                heading_node = self._build_node(
                    element,
                    document_name,
                )

                self._insert_heading(
                    node=heading_node,
                    level=int(element.name[1]),
                    root=root,
                )

            else:
                node = self._build_node(
                    element,
                    document_name,
                )

                self._current_parent(root).add_child(node)

        return root

    def _build_node(
        self,
        element: Tag,
        document_name: str,
    ):
        node = HTMLNode(
            document_name=document_name,
            tag=element.name,
            attributes=dict(element.attrs),
            position=self._next_position(),
        )

        for child in element.children:
            if isinstance(child, NavigableString):
                text = child.strip()

                if text:
                    if node.text:
                        node.text += " " + text
                    else:
                        node.text = text

            elif isinstance(child, Tag):
                if child.name == "br":
                    if node.text:
                        node.text += "\n"
                    else:
                        node.text = "\n"

                    continue

                child_node = self._build_node(
                    child,
                    document_name,
                )

                node.add_child(child_node)

        return node

    def _insert_heading(
        self,
        node,
        level,
        root,
    ):
        while self.heading_stack and self.heading_stack[-1][0] >= level:
            self.heading_stack.pop()

        if self.heading_stack:
            parent = self.heading_stack[-1][1]
        else:
            parent = root

        parent.add_child(node)

        self.heading_stack.append((level, node))

    def _current_parent(self, root):
        if self.heading_stack:
            return self.heading_stack[-1][1]

        return root

    def _is_heading(self, element):
        return element.name.startswith("h") and element.name[1:].isdigit()

    def _next_position(self):
        position = self.position
        self.position += 1
        return position
