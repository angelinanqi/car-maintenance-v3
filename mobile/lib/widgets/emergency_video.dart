import 'dart:io';
import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';

/// Uploaded MP4s use the downloaded file first, with no autoplay.
class EmergencyVideo extends StatefulWidget {
  final String url;
  final String? localPath;
  const EmergencyVideo({super.key, required this.url, this.localPath});

  @override
  State<EmergencyVideo> createState() => _EmergencyVideoState();
}

class _EmergencyVideoState extends State<EmergencyVideo> {
  VideoPlayerController? _controller;
  bool _failed = false;

  @override
  void initState() {
    super.initState();
    _initialize();
  }

  Future<void> _initialize() async {
    try {
      final local = widget.localPath;
      if (local != null && !await File(local).exists()) {
        throw const FileSystemException('Downloaded video is missing');
      }
      if (!mounted) return;
      final controller = local != null
          ? VideoPlayerController.file(File(local))
          : VideoPlayerController.networkUrl(Uri.parse(widget.url));
      _controller = controller;
      controller.addListener(_changed);
      await controller.initialize().timeout(const Duration(seconds: 30));
      if (mounted) setState(() {});
    } catch (_) {
      if (mounted) setState(() => _failed = true);
    }
  }

  void _changed() {
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    _controller?.removeListener(_changed);
    _controller?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final controller = _controller;
    if (_failed || controller?.value.hasError == true) {
      return const Text(
        'Video unavailable. Use the written instructions. Download the guide again when connected.',
      );
    }
    if (controller == null || !controller.value.isInitialized) {
      return const Padding(
        padding: EdgeInsets.all(12),
        child: Text(
          'Loading supporting video. Continue with the written instructions.',
        ),
      );
    }
    return Column(
      children: [
        ConstrainedBox(
          constraints: const BoxConstraints(maxHeight: 320),
          child: AspectRatio(
            aspectRatio: controller.value.aspectRatio > 0
                ? controller.value.aspectRatio
                : 16 / 9,
            child: VideoPlayer(controller),
          ),
        ),
        VideoProgressIndicator(
          controller,
          allowScrubbing: true,
          padding: const EdgeInsets.symmetric(vertical: 12),
        ),
        TextButton.icon(
          icon: Icon(
            controller.value.isPlaying ? Icons.pause : Icons.play_arrow,
          ),
          label: Text(
            controller.value.isPlaying ? 'Pause video' : 'Play video',
          ),
          onPressed: () async {
            try {
              if (controller.value.isPlaying) {
                await controller.pause();
              } else {
                if (controller.value.position >= controller.value.duration) {
                  await controller.seekTo(Duration.zero);
                }
                await controller.play();
              }
            } catch (_) {
              if (mounted) setState(() => _failed = true);
            }
          },
        ),
      ],
    );
  }
}
