import 'dart:async';
import 'package:geolocator/geolocator.dart';
import 'api_client.dart';

class NearbyPlace {
  final String id, name, address, phone, mapsUrl, businessStatus;
  final int distanceMetres;
  final List<Map<String, dynamic>> attributions;
  const NearbyPlace({
    required this.id,
    required this.name,
    required this.address,
    required this.phone,
    required this.mapsUrl,
    required this.businessStatus,
    required this.distanceMetres,
    required this.attributions,
  });

  factory NearbyPlace.fromJson(Map<String, dynamic> json) => NearbyPlace(
    id: json['id'] as String,
    name: json['name'] as String,
    address: json['address'] as String? ?? '',
    phone: json['phone'] as String? ?? '',
    mapsUrl: json['maps_url'] as String? ?? '',
    businessStatus: json['business_status'] as String? ?? '',
    distanceMetres: json['distance_metres'] as int,
    attributions: (json['attributions'] as List? ?? [])
        .map((value) => Map<String, dynamic>.from(value as Map))
        .toList(),
  );

  Uri? get dialUri {
    if (!RegExp(r'^\+?[0-9 ()-]{3,30}$').hasMatch(phone)) return null;
    final digits = phone.replaceAll(RegExp(r'[^0-9+]'), '');
    if (!RegExp(r'^\+?[0-9]{3,15}$').hasMatch(digits)) return null;
    return Uri(scheme: 'tel', path: digits);
  }

  Uri get mapsUri {
    final uri = Uri.tryParse(mapsUrl);
    if (uri != null &&
        uri.scheme == 'https' &&
        (uri.host == 'google.com' || uri.host.endsWith('.google.com'))) {
      return uri;
    }
    return Uri.https('www.google.com', '/maps/search/', {
      'api': '1',
      'query': '$name $address',
      'query_place_id': id,
    });
  }
}

class NearbyRepository {
  final ApiClient api;
  NearbyRepository(this.api);

  Future<List<NearbyPlace>> search({
    required double latitude,
    required double longitude,
    required String service,
    required int radiusMetres,
  }) async {
    final result = await api.post('/emergency/nearby', {
      'latitude': latitude,
      'longitude': longitude,
      'service': service,
      'radius_metres': radiusMetres,
    });
    try {
      return (result['places'] as List)
          .map(
            (row) =>
                NearbyPlace.fromJson(Map<String, dynamic>.from(row as Map)),
          )
          .toList();
    } on TypeError {
      throw const ApiException(
        'Nearby search returned an unexpected response. Please retry.',
      );
    }
  }
}

enum LocationSettingsAction { app, location }

class NearbyLocationException implements Exception {
  final String message;
  final LocationSettingsAction? settingsAction;
  const NearbyLocationException(this.message, [this.settingsAction]);
  @override
  String toString() => message;
}

class NearbyLocation {
  Future<Position> current() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      throw const NearbyLocationException(
        'Turn on device location to search around you, or search directly in Google Maps.',
        LocationSettingsAction.location,
      );
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.deniedForever) {
      throw const NearbyLocationException(
        'Location permission is blocked. Enable it in app settings, or search directly in Google Maps.',
        LocationSettingsAction.app,
      );
    }
    if (permission == LocationPermission.denied) {
      throw const NearbyLocationException(
        'Location permission was denied. Allow location when you retry, or search directly in Google Maps.',
      );
    }
    try {
      return await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(
          accuracy: LocationAccuracy.high,
          timeLimit: Duration(seconds: 20),
        ),
      );
    } on TimeoutException {
      throw const NearbyLocationException(
        'Could not get your location in time. Move somewhere with a clearer signal and retry, or use Google Maps.',
      );
    } on LocationServiceDisabledException {
      throw const NearbyLocationException(
        'Device location was switched off. Turn it on and retry.',
        LocationSettingsAction.location,
      );
    } on PermissionDeniedException {
      throw const NearbyLocationException(
        'Location access is unavailable. Check app permissions and retry.',
        LocationSettingsAction.app,
      );
    }
  }
}
