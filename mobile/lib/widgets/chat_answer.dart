import 'package:flutter/material.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';
import 'package:markdown/markdown.dart' as md;
import 'package:url_launcher/url_launcher.dart';

/// Answer text only. Original source assets use ChatAttachment's access checks.
class ChatAnswer extends StatelessWidget {
  final String text;
  const ChatAnswer({super.key, required this.text});

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
    return MarkdownBody(
      data: text,
      selectable: true,
      // CommonMark formats prose and steps without generated GFM tables.
      extensionSet: md.ExtensionSet.commonMark,
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
    );
  }
}
