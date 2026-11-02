import '../app_spacing.dart';
import 'package:flutter/material.dart';
import '../data/content_repository.dart';
import '../models/content.dart';
import '../widgets/emergency_widgets.dart';

class EmergencyDownloads extends StatefulWidget {
  final ContentRepository content;
  final List<EmergencyGuide> guides;
  const EmergencyDownloads({
    super.key,
    required this.content,
    required this.guides,
  });
  @override
  State<EmergencyDownloads> createState() => _EmergencyDownloadsState();
}

class _EmergencyDownloadsState extends State<EmergencyDownloads> {
  late List<EmergencyGuide> _guides;
  bool _busy = false;
  String? _message;
  @override
  void initState() {
    super.initState();
    _guides = widget.guides;
  }

  Future<void> _change(EmergencyGuide? guide) async {
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      List<EmergencyGuide> result;
      if (guide == null) {
        result = await widget.content.refreshEmergency();
      } else {
        result = await widget.content.saveOfflineGuide(guide.id);
      }
      if (mounted) {
        setState(() {
          _guides = result;
          _message = widget.content.warning == null
              ? (guide == null
                    ? 'Published guides synced and saved for offline use.'
                    : 'Guide and illustrations saved on this device.')
              : 'Could not refresh all content. Available local guidance has been kept. Retry when connected.';
        });
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => _message =
              'Could not change the offline copy. Your existing guidance has been kept. Check your connection and retry.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _remove(EmergencyGuide guide) async {
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      await widget.content.removeOfflineGuide(guide.id);
      final guides = await widget.content.currentEmergencyCatalogue();
      if (mounted)
        setState(() {
          _guides = guides;
          _message =
              'Offline copy removed. It will stay off this device until you choose Save offline.';
        });
    } catch (_) {
      if (mounted)
        setState(
          () => _message = 'Could not remove the offline copy. Please retry.',
        );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Offline guides')),
    body: ListView(
      padding: const EdgeInsets.all(AppSpacing.screen),
      children: [
        const EmergencyNotice(
          title: 'Keep guidance on your phone',
          message:
              'Published guides and their illustrations download automatically while connected. Removed copies stay removed until you save them again. Open the app online once before relying on offline guidance.',
        ),
        const SizedBox(height: 16),
        OutlinedButton.icon(
          onPressed: _busy ? null : () => _change(null),
          icon: const Icon(Icons.refresh),
          label: const Text('Refresh available guides'),
        ),
        if (_busy)
          const LinearProgressIndicator(
            semanticsLabel: 'Updating offline guides',
          ),
        if (_message != null)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Semantics(liveRegion: true, child: Text(_message!)),
          ),
        if (_guides.isEmpty)
          const Text('No guides are available yet. Retry when connected.'),
        for (final guide in _guides) ...[
          const SizedBox(height: 24),
          Text(guide.title, style: Theme.of(context).textTheme.titleMedium),
          Text(
            !guide.available
                ? 'Instructions unavailable; review required'
                : guide.savedOffline
                ? 'Saved on this device'
                : 'Internet needed until downloaded',
          ),
          if (guide.available && !guide.legacy)
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                TextButton.icon(
                  onPressed: _busy ? null : () => _change(guide),
                  icon: const Icon(Icons.download_outlined),
                  label: Text(
                    guide.savedOffline
                        ? (widget.content.hasUpdate(guide)
                              ? 'Download updated guide'
                              : 'Update offline copy')
                        : 'Save offline',
                  ),
                ),
                if (guide.savedOffline)
                  TextButton.icon(
                    onPressed: _busy ? null : () => _remove(guide),
                    icon: const Icon(Icons.delete_outline),
                    label: const Text('Remove offline copy'),
                  ),
              ],
            ),
        ],
      ],
    ),
  );
}
