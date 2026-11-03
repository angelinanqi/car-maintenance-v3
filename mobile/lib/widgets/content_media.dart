import 'dart:io';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../data/content_repository.dart';
import 'emergency_video.dart';

/// Shared by published guides, emergency steps, and resolved chat media.
class ContentMediaList extends StatelessWidget {
  final List<Map<String, dynamic>> items;
  final ContentRepository? content;
  final Widget Function(Map<String, dynamic>)? imageBuilder;
  const ContentMediaList({
    super.key,
    required this.items,
    this.content,
    this.imageBuilder,
  });

  Uri? _url(Map<String, dynamic> item) {
    final uri = Uri.tryParse(item['url'] as String? ?? '');
    if (uri == null ||
        !['https', 'http'].contains(uri.scheme) ||
        uri.host.isEmpty ||
        uri.userInfo.isNotEmpty)
      return null;
    final seconds = (item['start_seconds'] as num? ?? 0).toInt();
    if (item['kind'] != 'video' || seconds <= 0) return uri;
    if ([
      'youtu.be',
      'youtube.com',
      'www.youtube.com',
      'm.youtube.com',
      'youtube-nocookie.com',
      'www.youtube-nocookie.com',
    ].contains(uri.host)) {
      final query = {...uri.queryParameters}
        ..remove('start')
        ..remove('t');
      if (uri.path.startsWith('/embed/')) {
        query['start'] = '$seconds';
      } else {
        query['t'] = '${seconds}s';
      }
      return uri.replace(queryParameters: query, fragment: '');
    }
    return uri.replace(fragment: 't=$seconds');
  }

  Future<void> _open(BuildContext context, Uri uri) async {
    try {
      if (!await launchUrl(uri, mode: LaunchMode.externalApplication))
        throw StateError('No link handler');
    } catch (_) {
      if (context.mounted)
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Could not open this media.')),
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (content != null) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          for (final item in items)
            _ResolvedMedia(
              key: ValueKey(
                '${item['media_id'] ?? item['id']}:${item['sha256']}',
              ),
              item: item,
              content: content!,
            ),
        ],
      );
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final item in items)
          if (_url(item) != null)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text(
                        '${item['title'] ?? 'Related media'}${item['source_label'] != null ? ' [${item['source_label']}]' : ''}',
                        style: Theme.of(context).textTheme.titleSmall,
                      ),
                      if (item['step_title'] != null)
                        Text('Step: ${item['step_title']}'),
                      if (item['kind'] == 'image')
                        Padding(
                          padding: const EdgeInsets.symmetric(vertical: 8),
                          child:
                              imageBuilder?.call(item) ??
                              (item['localImagePath'] is String
                                  ? Image.file(
                                      File(item['localImagePath'] as String),
                                      height: 280,
                                      fit: BoxFit.contain,
                                      semanticLabel:
                                          item['description'] as String?,
                                      errorBuilder: (_, _, _) => const Text(
                                        'Illustration unavailable. Use the written instructions.',
                                      ),
                                    )
                                  : Image.network(
                                      _url(item).toString(),
                                      height: 280,
                                      fit: BoxFit.contain,
                                      semanticLabel:
                                          item['description'] as String?,
                                      errorBuilder: (_, _, _) => const Text(
                                        'Illustration unavailable. Use the written instructions.',
                                      ),
                                    )),
                        ),
                      if ((item['description'] as String? ?? '').isNotEmpty)
                        Text(item['description'] as String),
                      if ((item['vehicle_context'] as String? ?? '').isNotEmpty)
                        Text('Applies to: ${item['vehicle_context']}'),
                      if ((item['source_reference'] as String? ?? '')
                          .isNotEmpty)
                        Text(
                          'Source: ${item['source_reference']}',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                      if (item['kind'] == 'video' && item['asset_id'] is String)
                        EmergencyVideo(
                          key: ValueKey(
                            '${item['asset_id']}:${item['localMediaPath']}',
                          ),
                          url: _url(item).toString(),
                          localPath: item['localMediaPath'] as String?,
                        ),
                      if (item['kind'] == 'video' &&
                          item['asset_id'] is! String)
                        TextButton.icon(
                          icon: const Icon(Icons.play_circle_outline),
                          onPressed: () => _open(context, _url(item)!),
                          label: Text(
                            'Watch from ${((item['start_seconds'] as num? ?? 0).toInt() ~/ 60)}:${((item['start_seconds'] as num? ?? 0).toInt() % 60).toString().padLeft(2, '0')} · Opens externally',
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ),
      ],
    );
  }
}

class _ResolvedMedia extends StatefulWidget {
  final Map<String, dynamic> item;
  final ContentRepository content;
  const _ResolvedMedia({super.key, required this.item, required this.content});
  @override
  State<_ResolvedMedia> createState() => _ResolvedMediaState();
}

class _ResolvedMediaState extends State<_ResolvedMedia> {
  late Future<Map<String, dynamic>> _item;
  @override
  void initState() {
    super.initState();
    _item = widget.content.localEmergencyMedia(widget.item);
  }

  @override
  void didUpdateWidget(covariant _ResolvedMedia oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.item != widget.item)
      _item = widget.content.localEmergencyMedia(widget.item);
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<Map<String, dynamic>>(
    future: _item,
    builder: (_, snapshot) {
      if (!snapshot.hasData)
        return const Text(
          'Loading supporting media. Written guidance is available above.',
        );
      return ContentMediaList(items: [snapshot.data!]);
    },
  );
}
