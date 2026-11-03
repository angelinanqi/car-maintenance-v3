import 'dart:async';
import 'package:geocoding/geocoding.dart';
import 'package:geolocator/geolocator.dart';

class AccidentLocationException implements Exception {
  final String message;
  const AccidentLocationException(this.message);
}

class AccidentLocation {
  Future<Position> position() async {
    if (!await Geolocator.isLocationServiceEnabled()) {
      throw const AccidentLocationException(
        'Device location is off. Turn it on and retry, or enter the accident location yourself.',
      );
    }
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.deniedForever) {
      throw const AccidentLocationException(
        'Location permission is blocked. Enable it in app settings, or enter the accident location yourself.',
      );
    }
    if (permission == LocationPermission.denied) {
      throw const AccidentLocationException(
        'Location permission was denied. You can still enter the accident location yourself.',
      );
    }
    return Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high,
        timeLimit: Duration(seconds: 20),
      ),
    );
  }

  Future<String> current() async {
    final position = await this.position();
    final coordinates =
        '${position.latitude.toStringAsFixed(6)}, ${position.longitude.toStringAsFixed(6)}';
    try {
      final places = await placemarkFromCoordinates(
        position.latitude,
        position.longitude,
      ).timeout(const Duration(seconds: 5));
      if (places.isNotEmpty) {
        final place = places.first;
        final address =
            [
                  place.street,
                  place.subLocality,
                  place.locality,
                  place.administrativeArea,
                  place.postalCode,
                ]
                .whereType<String>()
                .where((part) => part.trim().isNotEmpty)
                .toSet()
                .join(', ');
        if (address.isNotEmpty) return '$address ($coordinates)';
      }
    } catch (_) {
      // GPS coordinates remain useful if address lookup is unavailable or offline.
    }
    return coordinates;
  }
}
