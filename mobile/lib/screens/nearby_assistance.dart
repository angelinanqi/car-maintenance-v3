import '../app_spacing.dart';
import 'dart:math' as math;
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:url_launcher/url_launcher.dart';
import '../data/nearby_repository.dart';
import '../data/api_client.dart';
import '../widgets/workshop_notes.dart';
import '../widgets/preview_mode.dart';

class NearbyAssistance extends StatefulWidget {
  final NearbyRepository repository;
  final NearbyLocation? location;
  final String? consultationNotes;
  const NearbyAssistance({
    super.key,
    required this.repository,
    this.location,
    this.consultationNotes,
  });

  @override
  State<NearbyAssistance> createState() => _NearbyAssistanceState();
}

class _NearbyAssistanceState extends State<NearbyAssistance> {
  static const int _resultsPerPage = 5;
  final _resultsKey = GlobalKey();
  int _page = 0;
  String _service = 'mechanic';
  int _radius = 5000;
  bool _busy = false;
  List<NearbyPlace>? _places;
  Position? _position;
  String? _error;
  LocationSettingsAction? _settingsAction;
  Timer? _cooldown;
  int _retrySeconds = 0;

  @override
  void dispose() {
    _cooldown?.cancel();
    super.dispose();
  }

  Future<void> _search() async {
    if (_busy || _retrySeconds > 0) return;
    if (previewExternalActions) {
      setState(() {
        _places = [];
        _page = 0;
        _error =
            'UI preview: location and provider searches are not sent. Use the controls to review the search layout.';
      });
      return;
    }
    setState(() {
      _busy = true;
      _places = null;
      _page = 0;
      _error = null;
      _settingsAction = null;
      _position = null;
    });
    try {
      final position = await (widget.location ?? NearbyLocation()).current();
      if (!mounted) return;
      _position = position;
      final places = await widget.repository.search(
        latitude: position.latitude,
        longitude: position.longitude,
        service: _service,
        radiusMetres: _radius,
      );
      if (mounted) {
        setState(() => _places = places);
        _scrollToResults();
      }
    } catch (error) {
      if (mounted) {
        if (error is ApiException && error.statusCode == 429) {
          _retrySeconds = (error.retryAfter ?? 60).clamp(1, 3600);
          _cooldown?.cancel();
          _cooldown = Timer.periodic(const Duration(seconds: 1), (timer) {
            if (!mounted) {
              timer.cancel();
              return;
            }
            setState(() => _retrySeconds--);
            if (_retrySeconds == 0) timer.cancel();
          });
        }
        setState(() {
          _error = error is NearbyLocationException
              ? error.message
              : error is ApiException && error.statusCode == 429
              ? 'Too many nearby searches. Wait for the retry timer, or use Google Maps below.'
              : 'Nearby search is unavailable. Check your connection and retry, or search directly in Google Maps below.';
          if (error is NearbyLocationException) {
            _settingsAction = error.settingsAction;
          }
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _open(Uri uri) async {
    if (previewExternalActions) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Preview only. No external call or map is opened.'),
        ),
      );
      return;
    }
    if (!['https', 'http', 'tel'].contains(uri.scheme)) return;
    try {
      if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
        throw StateError('No handler');
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Could not open this action. Check that a dialer or browser is available.',
            ),
          ),
        );
      }
    }
  }

  Uri _mapsSearch(String service) {
    final area = _position == null
        ? 'near me'
        : 'near ${_position!.latitude},${_position!.longitude}';
    return Uri.https('www.google.com', '/maps/search/', {
      'api': '1',
      'query': '$service $area',
    });
  }

  Future<void> _openSettings() async {
    final action = _settingsAction;
    try {
      final opened = action == LocationSettingsAction.app
          ? await Geolocator.openAppSettings()
          : await Geolocator.openLocationSettings();
      if (!opened) throw StateError('Settings unavailable');
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Open device settings to enable location, then retry.',
            ),
          ),
        );
      }
    }
  }

  Widget _place(NearbyPlace place) => Card.outlined(
    color: Colors.white,
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(place.name, style: Theme.of(context).textTheme.titleMedium),
          Text(
            '${(place.distanceMetres / 1000).toStringAsFixed(1)} km away · straight-line distance',
          ),
          if (place.address.isNotEmpty) Text(place.address),
          if (place.businessStatus == 'CLOSED_TEMPORARILY')
            const Text('Listed as temporarily closed'),
          const SizedBox(height: 8),
          SelectableText(
            place.phone.isEmpty ? 'Phone number not listed' : place.phone,
          ),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              FilledButton.icon(
                onPressed: place.dialUri == null
                    ? null
                    : () => _open(place.dialUri!),
                icon: const Icon(Icons.call),
                label: const Text('Call'),
              ),
              OutlinedButton.icon(
                onPressed: () => _open(place.mapsUri),
                icon: const Icon(Icons.map_outlined),
                label: const Text('Open Maps'),
              ),
            ],
          ),
          for (final attribution in place.attributions)
            TextButton(
              onPressed: () {
                final uri = Uri.tryParse(
                  attribution['providerUri'] as String? ?? '',
                );
                if (uri != null &&
                    ['https', 'http'].contains(uri.scheme) &&
                    uri.host.isNotEmpty) {
                  _open(uri);
                }
              },
              child: Text(
                attribution['provider'] as String? ?? 'Data provider',
              ),
            ),
        ],
      ),
    ),
  );

  void _changePage(int page) {
    final places = _places;
    if (places == null ||
        page < 0 ||
        page >= (places.length / _resultsPerPage).ceil()) {
      return;
    }
    setState(() => _page = page);
    _scrollToResults();
  }

  void _scrollToResults() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final target = _resultsKey.currentContext;
      if (mounted && target != null) {
        Scrollable.ensureVisible(
          target,
          duration: const Duration(milliseconds: 250),
        );
      }
    });
  }

  Widget _pagination(int pageCount) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 12),
    child: Column(
      children: [
        Text('Page ${_page + 1} of $pageCount'),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: OutlinedButton(
                onPressed: _page > 0 ? () => _changePage(_page - 1) : null,
                child: const Text('Previous'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: FilledButton(
                onPressed: _page + 1 < pageCount
                    ? () => _changePage(_page + 1)
                    : null,
                child: const Text('Next'),
              ),
            ),
          ],
        ),
      ],
    ),
  );

  Widget _results() {
    final places = _places!;
    final pageCount = (places.length / _resultsPerPage).ceil();
    final start = _page * _resultsPerPage;
    final end = math.min(start + _resultsPerPage, places.length);
    return Container(
      key: _resultsKey,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border.all(color: Colors.grey.shade300),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'Google Maps',
            style: TextStyle(fontSize: 14, color: Color(0xFF1F1F1F)),
          ),
          Text('Within ${_radius ~/ 1000} km, ranked by proximity.'),
          if (places.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 16),
              child: Text(
                'No businesses found. Try a wider radius or search in Google Maps.',
              ),
            )
          else ...[
            const SizedBox(height: 8),
            Semantics(
              liveRegion: true,
              child: Text(
                'Showing ${start + 1}–$end of ${places.length} results',
                style: Theme.of(context).textTheme.titleMedium,
              ),
            ),
            if (pageCount > 1) _pagination(pageCount),
            ...places.skip(start).take(_resultsPerPage).map(_place),
            if (pageCount > 1) _pagination(pageCount),
          ],
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Nearby assistance')),
    body: ListView(
      padding: const EdgeInsets.all(AppSpacing.screen),
      children: [
        if (widget.consultationNotes?.isNotEmpty == true)
          WorkshopNotes(notes: widget.consultationNotes!),
        const Text(
          'Find a workshop to call',
          style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
        ),
        const SizedBox(height: 8),
        const Text(
          'Requires internet. Search uses your current location and shares it with our backend and Google to find nearby businesses. No account is needed.',
        ),
        const SizedBox(height: 16),
        DropdownButtonFormField<String>(
          isExpanded: true,
          itemHeight: null,
          initialValue: _service,
          decoration: const InputDecoration(labelText: 'Service'),
          items: const [
            DropdownMenuItem(
              value: 'mechanic',
              child: Text('Mechanics / workshops'),
            ),
            DropdownMenuItem(value: 'tyres', child: Text('Tyre shops')),
          ],
          onChanged: _busy
              ? null
              : (value) => setState(() {
                  _service = value!;
                  _places = null;
                  _page = 0;
                  _error = null;
                }),
        ),
        const SizedBox(height: 12),
        DropdownButtonFormField<int>(
          isExpanded: true,
          itemHeight: null,
          initialValue: _radius,
          decoration: const InputDecoration(labelText: 'Search radius'),
          items: const [
            DropdownMenuItem(value: 5000, child: Text('5 km')),
            DropdownMenuItem(value: 10000, child: Text('10 km')),
            DropdownMenuItem(value: 20000, child: Text('20 km')),
            DropdownMenuItem(value: 50000, child: Text('50 km')),
          ],
          onChanged: _busy
              ? null
              : (value) => setState(() {
                  _radius = value!;
                  _places = null;
                  _page = 0;
                  _error = null;
                }),
        ),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: _busy || _retrySeconds > 0 ? null : _search,
          icon: const Icon(Icons.my_location),
          label: Text(
            _busy
                ? 'Finding nearby businesses...'
                : _retrySeconds > 0
                ? 'Retry in $_retrySeconds s'
                : 'Search nearby',
          ),
        ),
        if (_busy)
          const LinearProgressIndicator(
            semanticsLabel: 'Searching nearby assistance',
          ),
        if (_error != null) ...[
          const SizedBox(height: 12),
          Text(
            _error!,
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
          if (_settingsAction != null)
            TextButton(
              onPressed: _openSettings,
              child: const Text('Open location settings'),
            ),
        ],
        const SizedBox(height: 12),
        const Text(
          'Call to confirm availability, roadside call-outs and charges. A workshop listing does not confirm towing service or current opening hours.',
        ),
        if (_position != null && _places != null)
          Text(
            'Location accuracy: about ${_position!.accuracy.round()} m. Search again if you move.',
          ),
        if (_places != null) ...[const SizedBox(height: 16), _results()],
        const SizedBox(height: 16),
        OutlinedButton.icon(
          onPressed: () => _open(
            _mapsSearch(_service == 'tyres' ? 'tyre shop' : 'car repair'),
          ),
          icon: const Icon(Icons.open_in_new),
          label: const Text('Search directly in Google Maps'),
        ),
        OutlinedButton.icon(
          onPressed: () => _open(_mapsSearch('towing service')),
          icon: const Icon(Icons.local_shipping_outlined),
          label: const Text('Find towing in Google Maps'),
        ),
        const Text(
          'Towing opens Google Maps for a separate search. It is not included in the workshop results above.',
        ),
        const SizedBox(height: 8),
        Wrap(
          children: [
            TextButton(
              onPressed: () =>
                  _open(Uri.parse('https://maps.google.com/help/terms_maps/')),
              child: const Text('Google Maps terms'),
            ),
            TextButton(
              onPressed: () =>
                  _open(Uri.parse('https://policies.google.com/privacy')),
              child: const Text('Google privacy'),
            ),
          ],
        ),
      ],
    ),
  );
}
