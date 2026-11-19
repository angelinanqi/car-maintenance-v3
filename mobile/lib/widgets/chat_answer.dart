import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';
import 'package:markdown/markdown.dart' as md;
import 'package:url_launcher/url_launcher.dart';

/// Renders answer text and citations to sources supplied with the reply.
class ChatAnswer extends StatelessWidget {
  final String text;
  final Map<String, String> citationTitles;
  const ChatAnswer({
    super.key,
    required this.text,
    this.citationTitles = const {},
  });

  Future<void> _openLink(BuildContext context, String? href) async {
    final uri = Uri.tryParse(href ?? '');
    if (uri == null ||
        !['https', 'http'].contains(uri.scheme) ||
        uri.host.isEmpty) {
      return;
    }
    try {
      if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
        throw StateError('No link handler');
      }
    } catch (_) {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not open the link.')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final body = theme.textTheme.bodyLarge?.copyWith(height: 1.6);
    final heading = body?.copyWith(fontWeight: FontWeight.w600);
    // SelectionArea supports inline widgets while keeping the answer selectable.
    return SelectionArea(
      child: MarkdownBody(
        // MarkdownBody caches the parsed content even when its builders change.
        key: ValueKey(jsonEncode(citationTitles)),
        data: text,
        // CommonMark formats prose and steps without generated GFM tables.
        extensionSet: md.ExtensionSet.commonMark,
        inlineSyntaxes: [_CitationSyntax(citationTitles)],
        builders: {_CitationSyntax.tag: _CitationBuilder()},
        // Never load model-written network, file or asset image references.
        imageBuilder: (_, _, _) => const SizedBox.shrink(),
        onTapLink: (_, href, _) => _openLink(context, href),
        styleSheet: MarkdownStyleSheet.fromTheme(theme).copyWith(
          p: body,
          h1: heading,
          h2: heading,
          h3: heading,
          h4: heading,
          h5: heading,
          h6: heading,
          listBullet: body,
          blockSpacing: 12,
        ),
      ),
    );
  }
}

class _CitationSyntax extends md.InlineSyntax {
  static const tag = 'chat-citation';
  final Map<String, String> titles;

  _CitationSyntax(this.titles)
    : super(r'\[([SP]\d+(?:\s*,\s*[SP]\d+)*)\](?!\()', startCharacter: 0x5B);

  @override
  bool onMatch(md.InlineParser parser, Match match) {
    // Restored replies can still contain markers for sources that were removed.
    final names = match[1]!
        .split(',')
        .map((label) => titles[label.trim()])
        .whereType<String>()
        .toSet();
    for (final name in names) {
      parser.addNode(md.Element.text(tag, name));
    }
    return true;
  }
}

class _CitationBuilder extends MarkdownElementBuilder {
  @override
  Widget visitElementAfterWithContext(
    BuildContext context,
    md.Element element,
    TextStyle? preferredStyle,
    TextStyle? parentStyle,
  ) {
    final theme = Theme.of(context);
    final name = element.textContent;
    return Text.rich(
      TextSpan(
        children: [
          WidgetSpan(
            alignment: PlaceholderAlignment.middle,
            child: Tooltip(
              message: name,
              excludeFromSemantics: true,
              child: Container(
                margin: const EdgeInsets.symmetric(horizontal: 2),
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: ShapeDecoration(
                  color: theme.colorScheme.secondaryContainer,
                  shape: const StadiumBorder(),
                ),
                child: Text(
                  name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: theme.textTheme.labelMedium?.copyWith(
                    color: theme.colorScheme.onSecondaryContainer,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
