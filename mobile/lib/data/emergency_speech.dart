import 'dart:async';
import 'package:flutter/widgets.dart';
import 'package:flutter_tts/flutter_tts.dart';
import '../models/content.dart';

/// Optional device speech; guide access never waits for voice initialization.
class EmergencySpeech extends ChangeNotifier with WidgetsBindingObserver {
  FlutterTts? _tts;
  Future<FlutterTts>? _ready;
  Future<void> _stopping = Future.value();
  int _request = 0;
  bool _disposed = false;
  bool _speaking = false;
  bool active = false;
  String? error;

  EmergencySpeech({FlutterTts? engine}) : _tts = engine {
    WidgetsBinding.instance.addObserver(this);
  }

  static String instruction(EmergencyGuide guide, int index) => [
    '${guide.title}. Step ${index + 1} of ${guide.steps.length}.',
    if (guide.isAccident)
      'For injuries, fire or immediate danger, call 999. This guide is for minor property damage with no injuries.',
    if (guide.safetyWarnings.isNotEmpty)
      'Safety warnings. ${guide.safetyWarnings}',
    if (index == 0 && guide.description.isNotEmpty) guide.description,
    guide.steps[index].title,
    guide.steps[index].description,
  ].join('\n\n');

  Future<FlutterTts> _initialize() async {
    final engine = _tts ??= FlutterTts();
    engine.setErrorHandler((_) {
      if (!_disposed && active) {
        _request++;
        _speaking = false;
        _ready = null;
        active = false;
        error = _unavailable;
        notifyListeners();
        unawaited(_stopEngine());
      }
    });
    engine.setCancelHandler(() {
      if (!_disposed && active && _speaking) {
        _request++;
        _speaking = false;
        active = false;
        notifyListeners();
      }
    });
    final language = await engine.isLanguageAvailable('en-GB') == true
        ? 'en-GB'
        : await engine.isLanguageAvailable('en-US') == true
        ? 'en-US'
        : null;
    if (language == null || await engine.setLanguage(language) != 1) {
      throw StateError('English voice unavailable');
    }
    await engine.setSpeechRate(0.45);
    await engine.awaitSpeakCompletion(true);
    return engine;
  }

  static const _unavailable =
      'Read aloud is unavailable. Check your device’s text-to-speech settings and downloaded English voice, then retry. You can keep using the written instructions.';

  Future<void> read(String text) async {
    if (_disposed || active || text.trim().isEmpty) return;
    final request = ++_request;
    active = true;
    error = null;
    notifyListeners();
    try {
      await _stopping;
      if (_disposed || request != _request) return;
      final engine = await (_ready ??= _initialize());
      if (_disposed || request != _request) return;
      // Keep each utterance below Android engine input limits. Every part must
      // complete before the next is spoken, so long reviewed steps stay intact.
      for (final part in _parts(text.trim())) {
        if (_disposed || request != _request) return;
        _speaking = true;
        final result = await engine.speak(part, focus: true);
        if (_disposed || request != _request) return;
        _speaking = false;
        if (result != 1) throw StateError('Speech did not complete');
      }
    } catch (_) {
      if (!_disposed && request == _request) {
        error = _unavailable;
        _ready =
            null; // Retry voice setup after the user changes device settings.
        unawaited(_stopEngine());
      }
    } finally {
      if (!_disposed && request == _request) {
        _speaking = false;
        active = false;
        notifyListeners();
      }
    }
  }

  Iterable<String> _parts(String text) sync* {
    var offset = 0;
    while (offset < text.length) {
      var end = (offset + 3000).clamp(0, text.length);
      if (end < text.length) {
        final boundary = text.lastIndexOf(RegExp(r'\s'), end - 1);
        if (boundary > offset) {
          end = boundary + 1;
        } else if (text.codeUnitAt(end - 1) >= 0xd800 &&
            text.codeUnitAt(end - 1) <= 0xdbff) {
          end--; // Do not split a Unicode surrogate pair.
        }
      }
      yield text.substring(offset, end);
      offset = end;
    }
  }

  Future<void> _stopEngine() {
    final engine = _tts;
    if (engine == null) return Future.value();
    _stopping = _stopping.then((_) async {
      try {
        await engine.stop();
      } catch (_) {
        // Missing/unsupported speech engines must not interrupt the guide.
      }
    });
    return _stopping;
  }

  Future<void> stop() {
    _request++;
    _speaking = false;
    active = false;
    error = null;
    if (!_disposed) notifyListeners();
    return _stopEngine();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed && active) unawaited(stop());
  }

  @override
  void dispose() {
    _disposed = true;
    WidgetsBinding.instance.removeObserver(this);
    unawaited(stop());
    super.dispose();
  }
}
