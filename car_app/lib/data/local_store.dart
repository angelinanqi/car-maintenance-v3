import 'dart:convert';
import 'dart:io';
import 'package:path_provider/path_provider.dart';

class LocalStore {
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
    final folder = await directory();
    final photos = Directory('${folder.path}/accident_photos');
    await photos.create(recursive: true);
    final extension = source.split('.').last.toLowerCase();
    final target =
        '${photos.path}/${DateTime.now().microsecondsSinceEpoch}.$extension';
    await File(source).copy(target);
    return target;
  }

  Future<void> removePhoto(String photo) async {
    final folder = await directory();
    final parent = Directory('${folder.path}/accident_photos').absolute.path;
    final file = File(photo).absolute;
    if (file.parent.path == parent && await file.exists()) await file.delete();
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
