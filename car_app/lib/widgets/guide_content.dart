import 'package:flutter/material.dart';
import 'package:flutter_html/flutter_html.dart';
import 'package:url_launcher/url_launcher.dart';

class GuideContent extends StatelessWidget {
  final String content;
  const GuideContent({super.key, required this.content});

  Future<void> _open(BuildContext context, String? value) async {
    final uri = Uri.tryParse(value ?? '');
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
  Widget build(BuildContext context) => Html(
    data: content,
    onlyRenderTheseTags: {
      'html',
      'body',
      'div',
      'span',
      'p',
      'h1',
      'h2',
      'h3',
      'strong',
      'b',
      'em',
      'i',
      'u',
      's',
      'del',
      'ul',
      'ol',
      'li',
      'blockquote',
      'pre',
      'code',
      'br',
      'hr',
      'a',
      'img',
      'iframe',
    },
    onLinkTap: (url, attributes, element) => _open(context, url),
    extensions: [
      TagExtension(
        tagsToExtend: {'img'},
        builder: (extension) {
          final uri = Uri.tryParse(extension.attributes['src'] ?? '');
          if (uri == null ||
              !['https', 'http'].contains(uri.scheme) ||
              uri.host.isEmpty) {
            return const Text('Image unavailable.');
          }
          return Image.network(
            uri.toString(),
            semanticLabel: extension.attributes['alt'],
            fit: BoxFit.contain,
            errorBuilder: (_, _, _) => const Text('Image could not be loaded.'),
          );
        },
      ),
      TagExtension(
        tagsToExtend: {'iframe'},
        builder: (extension) {
          final uri = Uri.tryParse(extension.attributes['src'] ?? '');
          const hosts = {
            'youtube.com',
            'www.youtube.com',
            'youtube-nocookie.com',
            'www.youtube-nocookie.com',
            'youtu.be',
          };
          if (uri == null ||
              !['https', 'http'].contains(uri.scheme) ||
              !hosts.contains(uri.host)) {
            return const Text(
              'This embedded content is unavailable in the reader.',
            );
          }
          return TextButton.icon(
            onPressed: () => _open(context, uri.toString()),
            icon: const Icon(Icons.play_circle_outline),
            label: const Text('Open YouTube video'),
          );
        },
      ),
    ],
    style: {
      'body': Style(margin: Margins.zero),
      'iframe': Style(width: Width.auto(), height: Height.auto()),
    },
  );
}
