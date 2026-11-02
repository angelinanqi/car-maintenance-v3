import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

class LocalStore {
  static const maxPhotoBytes = 10 * 1024 * 1024;
  static Future<void> validateImage(List<int> bytes) async {
    if (bytes.isEmpty || bytes.length > maxPhotoBytes)
      throw const FormatException('Invalid image size');
    final buffer = await ui.ImmutableBuffer.fromUint8List(
      Uint8List.fromList(bytes),
    );
    ui.ImageDescriptor? descriptor;
    try {
      descriptor = await ui.ImageDescriptor.encoded(buffer);
      if (descriptor.width > 8192 ||
          descriptor.height > 8192 ||
          descriptor.width * descriptor.height > 16000000) {
        throw const FormatException('Image dimensions are too large');
      }
      final codec = await descriptor.instantiateCodec(
        targetWidth: 1,
        targetHeight: 1,
      );
      try {
        if (codec.frameCount > 100)
          throw const FormatException('Image has too many frames');
        final frame = await codec.getNextFrame();
        frame.image.dispose();
      } finally {
        codec.dispose();
      }
    } finally {
      descriptor?.dispose();
      buffer.dispose();
    }
  }

  final Future<Directory> Function() directory;
  LocalStore({Future<Directory> Function()? directory})
    : directory = directory ?? getApplicationDocumentsDirectory;

  Future<Map<String, dynamic>?> read(String name) async {
    final folder = await directory();
    final file = File('${folder.path}/$name');
    if (!await file.exists()) return null;
    return jsonDecode(await file.readAsString()) as Map<String, dynamic>;
  }

  Future<void> write(String name, Map<String, dynamic> data) async {
    final folder = await directory();
    await folder.create(recursive: true);
    final file = File('${folder.path}/$name.tmp');
    await file.writeAsString(jsonEncode(data), flush: true);
    // Replace only after a complete write; a failed write keeps the old file.
    await file.rename('${folder.path}/$name');
  }

  Future<String> savePhoto(String source) async {
    final original = File(source);
    final length = await original.length();
    if (length == 0 || length > maxPhotoBytes) {
      throw const FormatException('Choose an image smaller than 10 MB.');
    }
    final bytes = await original.readAsBytes();
    try {
      await validateImage(bytes);
    } catch (_) {
      throw const FormatException('Choose a supported, undamaged image.');
    }
    final folder = await directory();
    final photos = Directory('${folder.path}/accident_photos');
    await photos.create(recursive: true);
    final target =
        '${photos.path}/${DateTime.now().microsecondsSinceEpoch}.img';
    try {
      await File(target).writeAsBytes(bytes, flush: true);
    } catch (_) {
      await removePhotoIfUnreferenced(target);
      rethrow;
    }
    return target;
  }

  Future<void> removePhotoIfUnreferenced(String path) async {
    try {
      final folder = await directory();
      final file = File(path).absolute;
      if (file.parent.path !=
              Directory('${folder.path}/accident_photos').absolute.path ||
          !await file.exists())
        return;
      await for (final entry in folder.list()) {
        if (entry is! File) continue;
        final name = entry.uri.pathSegments.last;
        if (!name.endsWith('.json') ||
            !(name.startsWith('accident_draft') ||
                name.startsWith('incidents_')))
          continue;
        final manifest = jsonDecode(await entry.readAsString());
        final rows = manifest is Map
            ? (manifest['drafts'] ?? manifest['records'] ?? [manifest])
            : null;
        if (rows is! List)
          return; // Never delete when references cannot be established.
        for (final row in rows) {
          if (row is! Map || row['photos'] is! List) return;
          if ((row['photos'] as List).contains(path)) return;
        }
      }
      await file.delete();
    } catch (_) {
      debugPrint(
        'WARNING [emergency-files] Unreferenced photo cleanup could not be confirmed; file retained.',
      );
    }
  }

  Future<void> cleanupPhotos() async {
    try {
      final folder = await directory();
      final photos = Directory('${folder.path}/accident_photos');
      if (!await photos.exists()) return;
      final cutoff = DateTime.now().subtract(const Duration(days: 1));
      await for (final entry in photos.list(followLinks: false)) {
        if (entry is File && (await entry.lastModified()).isBefore(cutoff)) {
          await removePhotoIfUnreferenced(entry.path);
        }
      }
    } catch (_) {
      debugPrint(
        'WARNING [emergency-files] Deferred photo cleanup failed; files retained for a later retry.',
      );
    }
  }

  Future<String> saveEmergencyImage(List<int> bytes) async {
    final folder = await directory();
    final images = Directory('${folder.path}/emergency_images');
    await images.create(recursive: true);
    final file = File(
      '${images.path}/${DateTime.now().microsecondsSinceEpoch}.img',
    );
    await file.writeAsBytes(bytes, flush: true);
    return file.path;
  }

  Future<bool> hasEmergencyImage(String path) async {
    final folder = await directory();
    final file = File(path).absolute;
    return file.parent.path ==
            Directory('${folder.path}/emergency_images').absolute.path &&
        await file.exists();
  }

  Future<void> removeEmergencyImage(String path) async {
    if (await hasEmergencyImage(path)) await File(path).delete();
  }
}
