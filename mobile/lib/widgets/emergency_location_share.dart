import 'package:flutter/material.dart';
import 'package:share_plus/share_plus.dart';
import 'package:geolocator/geolocator.dart';
import '../data/accident_location.dart';
import 'preview_mode.dart';

class EmergencyLocationShare extends StatefulWidget {
  final Future<Position> Function()? locate;
  final Future<ShareResult> Function(ShareParams)? share;
  const EmergencyLocationShare({super.key, this.locate, this.share});
  @override
  State<EmergencyLocationShare> createState() => _EmergencyLocationShareState();
}

class _EmergencyLocationShareState extends State<EmergencyLocationShare> {
  bool _busy = false;
  String? _error;

  Future<void> _share(BuildContext buttonContext) async {
    if (_busy) return;
    if (previewExternalActions) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Preview only. Your location is not retrieved or shared.',
          ),
        ),
      );
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final position = await (widget.locate ?? AccidentLocation().position)();
      if (!mounted || !buttonContext.mounted) return;
      final box = buttonContext.findRenderObject() as RenderBox?;
      final lat = position.latitude.toStringAsFixed(6);
      final lng = position.longitude.toStringAsFixed(6);
      final map = Uri.https('www.google.com', '/maps/search/', {
        'api': '1',
        'query': '$lat,$lng',
      });
      await (widget.share ?? SharePlus.instance.share)(
        ShareParams(
          title: 'My roadside location',
          text:
              'I need roadside assistance. My current location is $lat, $lng.\n$map',
          sharePositionOrigin: box == null
              ? null
              : box.localToGlobal(Offset.zero) & box.size,
        ),
      );
    } on AccidentLocationException {
      if (mounted)
        setState(
          () => _error =
              'Location is unavailable. Check device location and app permission, then retry. You can still call for help.',
        );
    } catch (_) {
      if (mounted)
        setState(
          () => _error =
              'Could not prepare location sharing. Check location access and retry. You can still call for help.',
        );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Builder(
        builder: (buttonContext) => OutlinedButton.icon(
          onPressed: _busy ? null : () => _share(buttonContext),
          icon: const Icon(Icons.share_location_outlined),
          label: Text(_busy ? 'Getting location…' : 'Share my location'),
        ),
      ),
      const Text(
        'Choose a trusted contact in the share sheet. GPS may work offline; sending the message requires connectivity.',
      ),
      if (_error != null) Semantics(liveRegion: true, child: Text(_error!)),
    ],
  );
}
