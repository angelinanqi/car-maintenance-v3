import 'package:flutter/material.dart';
import '../data/local_store.dart';
import '../models/content.dart';

/// Verify actual files rather than treating the guide flag as a media guarantee.
class EmergencyOfflineStatus extends StatefulWidget {
  final EmergencyGuide guide;
  final LocalStore store;
  const EmergencyOfflineStatus({
    super.key,
    required this.guide,
    required this.store,
  });
  @override
  State<EmergencyOfflineStatus> createState() => _EmergencyOfflineStatusState();
}

class _EmergencyOfflineStatusState extends State<EmergencyOfflineStatus> {
  late Future<String> _status;
  @override
  void initState() {
    super.initState();
    _status = _check();
  }

  @override
  void didUpdateWidget(covariant EmergencyOfflineStatus oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.guide != widget.guide || oldWidget.store != widget.store)
      _status = _check();
  }

  Future<String> _check() async {
    var images = 0, videos = 0, savedImages = 0, savedVideos = 0;
    try {
      for (final step in widget.guide.steps) {
        if (step.imageUrl.isNotEmpty || step.localImagePath != null) {
          images++;
          if (step.localImagePath != null &&
              await widget.store.hasEmergencyImage(step.localImagePath!))
            savedImages++;
        }
        for (final item in step.media) {
          final video = item['kind'] == 'video';
          if (video) {
            videos++;
          } else {
            images++;
          }
          final path = item['localMediaPath'] ?? item['localImagePath'];
          if (path is String &&
              await widget.store.hasEmergencyMedia(
                path,
                digest: item['sha256'] as String?,
                size: item['size_bytes'] as int?,
              )) {
            if (video) {
              savedVideos++;
            } else {
              savedImages++;
            }
          }
        }
      }
      if (images + videos == 0)
        return 'Written instructions only; no supporting media.';
      return [
        if (images > 0) 'Images: $savedImages/$images saved',
        if (videos > 0) 'Videos: $savedVideos/$videos saved',
        if (savedImages + savedVideos < images + videos)
          'Download missing media when connected.',
      ].join(' · ');
    } catch (_) {
      return 'Media availability could not be checked. Written instructions remain available.';
    }
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<String>(
    future: _status,
    builder: (_, snapshot) => Text(snapshot.data ?? 'Checking offline media…'),
  );
}
