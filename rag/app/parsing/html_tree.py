from pathlib import Path
from bs4 import BeautifulSoup
from bs4.element import Tag, NavigableString, Comment
from rag.app.models.html_node import HTMLNode


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
                if not isinstance(element, Comment) and element.strip():
                    text_node = HTMLNode(
                        document_name=document_name,
                        tag="p",
                        text=str(element),
                        content=[str(element)],
                        position=self._next_position(),
                    )
                    self._current_parent(root).add_child(text_node)
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

        root.set_depth()
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

        inline = {
            "strong",
            "em",
            "a",
            "span",
            "code",
            "b",
            "i",
            "u",
            "small",
            "sub",
            "sup",
            "s",
            "del",
            "mark",
        }

        def append_text(text):
            node.text = (node.text or "") + text
            if node.content and isinstance(node.content[-1], str):
                node.content[-1] += text
            else:
                node.content.append(text)

        def visit(child):
            if isinstance(child, Comment):
                return
            if isinstance(child, NavigableString):
                append_text(str(child))
            elif isinstance(child, Tag):
                if child.name == "br":
                    append_text("\n")
                elif child.name in inline:
                    self._next_position()
                    for part in child.children:
                        visit(part)
                else:
                    node.content.append(len(node.children))
                    node.add_child(self._build_node(child, document_name))

        for child in element.children:
            visit(child)

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