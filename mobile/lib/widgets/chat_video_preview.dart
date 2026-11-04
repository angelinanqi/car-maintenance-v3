import 'package:flutter/material.dart';

// Only construct thumbnails from a recognised YouTube URL and valid video ID.
// The existing answer contract already supplies timestamped URLs.
String? youtubeThumbnail(String url) {
  final uri = Uri.tryParse(url);
  if (uri == null || !['https', 'http'].contains(uri.scheme)) return null;
  final String? id;
  if (uri.host == 'youtu.be') {
    id = uri.pathSegments.firstOrNull;
  } else if ([
    'youtube.com',
    'www.youtube.com',
    'm.youtube.com',
  ].contains(uri.host)) {
    id = uri.queryParameters['v'];
  } else {
    return null;
  }
  if (id == null || !RegExp(r'^[a-zA-Z0-9_-]{11}$').hasMatch(id)) return null;
  return 'https://i.ytimg.com/vi/$id/mqdefault.jpg';
}

class ChatVideoPreview extends StatelessWidget {
  final Map<String, dynamic> video;
  final VoidCallback onTap;
  const ChatVideoPreview({super.key, required this.video, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final thumbnail = youtubeThumbnail(video['url'] as String? ?? '');
    final timestamp = video['timestamp'] as num?;
    final seconds = (timestamp ?? 0).toInt().clamp(0, 86400);
    final time =
        '${seconds ~/ 60}:${(seconds % 60).toString().padLeft(2, '0')}';
    const fallback = SizedBox(
      width: 88,
      height: 64,
      child: Icon(Icons.play_circle_outline, size: 32),
    );
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Material(
        color: theme.colorScheme.surfaceContainerLow,
        borderRadius: BorderRadius.circular(16),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: thumbnail == null
                      ? fallback
                      : Image.network(
                          thumbnail,
                          width: 88,
                          height: 64,
                          fit: BoxFit.cover,
                          excludeFromSemantics: true,
                          errorBuilder: (_, _, _) => fallback,
                        ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Related video · External tutorial',
                          style: theme.textTheme.labelSmall),
                      Text(
                        video['title'] as String? ?? 'Watch related video',
                        style: theme.textTheme.titleSmall,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'YouTube${video['channel_title'] == null || video['channel_title'] == '' ? '' : ' · ${video['channel_title']}'}'
                        '${timestamp == null ? '' : ' · $time'} · Opens externally',
                        style: theme.textTheme.bodySmall,
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${video['matched_using'] == 'title_and_description' ? 'Matched using its title and description. ' : video['matched_using'] == 'title' ? 'Matched using its title. ' : ''}'
                        '${video['vehicle_match'] == 'generic' ? 'Generic demonstration. ' : ''}'
                        'Content and vehicle compatibility have not been verified.',
                        style: theme.textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 4),
                const Icon(Icons.open_in_new, size: 16),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
