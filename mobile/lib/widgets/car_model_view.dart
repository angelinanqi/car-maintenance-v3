import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:model_viewer_plus/model_viewer_plus.dart';
import '../app_theme.dart';
import 'design_widgets.dart';

class CarPin {
  final String label;
  final Color color;
  final VoidCallback onTap;
  const CarPin({required this.label, required this.color, required this.onTap});
}

/// The supplied Corolla GLB, bundled locally. Hotspots rotate with the model.
class CarModelView extends StatefulWidget {
  final List<CarPin> pins;
  final bool compact;
  const CarModelView({super.key, this.pins = const [], this.compact = false});
  @override
  State<CarModelView> createState() => _CarModelViewState();
}

class _CarModelViewState extends State<CarModelView> {
  Timer? _timeout;
  bool _failed = false;
  int _attempt = 0;

  @override
  void initState() {
    super.initState();
  }

  void _startTimeout() {
    _timeout?.cancel();
    _timeout = Timer(const Duration(seconds: 25), () {
      if (mounted) setState(() => _failed = true);
    });
  }

  @override
  void dispose() {
    _timeout?.cancel();
    super.dispose();
  }

  void _message(String message) {
    if (!mounted) return;
    if (message == 'loaded') {
      _timeout?.cancel();
    } else if (message == 'error') {
      _timeout?.cancel();
      setState(() => _failed = true);
    } else {
      final index = int.tryParse(message);
      if (index != null && index >= 0 && index < widget.pins.length)
        widget.pins[index].onTap();
    }
  }

  @override
  Widget build(BuildContext context) {
    final active = TickerMode.valuesOf(context).enabled;
    if (!active) _timeout?.cancel();
    final supported =
        !kIsWeb &&
        (Theme.of(context).platform == TargetPlatform.android ||
            Theme.of(context).platform == TargetPlatform.iOS);
    const positions = [
      '-1.15m 0.95m 1.35m',
      '-0.85m 1.4m 1.8m',
      '-1.15m 0.95m -1.35m',
    ];
    return SurfaceCard(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 8),
      child: Column(
        children: [
          Row(
            children: [
              const StatusPill(
                '3D view',
                color: AppColors.ink,
                foreground: Color(0xFFFFE08A),
              ),
              const SizedBox(width: 12),
              const Expanded(
                child: Text(
                  'Drag to rotate · tap a pin',
                  style: TextStyle(color: AppColors.muted, fontSize: 13),
                ),
              ),
            ],
          ),
          SizedBox(
            height: supported && !_failed ? (widget.compact ? 110 : 170) : null,
            child: !active
                ? const SizedBox.shrink()
                : supported && !_failed
                ? ModelViewer(
                    key: ValueKey(
                      'corolla-$_attempt-${widget.compact}-${widget.pins.map((pin) => '${pin.label}:${pin.color.toARGB32()}').join('|')}',
                    ),
                    src: 'assets/models/corolla.glb',
                    alt: 'Interactive Toyota Corolla with maintenance markers',
                    cameraControls: true,
                    autoRotate: false,
                    ar: false,
                    disableZoom: true,
                    disablePan: true,
                    interactionPrompt: InteractionPrompt.none,
                    cameraOrbit: '-90deg 76deg ${widget.compact ? '4m' : '6m'}',
                    fieldOfView: '28deg',
                    backgroundColor: Colors.white,
                    environmentImage: 'neutral',
                    shadowIntensity: .5,
                    debugLogging: false,
                    innerModelViewerHtml: [
                      for (
                        var i = 0;
                        i < widget.pins.length && i < positions.length;
                        i++
                      )
                        '<button slot="hotspot-$i" data-position="${positions[i]}" data-normal="-1 0 0" class="pin" style="background:#${widget.pins[i].color.toARGB32().toRadixString(16).substring(2)}" aria-label="${const HtmlEscape().convert(widget.pins[i].label)}" onclick="Maintenance.postMessage(\'$i\')">${i + 1}</button>',
                    ].join(),
                    relatedCss:
                        '.pin{width:30px;height:30px;border-radius:50%;border:2px solid white;color:#2b2100;font:700 15px sans-serif;box-shadow:0 1px 3px #6b5a2e66;cursor:pointer}model-viewer{--progress-bar-color:#ffc21a}',
                    relatedJs:
                        "const car=document.querySelector('model-viewer'); car.addEventListener('load',()=>Maintenance.postMessage('loaded')); car.addEventListener('error',()=>Maintenance.postMessage('error'));",
                    onWebViewCreated: (controller) async {
                      _startTimeout();
                      try {
                        await controller.addJavaScriptChannel(
                          'Maintenance',
                          onMessageReceived: (message) =>
                              _message(message.message),
                        );
                      } catch (_) {
                        _message('error');
                      }
                    },
                  )
                : Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(
                          Icons.directions_car_outlined,
                          size: 56,
                          color: AppColors.muted,
                        ),
                        Text(
                          supported
                              ? '3D view could not load'
                              : '3D view is available on Android and iOS',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        if (supported)
                          TextButton(
                            onPressed: () {
                              setState(() {
                                _failed = false;
                                _attempt++;
                              });
                              _startTimeout();
                            },
                            child: const Text('Retry 3D view'),
                          ),
                      ],
                    ),
                  ),
          ),
          if (widget.pins.isNotEmpty && (!supported || _failed))
            Wrap(
              spacing: 6,
              children: [
                for (var i = 0; i < widget.pins.length && i < 3; i++)
                  TextButton(
                    onPressed: widget.pins[i].onTap,
                    child: Text(
                      '${i + 1} · ${widget.pins[i].label}',
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
              ],
            ),
        ],
      ),
    );
  }
}
